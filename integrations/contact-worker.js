/**
 * Privacy-safe contact bridge and authenticated CMS submitter for Cloudflare Workers.
 *
 * Required contact secrets:
 *   WEB3FORMS_ACCESS_KEY, GITHUB_TOKEN
 *
 * Required CMS secret:
 *   GITHUB_OAUTH_CLIENT_SECRET
 *
 * GITHUB_OAUTH_CLIENT_ID defaults to this site's public OAuth App client ID.
 * CMS_SESSION_SECRET is optional; when omitted, the Worker derives the signing
 * key from GITHUB_OAUTH_CLIENT_SECRET without exposing it to the browser.
 *
 * GITHUB_TOKEN must be a fine-grained token owned by the repository owner and
 * limited to this repository. It needs Contents: write for repository_dispatch
 * and Issues: write for CMS batch submission, plus Actions: read for live
 * processing and deployment status.
 *
 * Optional secrets/vars:
 *   TURNSTILE_SECRET
 *   CLOUDFLARE_ANALYTICS_API_TOKEN  Account Analytics: Read token
 *   CLOUDFLARE_ACCOUNT_ID           account containing Web Analytics data
 *   ANALYTICS_SITE_HOST             defaults to SITE_ORIGIN hostname
 *   GOOGLE_ANALYTICS_SERVICE_ACCOUNT_JSON  GA4 read-only service account JSON
 *   GOOGLE_ANALYTICS_PROPERTY_ID          numeric GA4 property ID
 *   SITE_ORIGIN              defaults to https://hctsui.github.io
 *   ADMIN_URL                defaults to https://hctsui.github.io/admin/
 *   CMS_ALLOWED_GITHUB_LOGIN defaults to hctsui
 *   GITHUB_REPOSITORY        defaults to hctsui/hctsui.github.io
 *   EMAIL_SUBJECT
 */
const utf8 = new TextEncoder();
const decoder = new TextDecoder();
const SESSION_SECONDS = 14 * 24 * 60 * 60;
const OAUTH_SECONDS = 10 * 60;
const DEFAULT_OAUTH_CLIENT_ID = "Ov23liuhyCd8KNHvlDLA";
const ANALYTICS_CACHE_SECONDS = 5 * 60;
const analyticsCache = new Map();
const googleTokenCache = new Map();

const clean = (value, max) => String(value || "").replace(/[\u0000-\u001f]/g, "").trim().slice(0, max);
const emailOk = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
const nowSeconds = () => Math.floor(Date.now() / 1000);
const oauthClientId = (env) => clean(env.GITHUB_OAUTH_CLIENT_ID, 200) || DEFAULT_OAUTH_CLIENT_ID;
const cmsSessionSecret = (env) => clean(env.CMS_SESSION_SECRET, 500) || clean(env.GITHUB_OAUTH_CLIENT_SECRET, 500);

function base64UrlEncode(value) {
  const bytes = typeof value === "string" ? utf8.encode(value) : new Uint8Array(value);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(value) {
  const normalized = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(normalized + "=".repeat((4 - normalized.length % 4) % 4));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function hmac(secret, value) {
  const key = await crypto.subtle.importKey("raw", utf8.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, utf8.encode(value)));
}

async function signedToken(payload, secret) {
  const body = base64UrlEncode(JSON.stringify(payload));
  return `${body}.${base64UrlEncode(await hmac(secret, body))}`;
}

function timingSafeEqual(left, right) {
  const a = new Uint8Array(left);
  const b = new Uint8Array(right);
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let index = 0; index < a.length; index++) difference |= a[index] ^ b[index];
  return difference === 0;
}

async function verifySignedToken(token, secret, expectedKind) {
  try {
    const [body, signature, extra] = String(token || "").split(".");
    if (!body || !signature || extra) return null;
    const expected = await hmac(secret, body);
    if (!timingSafeEqual(expected, base64UrlDecode(signature))) return null;
    const payload = JSON.parse(decoder.decode(base64UrlDecode(body)));
    if (payload.kind !== expectedKind || !Number.isFinite(payload.exp) || payload.exp <= nowSeconds()) return null;
    return payload;
  } catch {
    return null;
  }
}

function randomToken(bytes = 32) {
  const value = new Uint8Array(bytes);
  crypto.getRandomValues(value);
  return base64UrlEncode(value);
}

function parseCookies(request) {
  return Object.fromEntries((request.headers.get("cookie") || "").split(";").map((part) => {
    const index = part.indexOf("=");
    return index < 0 ? ["", ""] : [part.slice(0, index).trim(), part.slice(index + 1).trim()];
  }).filter(([key]) => key));
}

function corsHeaders(origin) {
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET, POST, OPTIONS",
    "access-control-allow-headers": "authorization, content-type, accept",
    "vary": "Origin",
  };
}

const json = (data, status = 200, origin = "*") => new Response(JSON.stringify(data), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", ...corsHeaders(origin) },
});

function redirect(location, headers = {}) {
  return new Response(null, { status: 302, headers: { location, "cache-control": "no-store", ...headers } });
}

function adminRedirect(env, parameters) {
  const adminUrl = clean(env.ADMIN_URL, 500) || "https://hctsui.github.io/admin/";
  const fragment = new URLSearchParams(parameters).toString();
  return redirect(`${adminUrl.replace(/#.*$/, "")}#${fragment}`);
}

async function verifyTurnstile(secret, token, ip) {
  if (!secret) return true;
  if (!token) return false;
  const body = new URLSearchParams({ secret, response: token });
  if (ip) body.set("remoteip", ip);
  const response = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body });
  const result = await response.json();
  return result.success === true;
}

async function parsePayload(request) {
  const type = request.headers.get("content-type") || "";
  if (type.includes("application/json")) return await request.json();
  const form = await request.formData();
  return Object.fromEntries(form.entries());
}

async function oauthStart(request, env) {
  const sessionSecret = cmsSessionSecret(env);
  if (!env.GITHUB_OAUTH_CLIENT_SECRET || !sessionSecret) {
    return adminRedirect(env, { github_error: "GitHub 登入服務尚未設定完成" });
  }
  const url = new URL(request.url);
  const state = randomToken(24);
  const verifier = randomToken(48);
  const challenge = base64UrlEncode(await crypto.subtle.digest("SHA-256", utf8.encode(verifier)));
  const oauthState = await signedToken({ kind: "oauth", state, verifier, exp: nowSeconds() + OAUTH_SECONDS }, sessionSecret);
  const authorize = new URL("https://github.com/login/oauth/authorize");
  authorize.searchParams.set("client_id", oauthClientId(env));
  authorize.searchParams.set("redirect_uri", `${url.origin}/cms/auth/callback`);
  authorize.searchParams.set("state", state);
  authorize.searchParams.set("login", clean(env.CMS_ALLOWED_GITHUB_LOGIN, 100) || "hctsui");
  authorize.searchParams.set("code_challenge", challenge);
  authorize.searchParams.set("code_challenge_method", "S256");
  return redirect(authorize.toString(), {
    "set-cookie": `cms_oauth=${oauthState}; Path=/cms/auth; Max-Age=${OAUTH_SECONDS}; HttpOnly; Secure; SameSite=Lax`,
  });
}

async function oauthCallback(request, env) {
  const sessionSecret = cmsSessionSecret(env);
  if (!env.GITHUB_OAUTH_CLIENT_SECRET || !sessionSecret) {
    return adminRedirect(env, { github_error: "GitHub 登入服務尚未設定完成" });
  }
  const url = new URL(request.url);
  const stored = await verifySignedToken(parseCookies(request).cms_oauth, sessionSecret, "oauth");
  if (!stored || !url.searchParams.get("code") || stored.state !== url.searchParams.get("state")) {
    return adminRedirect(env, { github_error: "登入驗證已過期，請再試一次" });
  }
  const tokenResponse = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json", "user-agent": "hctsui-cms-submit" },
    body: JSON.stringify({
      client_id: oauthClientId(env),
      client_secret: env.GITHUB_OAUTH_CLIENT_SECRET,
      code: url.searchParams.get("code"),
      redirect_uri: `${url.origin}/cms/auth/callback`,
      code_verifier: stored.verifier,
    }),
  });
  const tokenData = await tokenResponse.json().catch(() => ({}));
  if (!tokenResponse.ok || !tokenData.access_token) return adminRedirect(env, { github_error: "GitHub 無法完成登入" });
  const userResponse = await fetch("https://api.github.com/user", {
    headers: {
      accept: "application/vnd.github+json",
      authorization: `Bearer ${tokenData.access_token}`,
      "x-github-api-version": "2022-11-28",
      "user-agent": "hctsui-cms-submit",
    },
  });
  const user = await userResponse.json().catch(() => ({}));
  const allowed = (clean(env.CMS_ALLOWED_GITHUB_LOGIN, 300) || "hctsui").split(",").map((login) => login.trim().toLowerCase()).filter(Boolean);
  if (!userResponse.ok || !allowed.includes(String(user.login || "").toLowerCase())) {
    return adminRedirect(env, { github_error: "這個 GitHub 帳號沒有網站送出權限" });
  }
  const expires = nowSeconds() + SESSION_SECONDS;
  const session = await signedToken({ kind: "session", sub: user.login, exp: expires }, sessionSecret);
  return adminRedirect(env, { github_session: session, github_login: user.login, github_expires: String(expires) });
}

async function requireSession(request, env) {
  const sessionSecret = cmsSessionSecret(env);
  if (!sessionSecret) return null;
  const header = request.headers.get("authorization") || "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  const session = await verifySignedToken(match?.[1], sessionSecret, "session");
  const allowed = (clean(env.CMS_ALLOWED_GITHUB_LOGIN, 300) || "hctsui").split(",").map((login) => login.trim().toLowerCase()).filter(Boolean);
  return session && allowed.includes(String(session.sub || "").toLowerCase()) ? session : null;
}

async function gzipBase64(text) {
  const compressed = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  const bytes = new Uint8Array(await new Response(compressed).arrayBuffer());
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return `gzip-base64:${btoa(binary)}`;
}

function githubHeaders(env) {
  return {
    accept: "application/vnd.github+json",
    authorization: `Bearer ${env.GITHUB_TOKEN}`,
    "x-github-api-version": "2022-11-28",
    "user-agent": "hctsui-cms-submit",
    "content-type": "application/json",
  };
}

async function existingIssue(env, repository, requestId) {
  const response = await fetch(`https://api.github.com/repos/${repository}/issues?state=all&per_page=50&sort=created&direction=desc`, {
    headers: githubHeaders(env),
  });
  if (!response.ok) throw new Error("GitHub idempotency check failed");
  const marker = `<!-- cms-request:${requestId} -->`;
  const issues = await response.json();
  return issues.find((issue) => !issue.pull_request && String(issue.body || "").includes(marker)) || null;
}

async function submitCms(request, env, origin) {
  const session = await requireSession(request, env);
  if (!session) return json({ success: false, code: "login_required", message: "請重新登入 GitHub" }, 401, origin);
  if (!env.GITHUB_TOKEN) return json({ success: false, message: "網站送出服務尚未設定 GitHub Token" }, 503, origin);
  let raw;
  try { raw = await request.json(); }
  catch { return json({ success: false, message: "送出資料格式不正確" }, 400, origin); }
  const requestId = clean(raw.request_id, 80);
  const batch = raw.payload;
  if (!/^[a-zA-Z0-9_-]{16,80}$/.test(requestId)) return json({ success: false, message: "送出識別碼不正確" }, 400, origin);
  if (!batch || batch.schema_version !== 2 || !Array.isArray(batch.operations) || !batch.operations.length) {
    return json({ success: false, message: "沒有可送出的網站修改" }, 400, origin);
  }
  const batchText = JSON.stringify(batch);
  if (batchText.length > 1_500_000) return json({ success: false, message: "這次修改太大，請分成兩次送出" }, 413, origin);
  const repository = clean(env.GITHUB_REPOSITORY, 200) || "hctsui/hctsui.github.io";
  let duplicate;
  try { duplicate = await existingIssue(env, repository, requestId); }
  catch { return json({ success: false, message: "GitHub 暫時無法確認是否已送出；為避免重複，請稍後重試" }, 502, origin); }
  if (duplicate) return json({ success: true, duplicate: true, issue: { number: duplicate.number, url: duplicate.html_url } }, 200, origin);
  let encoded;
  try { encoded = await gzipBase64(batchText); }
  catch { return json({ success: false, message: "伺服器無法壓縮本次修改" }, 500, origin); }
  const marker = `<!-- cms-request:${requestId} -->`;
  const body = `### Batch payload / 批次資料\n\n\`\`\`json\n${encoded}\n\`\`\`\n\n${marker}`;
  if (body.length > 64_000) return json({ success: false, message: "壓縮後仍超過 GitHub 限制，請分成兩次送出" }, 413, origin);
  const created = await fetch(`https://api.github.com/repos/${repository}/issues`, {
    method: "POST",
    headers: githubHeaders(env),
    body: JSON.stringify({ title: `[Website: Batch] ${new Date().toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}`, body }),
  });
  const issue = await created.json().catch(() => ({}));
  if (!created.ok) {
    const message = created.status === 403 ? "GitHub Token 尚未開啟 Issues 寫入權限" : "GitHub 暫時無法建立修改請求";
    return json({ success: false, message, detail: clean(issue.message, 300) }, 502, origin);
  }
  return json({ success: true, issue: { number: issue.number, url: issue.html_url }, login: session.sub }, 201, origin);
}

async function githubJson(env, url) {
  const response = await fetch(url, { headers: githubHeaders(env) });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) {
    const reason = new Error(clean(value?.message, 300) || `GitHub status request failed (${response.status})`);
    reason.status = response.status;
    throw reason;
  }
  return value;
}

function workflowFailure(run) {
  return run?.status === "completed" && run?.conclusion !== "success" && run?.conclusion !== "skipped";
}

async function cmsStatus(request, env, origin) {
  const session = await requireSession(request, env);
  if (!session) return json({ success: false, code: "login_required", message: "請重新登入 GitHub" }, 401, origin);
  if (!env.GITHUB_TOKEN) return json({ success: false, message: "網站送出服務尚未設定 GitHub Token" }, 503, origin);
  const issueNumber = Number(new URL(request.url).searchParams.get("issue"));
  if (!Number.isSafeInteger(issueNumber) || issueNumber < 1) return json({ success: false, message: "修改請求編號不正確" }, 400, origin);
  const repository = clean(env.GITHUB_REPOSITORY, 200) || "hctsui/hctsui.github.io";
  const api = `https://api.github.com/repos/${repository}`;
  try {
    const issue = await githubJson(env, `${api}/issues/${issueNumber}`);
    const processRuns = await githubJson(env, `${api}/actions/workflows/process-website-batch.yml/runs?event=issues&per_page=50`);
    const processRun = (processRuns.workflow_runs || []).find((run) => run.display_title === issue.title);
    const base = {
      success: true,
      issue: { number: issue.number, url: issue.html_url },
      checked_at: new Date().toISOString(),
    };
    if (!processRun) return json({ ...base, stage: "queued", message: "修改請求已建立，等待 GitHub 開始處理" }, 200, origin);
    if (workflowFailure(processRun)) {
      return json({ ...base, stage: "failed", message: "自動處理失敗，草稿已保留", log_url: processRun.html_url }, 200, origin);
    }
    if (processRun.status !== "completed") {
      return json({ ...base, stage: "processing", message: "正在檢查並套用網站修改", action_url: processRun.html_url }, 200, origin);
    }

    const commits = await githubJson(env, `${api}/commits?sha=cms&per_page=100`);
    const commit = (Array.isArray(commits) ? commits : []).find((entry) => String(entry?.commit?.message || "").includes(`issue #${issueNumber}`));
    const deployRuns = await githubJson(env, `${api}/actions/workflows/deploy-cms-pages.yml/runs?branch=cms&per_page=50`);
    const processFinished = Date.parse(processRun.updated_at || processRun.created_at || 0) || 0;
    const deployment = (deployRuns.workflow_runs || []).find((run) => commit && run.head_sha === commit.sha)
      || (deployRuns.workflow_runs || []).find((run) => (Date.parse(run.created_at || 0) || 0) >= processFinished - 5000);
    if (!deployment) {
      return json({ ...base, stage: "publishing", message: "修改已套用，等待網站發布", action_url: processRun.html_url }, 200, origin);
    }
    if (workflowFailure(deployment)) {
      return json({ ...base, stage: "failed", message: "網站發布失敗，草稿已保留", log_url: deployment.html_url }, 200, origin);
    }
    if (deployment.status !== "completed") {
      return json({ ...base, stage: "publishing", message: "修改已套用，正在發布網站", action_url: deployment.html_url }, 200, origin);
    }
    return json({ ...base, stage: "completed", message: "網站發布完成", action_url: deployment.html_url, site_url: clean(env.SITE_ORIGIN, 300) || "https://hctsui.github.io" }, 200, origin);
  } catch (reason) {
    const status = reason?.status === 403 ? 503 : 502;
    const message = reason?.status === 403 ? "GitHub Token 尚未開啟 Actions 讀取權限" : "暫時無法讀取 GitHub 處理狀態";
    return json({ success: false, code: "status_unavailable", message }, status, origin);
  }
}

const ANALYTICS_RANGES = { "1d": 1, "7d": 7, "30d": 30, "90d": 90 };
const numberValue = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};
const dimensionRows = (rows, field, value = (row) => row?.count) => (Array.isArray(rows) ? rows : []).map((row) => ({
  label: clean(row?.dimensions?.[field] || "(未提供)", 300) || "(未提供)",
  value: numberValue(value(row)),
})).filter((row) => row.value > 0);

function analyticsRange(url) {
  const key = clean(url.searchParams.get("range"), 10).toLowerCase();
  return { key: ANALYTICS_RANGES[key] ? key : "7d", days: ANALYTICS_RANGES[key] || 7 };
}

function analyticsHost(env) {
  const configured = clean(env.ANALYTICS_SITE_HOST, 255).toLowerCase();
  if (configured) return configured;
  try { return new URL(clean(env.SITE_ORIGIN, 300) || "https://hctsui.github.io").hostname.toLowerCase(); }
  catch { return "hctsui.github.io"; }
}

function normalizedAnalytics(provider, range, summary, sections) {
  return {
    success: true,
    provider,
    range: range.key,
    days: range.days,
    generated_at: new Date().toISOString(),
    summary: {
      views: numberValue(summary.views),
      visits: summary.visits == null ? null : numberValue(summary.visits),
      users: summary.users == null ? null : numberValue(summary.users),
    },
    trend: sections.trend || [],
    top_pages: sections.top_pages || [],
    referrers: sections.referrers || [],
    countries: sections.countries || [],
    devices: sections.devices || [],
    browsers: sections.browsers || [],
  };
}

const CLOUDFLARE_ANALYTICS_QUERY = `
query AdminAnalytics($accountTag:String!,$host:String!,$start:Time!,$end:Time!){
  viewer{accounts(filter:{accountTag:$accountTag}){
    totals:rumPageloadEventsAdaptiveGroups(limit:1,filter:{requestHost:$host,datetime_geq:$start,datetime_lt:$end}){count sum{visits}}
    daily:rumPageloadEventsAdaptiveGroups(limit:100,orderBy:[date_ASC],filter:{requestHost:$host,datetime_geq:$start,datetime_lt:$end}){dimensions{date} count sum{visits}}
    pages:rumPageloadEventsAdaptiveGroups(limit:12,orderBy:[count_DESC],filter:{requestHost:$host,datetime_geq:$start,datetime_lt:$end}){dimensions{requestPath} count}
    referrers:rumPageloadEventsAdaptiveGroups(limit:12,orderBy:[count_DESC],filter:{requestHost:$host,datetime_geq:$start,datetime_lt:$end}){dimensions{refererHost} count}
    countries:rumPageloadEventsAdaptiveGroups(limit:12,orderBy:[count_DESC],filter:{requestHost:$host,datetime_geq:$start,datetime_lt:$end}){dimensions{countryName} count}
    devices:rumPageloadEventsAdaptiveGroups(limit:8,orderBy:[count_DESC],filter:{requestHost:$host,datetime_geq:$start,datetime_lt:$end}){dimensions{deviceType} count}
    browsers:rumPageloadEventsAdaptiveGroups(limit:10,orderBy:[count_DESC],filter:{requestHost:$host,datetime_geq:$start,datetime_lt:$end}){dimensions{userAgentBrowser} count}
  }}
}`;

async function cloudflareAnalytics(env, range) {
  const token = clean(env.CLOUDFLARE_ANALYTICS_API_TOKEN || env.CLOUDFLARE_API_TOKEN, 2000);
  const accountId = clean(env.CLOUDFLARE_ACCOUNT_ID, 100);
  if (!token || !accountId) {
    const error = new Error("Cloudflare 報表尚未設定：請在 Worker 加入 Account Analytics 唯讀 Token 與 Account ID。");
    error.code = "analytics_not_configured";
    throw error;
  }
  const end = new Date();
  const start = new Date(end.getTime() - range.days * 86400000);
  const response = await fetch("https://api.cloudflare.com/client/v4/graphql", {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({
      query: CLOUDFLARE_ANALYTICS_QUERY,
      variables: { accountTag: accountId, host: analyticsHost(env), start: start.toISOString(), end: end.toISOString() },
    }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.errors?.length) {
    const detail = clean(payload.errors?.map((item) => item.message).join("; ") || payload?.errors?.[0]?.message, 500);
    const error = new Error(detail ? `Cloudflare 暫時無法讀取報表：${detail}` : "Cloudflare 暫時無法讀取報表。");
    error.code = "analytics_provider_error";
    throw error;
  }
  const account = payload?.data?.viewer?.accounts?.[0];
  if (!account) {
    const error = new Error("Cloudflare Token 無法讀取指定帳戶，請檢查 Account ID 與權限範圍。");
    error.code = "analytics_provider_error";
    throw error;
  }
  const totals = account.totals?.[0] || {};
  return normalizedAnalytics("cloudflare", range, { views: totals.count, visits: totals.sum?.visits, users: null }, {
    trend: (account.daily || []).map((row) => ({ date: clean(row?.dimensions?.date, 20), views: numberValue(row?.count), visits: numberValue(row?.sum?.visits), users: null })).filter((row) => row.date),
    top_pages: dimensionRows(account.pages, "requestPath"),
    referrers: dimensionRows(account.referrers, "refererHost").map((row) => row.label === "(未提供)" ? { ...row, label: "直接進入／未知" } : row),
    countries: dimensionRows(account.countries, "countryName"),
    devices: dimensionRows(account.devices, "deviceType"),
    browsers: dimensionRows(account.browsers, "userAgentBrowser"),
  });
}

function pemKeyBytes(pem) {
  const body = String(pem || "").replace(/\\n/g, "\n").replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g, "");
  if (!body) throw new Error("Google 服務帳戶私鑰格式不正確。");
  const binary = atob(body);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function googleAccessToken(env) {
  let credentials;
  try { credentials = JSON.parse(String(env.GOOGLE_ANALYTICS_SERVICE_ACCOUNT_JSON || "")); }
  catch {
    const error = new Error("Google Analytics 服務帳戶 JSON 格式不正確。");
    error.code = "analytics_not_configured";
    throw error;
  }
  const email = clean(credentials?.client_email, 320);
  const privateKey = String(credentials?.private_key || "");
  if (!email || !privateKey) {
    const error = new Error("Google 報表尚未設定：請在 Worker 加入唯讀服務帳戶 JSON 與 GA4 Property ID。");
    error.code = "analytics_not_configured";
    throw error;
  }
  const cached = googleTokenCache.get(email);
  if (cached?.expires > nowSeconds() + 60) return cached.token;
  const issued = nowSeconds();
  const header = base64UrlEncode(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claims = base64UrlEncode(JSON.stringify({
    iss: email,
    scope: "https://www.googleapis.com/auth/analytics.readonly",
    aud: "https://oauth2.googleapis.com/token",
    iat: issued,
    exp: issued + 3600,
  }));
  let key;
  try {
    key = await crypto.subtle.importKey("pkcs8", pemKeyBytes(privateKey), { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  } catch {
    const error = new Error("Google 服務帳戶私鑰無法使用，請重新貼上完整 JSON。");
    error.code = "analytics_not_configured";
    throw error;
  }
  const unsigned = `${header}.${claims}`;
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, utf8.encode(unsigned));
  const assertion = `${unsigned}.${base64UrlEncode(signature)}`;
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || !payload.access_token) {
    const error = new Error("Google 無法驗證報表服務帳戶，請檢查帳戶金鑰與 GA4 權限。");
    error.code = "analytics_provider_error";
    throw error;
  }
  googleTokenCache.set(email, { token: payload.access_token, expires: issued + Math.min(numberValue(payload.expires_in) || 3600, 3600) });
  return payload.access_token;
}

function gaRequest(days, dimension, limit = 12) {
  const request = {
    dateRanges: [{ startDate: days === 1 ? "today" : `${days - 1}daysAgo`, endDate: "today" }],
    metrics: [{ name: "screenPageViews" }, { name: "sessions" }, { name: "totalUsers" }],
    limit: String(limit),
  };
  if (dimension) {
    request.dimensions = [{ name: dimension }];
    request.orderBys = dimension === "date"
      ? [{ dimension: { dimensionName: "date" }, desc: false }]
      : [{ metric: { metricName: "screenPageViews" }, desc: true }];
  }
  return request;
}

async function gaRunReport(propertyId, token, body) {
  const response = await fetch(`https://analyticsdata.googleapis.com/v1beta/properties/${propertyId}:runReport`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(clean(payload?.error?.message, 400) || "Google Analytics Data API 暫時無法讀取報表。");
    error.code = "analytics_provider_error";
    throw error;
  }
  return payload;
}

const gaMetric = (row, index) => numberValue(row?.metricValues?.[index]?.value);
const gaRows = (report, label = (row) => row?.dimensionValues?.[0]?.value) => (report?.rows || []).map((row) => ({
  label: clean(label(row), 300) || "(未提供)",
  value: gaMetric(row, 0),
})).filter((row) => row.value > 0);

async function googleAnalytics(env, range) {
  const propertyId = clean(env.GOOGLE_ANALYTICS_PROPERTY_ID, 40);
  if (!/^\d{4,30}$/.test(propertyId) || !env.GOOGLE_ANALYTICS_SERVICE_ACCOUNT_JSON) {
    const error = new Error("Google 報表尚未設定：請在 Worker 加入 GA4 Property ID 與唯讀服務帳戶 JSON。");
    error.code = "analytics_not_configured";
    throw error;
  }
  const token = await googleAccessToken(env);
  const dimensions = [null, "date", "pagePath", "sessionSource", "country", "deviceCategory", "browser"];
  let reports;
  try { reports = await Promise.all(dimensions.map((dimension, index) => gaRunReport(propertyId, token, gaRequest(range.days, dimension, index === 1 ? 100 : 12)))); }
  catch (reason) {
    const error = new Error(`Google Analytics 暫時無法讀取報表：${clean(reason?.message, 400)}`);
    error.code = reason?.code || "analytics_provider_error";
    throw error;
  }
  const total = reports[0]?.rows?.[0] || {};
  return normalizedAnalytics("google", range, { views: gaMetric(total, 0), visits: gaMetric(total, 1), users: gaMetric(total, 2) }, {
    trend: (reports[1]?.rows || []).map((row) => {
      const raw = clean(row?.dimensionValues?.[0]?.value, 20);
      return { date: /^\d{8}$/.test(raw) ? `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6)}` : raw, views: gaMetric(row, 0), visits: gaMetric(row, 1), users: gaMetric(row, 2) };
    }).filter((row) => row.date).sort((left, right) => left.date.localeCompare(right.date)),
    top_pages: gaRows(reports[2]),
    referrers: gaRows(reports[3]).map((row) => row.label === "(direct)" ? { ...row, label: "直接進入" } : row),
    countries: gaRows(reports[4]),
    devices: gaRows(reports[5]),
    browsers: gaRows(reports[6]),
  });
}

async function analyticsReport(request, env, origin) {
  const session = await requireSession(request, env);
  if (!session) return json({ success: false, code: "login_required", message: "請重新登入 GitHub" }, 401, origin);
  const url = new URL(request.url);
  const provider = clean(url.searchParams.get("provider"), 20).toLowerCase() === "google" ? "google" : "cloudflare";
  const range = analyticsRange(url);
  const cacheKey = `${provider}:${range.key}:${analyticsHost(env)}:${clean(env.CLOUDFLARE_ACCOUNT_ID, 100)}:${clean(env.GOOGLE_ANALYTICS_PROPERTY_ID, 40)}`;
  const cached = analyticsCache.get(cacheKey);
  const refresh = url.searchParams.get("refresh") === "1";
  if (!refresh && cached?.expires > Date.now()) return json({ ...cached.value, cached: true }, 200, origin);
  try {
    const value = provider === "google" ? await googleAnalytics(env, range) : await cloudflareAnalytics(env, range);
    analyticsCache.set(cacheKey, { value, expires: Date.now() + ANALYTICS_CACHE_SECONDS * 1000 });
    return json(value, 200, origin);
  } catch (reason) {
    const status = reason?.code === "analytics_not_configured" ? 503 : 502;
    return json({ success: false, code: reason?.code || "analytics_provider_error", message: clean(reason?.message, 500) || "暫時無法讀取流量報表" }, status, origin);
  }
}

async function handleCms(request, env, allowedOrigin) {
  const url = new URL(request.url);
  const origin = request.headers.get("origin") || "";
  if (url.pathname === "/cms/auth/start" && request.method === "GET") return oauthStart(request, env);
  if (url.pathname === "/cms/auth/callback" && request.method === "GET") return oauthCallback(request, env);
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(allowedOrigin) });
  if (origin && origin !== allowedOrigin) return json({ success: false, message: "Origin not allowed" }, 403, allowedOrigin);
  if (url.pathname === "/cms/session" && request.method === "GET") {
    const session = await requireSession(request, env);
    return session
      ? json({ success: true, login: session.sub, expires: session.exp }, 200, allowedOrigin)
      : json({ success: false, code: "login_required" }, 401, allowedOrigin);
  }
  if (url.pathname === "/cms/submit" && request.method === "POST") return submitCms(request, env, allowedOrigin);
  if (url.pathname === "/cms/status" && request.method === "GET") return cmsStatus(request, env, allowedOrigin);
  if (url.pathname === "/cms/analytics" && request.method === "GET") return analyticsReport(request, env, allowedOrigin);
  return json({ success: false, message: "Not found" }, 404, allowedOrigin);
}

async function handleContact(request, env, allowedOrigin) {
  const origin = request.headers.get("origin") || "";
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(allowedOrigin) });
  if (request.method !== "POST") return json({ success: false, message: "Method not allowed" }, 405, allowedOrigin);
  if (origin && origin !== allowedOrigin) return json({ success: false, message: "Origin not allowed" }, 403, allowedOrigin);
  let raw;
  try { raw = await parsePayload(request); }
  catch { return json({ success: false, message: "Invalid form payload" }, 400, allowedOrigin); }
  if (raw.botcheck) return json({ success: true }, 200, allowedOrigin);
  const name = clean(raw.name, 160);
  const email = clean(raw.email, 320);
  const visitorSubject = clean(raw.visitor_subject || raw.subject, 240);
  const fixedSubject = clean(env.EMAIL_SUBJECT || raw.email_subject, 240) || "[hctsui.github.io] New contact message";
  const message = clean(raw.message, 8000);
  if (!name || !emailOk(email) || !message) return json({ success: false, message: "Please complete the required fields." }, 400, allowedOrigin);
  const turnstileToken = clean(raw["cf-turnstile-response"], 2048);
  const verified = await verifyTurnstile(env.TURNSTILE_SECRET, turnstileToken, request.headers.get("CF-Connecting-IP") || "");
  if (!verified) return json({ success: false, message: "Human verification failed." }, 400, allowedOrigin);
  if (!env.WEB3FORMS_ACCESS_KEY) return json({ success: false, message: "Contact service is not configured." }, 503, allowedOrigin);
  const privateMail = new FormData();
  privateMail.set("access_key", env.WEB3FORMS_ACCESS_KEY);
  privateMail.set("name", name);
  privateMail.set("email", email);
  privateMail.set("subject", fixedSubject);
  privateMail.set("Visitor subject", visitorSubject || "(none)");
  privateMail.set("message", visitorSubject ? `Visitor subject: ${visitorSubject}\n\n${message}` : message);
  privateMail.set("from_name", "hctsui.github.io contact form");
  const mailResponse = await fetch("https://api.web3forms.com/submit", { method: "POST", body: privateMail, headers: { Accept: "application/json" } });
  const mailResult = await mailResponse.json().catch(() => ({}));
  if (!mailResponse.ok || mailResult.success === false) return json({ success: false, message: "Email delivery failed." }, 502, allowedOrigin);
  if (env.GITHUB_TOKEN) {
    const repository = clean(env.GITHUB_REPOSITORY, 200) || "hctsui/hctsui.github.io";
    const eventId = crypto.randomUUID();
    const dispatch = await fetch(`https://api.github.com/repos/${repository}/dispatches`, {
      method: "POST",
      headers: githubHeaders(env),
      body: JSON.stringify({ event_type: "contact_message", client_payload: { event_id: eventId, received_at: new Date().toISOString() } }),
    });
    if (!dispatch.ok) return json({ success: true, notification: false }, 200, allowedOrigin);
  }
  return json({ success: true, notification: Boolean(env.GITHUB_TOKEN) }, 200, allowedOrigin);
}

export default {
  async fetch(request, env) {
    const allowedOrigin = clean(env.SITE_ORIGIN, 300) || "https://hctsui.github.io";
    const url = new URL(request.url);
    if (url.pathname.startsWith("/cms/")) return handleCms(request, env, allowedOrigin);
    return handleContact(request, env, allowedOrigin);
  },
};
