const menuButton=document.querySelector('.menu-button');
const nav=document.querySelector('.site-nav');
if(menuButton&&nav){
  menuButton.addEventListener('click',()=>{
    const open=nav.classList.toggle('open');
    menuButton.setAttribute('aria-expanded',String(open));
  });
  nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{
    nav.classList.remove('open');
    menuButton.setAttribute('aria-expanded','false');
  }));
}

const toggle=document.querySelector('.language-toggle');
const enNodes=document.querySelectorAll('[data-en]');
const zhNodes=document.querySelectorAll('[data-zh]');

function applyLanguage(lang){
  const zh=lang==='zh';
  enNodes.forEach(el=>el.hidden=zh);
  zhNodes.forEach(el=>el.hidden=!zh);
  document.documentElement.lang=zh?'zh-Hant':'en';
  if(toggle){
    toggle.textContent=zh?'English':'中文';
    toggle.setAttribute('aria-label',zh?'Switch to English':'切換至中文版');
  }
  localStorage.setItem('site-language',lang);
}
applyLanguage(localStorage.getItem('site-language')||'en');
if(toggle) toggle.addEventListener('click',()=>{
  applyLanguage(document.documentElement.lang==='zh-Hant'?'en':'zh');
});

const year=document.querySelector('#year');
if(year) year.textContent=new Date().getFullYear();
