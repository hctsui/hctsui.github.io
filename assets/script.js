document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".menu-button").forEach((button) => {
    const navId = button.getAttribute("aria-controls");
    const nav = navId ? document.getElementById(navId) : button.closest(".nav-wrap")?.querySelector(".site-nav");
    if (!nav) return;
    const closeMenu = () => {
      nav.classList.remove("open");
      button.setAttribute("aria-expanded", "false");
    };
    button.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      button.setAttribute("aria-expanded", String(open));
    });
    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && nav.classList.contains("open")) {
        closeMenu();
        button.focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (!nav.contains(event.target) && !button.contains(event.target)) closeMenu();
    });
  });

  const page = document.body.dataset.page;
  document.querySelectorAll(`[data-nav="${CSS.escape(page || "")}"]`).forEach((active) => {
    active.classList.add("active");
    active.setAttribute("aria-current", "page");
  });

  const year = document.querySelector("#year");
  if (year) year.textContent = new Date().getFullYear();

  const indexCache = new Map();
  const normalize = (value) => String(value || "").normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","\'":"&#39;"}[char]));
  const loadIndex = async (url) => {
    if (!indexCache.has(url)) {
      indexCache.set(url, fetch(url, { cache: "no-store" }).then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      }).then((data) => Array.isArray(data.items) ? data.items : []));
    }
    return indexCache.get(url);
  };
  document.querySelectorAll("[data-site-search]").forEach((shell) => {
    const input = shell.querySelector("input[data-search-index]");
    const results = shell.querySelector("[data-search-results]");
    if (!input || !results) return;
    let activeIndex = -1;
    const close = () => { results.hidden = true; results.innerHTML = ""; activeIndex = -1; };
    const move = (delta) => {
      const links = [...results.querySelectorAll("a")];
      if (!links.length) return;
      activeIndex = (activeIndex + delta + links.length) % links.length;
      links.forEach((link, index) => link.classList.toggle("active", index === activeIndex));
      links[activeIndex].scrollIntoView({ block: "nearest" });
    };
    input.addEventListener("input", async () => {
      const query = normalize(input.value);
      if (query.length < 2) return close();
      try {
        const lang = input.dataset.searchLanguage || document.documentElement.lang || "en";
        const items = (await loadIndex(input.dataset.searchIndex)).filter((item) => item.language === lang);
        const matched = items.map((item) => {
          const title = normalize(item.title), description = normalize(item.description);
          let score = 99;
          if (title === query) score = 0;
          else if (title.startsWith(query)) score = 1;
          else if (title.includes(query)) score = 2;
          else if (description.includes(query)) score = 3;
          return { item, score };
        }).filter((row) => row.score < 99).sort((a, b) => a.score - b.score || a.item.title.localeCompare(b.item.title)).slice(0, 8);
        activeIndex = -1;
        if (!matched.length) {
          results.innerHTML = `<div class="site-search-empty">${lang.startsWith("zh") ? "找不到結果" : "No results"}</div>`;
        } else {
          results.innerHTML = matched.map(({ item }) => `<a href="${escapeHtml(item.url)}"><strong>${escapeHtml(item.title)}</strong>${item.description ? `<span>${escapeHtml(item.description)}</span>` : ""}</a>`).join("");
        }
        results.hidden = false;
      } catch {
        results.innerHTML = `<div class="site-search-empty">${document.documentElement.lang.startsWith("zh") ? "搜尋索引暫時無法讀取" : "Search is temporarily unavailable"}</div>`;
        results.hidden = false;
      }
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") { event.preventDefault(); move(1); }
      else if (event.key === "ArrowUp") { event.preventDefault(); move(-1); }
      else if (event.key === "Enter" && activeIndex >= 0) { event.preventDefault(); results.querySelectorAll("a")[activeIndex]?.click(); }
      else if (event.key === "Escape") close();
    });
    document.addEventListener("click", (event) => { if (!shell.contains(event.target)) close(); });
  });

  /* Load MathJax only on pages that actually contain inline TeX delimiters. */
  const text = document.body.textContent || "";
  if (/\$[^$\n]+\$|\\\([^\n]+\\\)/.test(text)) {
    window.MathJax = {
      tex: { inlineMath: [["$", "$"], ["\\(", "\\)"]] },
      svg: { fontCache: "global" },
    };
    const mathJax = document.createElement("script");
    mathJax.defer = true;
    mathJax.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js";
    document.head.append(mathJax);
  }
});

/* Try the original JPEG if a generated WebP image cannot be loaded. */
document.querySelectorAll("img[data-photo-candidates]").forEach((image) => {
  const candidates = image.dataset.photoCandidates.split("|").filter(Boolean);
  let index = Math.max(candidates.indexOf(image.getAttribute("src")), 0);

  image.addEventListener("error", () => {
    index += 1;
    if (index < candidates.length) {
      image.removeAttribute("srcset");
      image.src = candidates[index];
    }
  });
});

/* Publication citation panels, format tabs, and clipboard copy. */
document.addEventListener("click", async (event) => {
  const toggle = event.target.closest("[data-citation-toggle], [data-bibtex-toggle]");
  if (toggle) {
    const panelId = toggle.dataset.citationToggle || toggle.dataset.bibtexToggle || "";
    const panel = document.getElementById(panelId);
    if (!panel) return;
    const opening = panel.hidden;
    document.querySelectorAll(".citation-panel:not([hidden])").forEach((other) => {
      if (other === panel) return;
      other.hidden = true;
      document.querySelector(`[data-citation-toggle="${CSS.escape(other.id)}"], [data-bibtex-toggle="${CSS.escape(other.id)}"]`)?.setAttribute("aria-expanded", "false");
    });
    panel.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
    if (opening) panel.querySelector(".citation-format-tab.active")?.focus({ preventScroll: true });
    return;
  }

  const closeButton = event.target.closest("[data-citation-close]");
  if (closeButton) {
    const panelId = closeButton.dataset.citationClose || "";
    const panel = document.getElementById(panelId);
    if (panel) panel.hidden = true;
    const trigger = document.querySelector(`[data-citation-toggle="${CSS.escape(panelId)}"], [data-bibtex-toggle="${CSS.escape(panelId)}"]`);
    trigger?.setAttribute("aria-expanded", "false");
    trigger?.focus({ preventScroll: true });
    return;
  }

  const formatButton = event.target.closest("[data-citation-format]");
  if (formatButton) {
    const panel = document.getElementById(formatButton.dataset.citationPanel || "");
    if (!panel) return;
    const format = formatButton.dataset.citationFormat || "bibtex";
    panel.querySelectorAll("[data-citation-format]").forEach((button) => {
      const active = button.dataset.citationFormat === format;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    panel.querySelectorAll("[data-citation-view]").forEach((view) => {
      view.hidden = view.dataset.citationView !== format;
    });
    return;
  }

  const copyButton = event.target.closest("[data-copy-citation], [data-copy-bibtex]");
  if (!copyButton) return;
  const targetId = copyButton.dataset.copyCitation || copyButton.dataset.copyBibtex || "";
  const target = document.getElementById(targetId);
  const text = target?.querySelector("code")?.textContent || "";
  if (!text) return;
  const original = copyButton.textContent;
  let copied = false;
  try {
    await navigator.clipboard.writeText(text);
    copied = true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    try { copied = document.execCommand("copy"); } finally { area.remove(); }
  }
  copyButton.textContent = copied ? (copyButton.dataset.copiedLabel || "Copied") : (document.documentElement.lang === "zh" ? "複製失敗；請手動選取" : "Copy failed; select manually");
  if (!copied) target.querySelector("pre")?.focus({ preventScroll: true });
  setTimeout(() => { copyButton.textContent = original; }, copied ? 1800 : 2600);
});

/* Optional Web3Forms / Cloudflare Worker contact form. */
document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-contact-form]");
  if (!form) return;
  event.preventDefault();
  const submit = form.querySelector("[type=submit]");
  const status = form.querySelector(".contact-form-status");
  const original = submit?.textContent || "Send";
  if (submit) { submit.disabled = true; submit.textContent = document.documentElement.lang === "zh" ? "傳送中…" : "Sending…"; }
  if (status) { status.textContent = ""; status.className = "contact-form-status"; }
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { Accept: "application/json" },
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.success === false) throw new Error(result.message || `HTTP ${response.status}`);
    form.reset();
    if (window.turnstile) window.turnstile.reset();
    if (status) { status.textContent = form.dataset.successMessage || (document.documentElement.lang === "zh" ? "訊息已送出。" : "Message sent."); status.className = "contact-form-status success-message"; }
  } catch (error) {
    if (status) { status.textContent = document.documentElement.lang === "zh" ? `傳送失敗：${error.message || error}` : `Could not send: ${error.message || error}`; status.className = "contact-form-status error-message"; }
  } finally {
    if (submit) { submit.disabled = false; submit.textContent = original; }
  }
});
