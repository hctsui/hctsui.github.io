# Contact form setup

The website supports two modes under **Admin → Website settings → Contact form**.

## Email-only mode

1. Create a Web3Forms access key.
2. Paste it into the Admin field.
3. Enable the form and submit the website batch.

The browser sends the form directly to Web3Forms. Messages arrive by email and no Admin alert is created.

## Cloudflare Worker bridge

This mode sends the full message privately to Web3Forms and creates an **anonymous** Admin alert. The public repository never stores the visitor's name, email address, subject, or message text.

1. Create a Cloudflare Worker and paste `integrations/contact-worker.js` into it.
2. Add Worker secrets:
   - `WEB3FORMS_ACCESS_KEY`
   - `GITHUB_TOKEN`: a fine-grained GitHub token restricted to `hctsui/hctsui.github.io`, with **Contents: write** only.
   - `TURNSTILE_SECRET` (strongly recommended).
3. Add Worker variables:
   - `SITE_ORIGIN=https://hctsui.github.io`
   - `GITHUB_REPOSITORY=hctsui/hctsui.github.io`
4. Create a Turnstile widget for `hctsui.github.io`; paste its Site Key into Admin.
5. Select Worker mode in Admin and paste the Worker URL.

Never put Worker secrets, GitHub tokens, or the Turnstile secret in `content/site.json`, Admin fields, or source code.
