document.addEventListener('DOMContentLoaded', () => {
  const menuButton = document.querySelector('.menu-button');
  const nav = document.querySelector('.site-nav');
  const languageToggle = document.querySelector('.language-toggle');

  if (menuButton && nav) {
    menuButton.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('open');
      menuButton.setAttribute('aria-expanded', String(isOpen));
    });
    nav.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        nav.classList.remove('open');
        menuButton.setAttribute('aria-expanded', 'false');
      });
    });
  }

  function readLanguage() {
    try { return localStorage.getItem('hctsui-language') || 'en'; }
    catch (_) { return 'en'; }
  }

  function saveLanguage(language) {
    try { localStorage.setItem('hctsui-language', language); }
    catch (_) {}
  }

  function applyLanguage(language) {
    const useChinese = language === 'zh';
    document.documentElement.lang = useChinese ? 'zh-Hant' : 'en';
    document.querySelectorAll('[data-lang="en"]').forEach((node) => { node.hidden = useChinese; });
    document.querySelectorAll('[data-lang="zh"]').forEach((node) => { node.hidden = !useChinese; });
    if (languageToggle) {
      languageToggle.textContent = useChinese ? 'English' : '中文';
      languageToggle.setAttribute('aria-label', useChinese ? 'Switch to English' : '切換至中文版');
    }
    saveLanguage(language);
  }

  let currentLanguage = readLanguage();
  applyLanguage(currentLanguage);
  if (languageToggle) {
    languageToggle.addEventListener('click', () => {
      currentLanguage = currentLanguage === 'en' ? 'zh' : 'en';
      applyLanguage(currentLanguage);
    });
  }

  const currentPage = document.body.dataset.page;
  const activeLink = document.querySelector(`[data-nav="${currentPage}"]`);
  if (activeLink) activeLink.classList.add('active');

  const year = document.querySelector('#year');
  if (year) year.textContent = new Date().getFullYear();
});
