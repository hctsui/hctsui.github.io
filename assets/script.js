document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector(".menu-button");
  const nav = document.querySelector(".site-nav");

  const closeMenu = () => {
    if (!button || !nav) return;
    nav.classList.remove("open");
    button.setAttribute("aria-expanded", "false");
  };

  if (button && nav) {
    button.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      button.setAttribute("aria-expanded", String(open));
    });

    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu();
        button.focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (!nav.contains(event.target) && !button.contains(event.target)) closeMenu();
    });
  }

  const page = document.body.dataset.page;
  const active = document.querySelector(`[data-nav="${page}"]`);
  if (active) {
    active.classList.add("active");
    active.setAttribute("aria-current", "page");
  }

  const year = document.querySelector("#year");
  if (year) year.textContent = new Date().getFullYear();

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
  const toggle = event.target.closest("[data-bibtex-toggle]");
  if (toggle) {
    const panel = document.getElementById(toggle.dataset.bibtexToggle || "");
    if (!panel) return;
    const opening = panel.hidden;
    panel.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
    if (opening) panel.querySelector(".citation-format-tab.active")?.focus({ preventScroll: true });
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
  if (copied) {
    copyButton.textContent = copyButton.dataset.copiedLabel || "Copied";
    setTimeout(() => { copyButton.textContent = original; }, 1800);
  }
});
