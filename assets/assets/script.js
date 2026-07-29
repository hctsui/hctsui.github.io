const menuButton = document.querySelector('.menu-button');
const nav = document.querySelector('.site-nav');

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

const year = document.querySelector('#year');
if (year) year.textContent = new Date().getFullYear();

const languageToggle = document.querySelector('.language-toggle');
const englishNodes = document.querySelectorAll('[data-en]');
const chineseNodes = document.querySelectorAll('[data-zh]');

function setLanguage(language) {
  const useChinese = language === 'zh';
  document.documentElement.lang = useChinese ? 'zh-Hant' : 'en';
  englishNodes.forEach((node) => { node.hidden = useChinese; });
  chineseNodes.forEach((node) => { node.hidden = !useChinese; });

  if (languageToggle) {
    languageToggle.textContent = useChinese ? 'English' : '中文';
    languageToggle.setAttribute('aria-label', useChinese ? 'Switch to English' : '切換至中文版');
  }

  localStorage.setItem('site-language', useChinese ? 'zh' : 'en');
}

if (languageToggle) {
  languageToggle.addEventListener('click', () => {
    setLanguage(document.documentElement.lang === 'zh-Hant' ? 'en' : 'zh');
  });
}

setLanguage(localStorage.getItem('site-language') || 'en');
