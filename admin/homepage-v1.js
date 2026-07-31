'use strict';

/* Compatibility loader.
   admin/index.html still references this historical path.  The maintained
   implementation lives in homepage.js; keeping this small loader avoids a
   risky all-at-once rename of the Admin shell. */
(function loadHomepageManager(){
  if(document.querySelector('script[data-homepage-manager]'))return;
  const script=document.createElement('script');
  script.src='homepage.js';
  script.dataset.homepageManager='';
  script.async=false;
  script.onerror=()=>console.error('Could not load admin/homepage.js');
  document.head.append(script);
})();
