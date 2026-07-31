/**
 * Privacy-safe contact bridge for Cloudflare Workers.
 *
 * Required secrets:
 *   WEB3FORMS_ACCESS_KEY  - private Web3Forms access key
 *   GITHUB_TOKEN          - fine-grained token limited to this repository,
 *                           Contents: write (needed for repository_dispatch)
 * Optional secrets/vars:
 *   TURNSTILE_SECRET      - strongly recommended
 *   SITE_ORIGIN           - e.g. https://hctsui.github.io
 *   GITHUB_REPOSITORY     - defaults to hctsui/hctsui.github.io
 *   EMAIL_SUBJECT         - fixed notification subject used for every message
 */
const json = (data, status = 200, origin = "*") => new Response(JSON.stringify(data), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type, accept",
    "vary": "Origin",
  },
});

const clean = (value, max) => String(value || "").replace(/[\u0000-\u001f]/g, "").trim().slice(0, max);
const emailOk = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

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

export default {
  async fetch(request, env) {
    const allowedOrigin = clean(env.SITE_ORIGIN, 300) || "https://hctsui.github.io";
    const origin = request.headers.get("origin") || "";
    const corsOrigin = origin === allowedOrigin ? origin : allowedOrigin;
    if (request.method === "OPTIONS") return json({ success: true }, 204, corsOrigin);
    if (request.method !== "POST") return json({ success: false, message: "Method not allowed" }, 405, corsOrigin);
    if (origin && origin !== allowedOrigin) return json({ success: false, message: "Origin not allowed" }, 403, corsOrigin);

    let raw;
    try { raw = await parsePayload(request); }
    catch { return json({ success: false, message: "Invalid form payload" }, 400, corsOrigin); }
    if (raw.botcheck) return json({ success: true }, 200, corsOrigin);

    const name = clean(raw.name, 160);
    const email = clean(raw.email, 320);
    const visitorSubject = clean(raw.visitor_subject || raw.subject, 240);
    const fixedSubject = clean(env.EMAIL_SUBJECT || raw.email_subject, 240) || "[hctsui.github.io] New contact message";
    const message = clean(raw.message, 8000);
    if (!name || !emailOk(email) || !message) return json({ success: false, message: "Please complete the required fields." }, 400, corsOrigin);

    const turnstileToken = clean(raw["cf-turnstile-response"], 2048);
    const verified = await verifyTurnstile(env.TURNSTILE_SECRET, turnstileToken, request.headers.get("CF-Connecting-IP") || "");
    if (!verified) return json({ success: false, message: "Human verification failed." }, 400, corsOrigin);
    if (!env.WEB3FORMS_ACCESS_KEY) return json({ success: false, message: "Contact service is not configured." }, 503, corsOrigin);

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
    if (!mailResponse.ok || mailResult.success === false) return json({ success: false, message: "Email delivery failed." }, 502, corsOrigin);

    // Only an opaque event ID and timestamp enter the public repository.
    if (env.GITHUB_TOKEN) {
      const repository = clean(env.GITHUB_REPOSITORY, 200) || "hctsui/hctsui.github.io";
      const eventId = crypto.randomUUID();
      const dispatch = await fetch(`https://api.github.com/repos/${repository}/dispatches`, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "hctsui-contact-worker",
          "content-type": "application/json",
        },
        body: JSON.stringify({ event_type: "contact_message", client_payload: { event_id: eventId, received_at: new Date().toISOString() } }),
      });
      // Email delivery is the primary operation. A dispatch failure must not expose
      // or resend the private message, but report a partial success to the browser.
      if (!dispatch.ok) return json({ success: true, notification: false }, 200, corsOrigin);
    }
    return json({ success: true, notification: Boolean(env.GITHUB_TOKEN) }, 200, corsOrigin);
  },
};
