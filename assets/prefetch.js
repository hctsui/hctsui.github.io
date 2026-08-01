
'use strict';

(() => {
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (connection?.saveData || ['slow-2g', '2g'].includes(connection?.effectiveType)) return;

  const prefetched = new Set();
  let hoverTimer = 0;

  function eligible(anchor) {
    if (!(anchor instanceof HTMLAnchorElement)) return null;
    if (anchor.target && anchor.target !== '_self') return null;
    if (anchor.hasAttribute('download') || anchor.relList.contains('external')) return null;

    let url;
    try {
      url = new URL(anchor.href, location.href);
    } catch {
      return null;
    }

    if (url.origin !== location.origin) return null;
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    if (url.pathname.startsWith('/admin/')) return null;
    if (url.hash && url.pathname === location.pathname && url.search === location.search) return null;
    if (/\.(?:pdf|zip|rar|7z|tar|gz|jpe?g|png|gif|webp|svg|ico|mp4|webm|mp3|wav|docx?|xlsx?|pptx?)$/i.test(url.pathname)) return null;

    url.hash = '';
    if (url.href === location.href.split('#')[0] || prefetched.has(url.href)) return null;
    return url;
  }

  function prefetch(anchor) {
    const url = eligible(anchor);
    if (!url) return;
    prefetched.add(url.href);

    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.as = 'document';
    link.href = url.href;
    link.dataset.instantNavigation = 'true';
    document.head.append(link);
  }

  document.addEventListener('mouseover', (event) => {
    const anchor = event.target.closest?.('a[href]');
    if (!anchor || !eligible(anchor)) return;
    clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(() => prefetch(anchor), 65);
  }, { passive: true });

  document.addEventListener('mouseout', (event) => {
    if (event.target.closest?.('a[href]')) clearTimeout(hoverTimer);
  }, { passive: true });

  document.addEventListener('touchstart', (event) => {
    const anchor = event.target.closest?.('a[href]');
    if (anchor) prefetch(anchor);
  }, { passive: true });
})();
