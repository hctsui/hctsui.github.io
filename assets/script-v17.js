document.addEventListener("DOMContentLoaded",()=>{const b=document.querySelector(".menu-button"),n=document.querySelector(".site-nav");if(b&&n){b.addEventListener("click",()=>{const o=n.classList.toggle("open");b.setAttribute("aria-expanded",String(o))});n.querySelectorAll("a").forEach(a=>a.addEventListener("click",()=>{n.classList.remove("open");b.setAttribute("aria-expanded","false")}))}const p=document.body.dataset.page,a=document.querySelector(`[data-nav="${p}"]`);if(a)a.classList.add("active");const y=document.querySelector("#year");if(y)y.textContent=new Date().getFullYear()});

async function loadLatestPublications() {
  const list = document.querySelector('#latest-publications');
  if (!list) return;

  list.classList.add('is-loading');
  const source = list.dataset.source || 'publications.html';
  const limit = Number.parseInt(list.dataset.limit || '2', 10);

  try {
    const response = await fetch(source, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const html = await response.text();
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    const newest = [...parsed.querySelectorAll('article.publication[data-date]')]
      .sort((a, b) => (b.dataset.date || '').localeCompare(a.dataset.date || ''))
      .slice(0, limit);

    if (!newest.length) return;

    list.replaceChildren();
    newest.forEach((article) => {
      const item = document.createElement('li');
      item.append(article.cloneNode(true));
      list.append(item);
    });
  } catch (error) {
    console.warn('Using the fallback selected publications.', error);
  } finally {
    list.classList.remove('is-loading');
  }
}

loadLatestPublications();
