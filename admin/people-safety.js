'use strict';

/* Legacy compatibility only. Person-link data is now loaded and drafted solely
   by people.js, using the same single-source pattern as the translation table. */
(function removeLegacyPeopleSafetyUi(){
  for(const key of ['hctsui-people-draft-backup-v2','hctsui-people-draft-safety-backup-v1'])localStorage.removeItem(key);
  for(const key of ['hctsui-people-merge-reloaded','hctsui-people-allow-removal-once'])sessionStorage.removeItem(key);
  document.querySelectorAll('[data-people-safety]').forEach(node=>node.remove());
})();
