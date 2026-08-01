/**
 * Privacy-safe contact bridge and authenticated CMS submitter for Cloudflare Workers.
 *
 * Required contact secrets:
 *   WEB3FORMS_ACCESS_KEY, GITHUB_TOKEN
 *
 * Required CMS secrets:
 *   GITHUB_OAUTH_CLIENT_ID, GITHUB_OAUTH_CLIENT_SECRET, CMS_SESSION_SECRET
 *
 * GITHUB_TOKEN must be a fine-grained token owned by the repository owner and
 * limited to this repository. It needs Contents: write for repository_dispatch
 * and Issues: write for CMS batch submission.
 *
 * Optional secrets/vars:
 *   TURNSTILE_SECRET
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

const clean = (value, max) => String(value || "").replace(/[\u0000-\u001f]/g, "").trim().slice(0, max);
const emailOk = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
const nowSeconds = () => Math.floor(Date.now() / 1000);

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
  if (!env.GITHUB_OAUTH_CLIENT_ID || !env.GITHUB_OAUTH_CLIENT_SECRET || !env.CMS_SESSION_SECRET) {
    return adminRedirect(env, { github_error: "GitHub 登入服務尚未設定完成" });
  }
  const url = new URL(request.url);
  const state = randomToken(24);
  const verifier = randomToken(48);
  const challenge = base64UrlEncode(await crypto.subtle.digest("SHA-256", utf8.encode(verifier)));
  const oauthState = await signedToken({ kind: "oauth", state, verifier, exp: nowSeconds() + OAUTH_SECONDS }, env.CMS_SESSION_SECRET);
  const authorize = new URL("https://github.com/login/oauth/authorize");
  authorize.searchParams.set("client_id", env.GITHUB_OAUTH_CLIENT_ID);
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
  if (!env.GITHUB_OAUTH_CLIENT_ID || !env.GITHUB_OAUTH_CLIENT_SECRET || !env.CMS_SESSION_SECRET) {
    return adminRedirect(env, { github_error: "GitHub 登入服務尚未設定完成" });
  }
  const url = new URL(request.url);
  const stored = await verifySignedToken(parseCookies(request).cms_oauth, env.CMS_SESSION_SECRET, "oauth");
  if (!stored || !url.searchParams.get("code") || stored.state !== url.searchParams.get("state")) {
    return adminRedirect(env, { github_error: "登入驗證已過期，請再試一次" });
  }
  const tokenResponse = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json", "user-agent": "hctsui-cms-submit" },
    body: JSON.stringify({
      client_id: env.GITHUB_OAUTH_CLIENT_ID,
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
  const session = await signedToken({ kind: "session", sub: user.login, exp: expires }, env.CMS_SESSION_SECRET);
  return adminRedirect(env, { github_session: session, github_login: user.login, github_expires: String(expires) });
}

async function requireSession(request, env) {
  if (!env.CMS_SESSION_SECRET) return null;
  const header = request.headers.get("authorization") || "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  const session = await verifySignedToken(match?.[1], env.CMS_SESSION_SECRET, "session");
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
