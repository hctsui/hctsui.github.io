'use strict';

(function installMediaSuggestions(){
  let manifestPromise=null;
  const normalize=value=>String(value||'').normalize('NFKC').toLowerCase().replace(/[^a-z0-9\u3400-\u9fff]+/g,' ').trim();
  const tokens=value=>normalize(value).split(/\s+/).filter(token=>token.length>1);
  const escapeHtml=value=>String(value||'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function loadManifest(){
    if(!manifestPromise)manifestPromise=fetch('../content/media.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();});
    return manifestPromise;
  }
  function kindFor(input){
    if(input.dataset.mediaKind)return input.dataset.mediaKind;
    const path=String(input.dataset.path||input.dataset.footerField||input.dataset.pageField||input.dataset.seoGlobal||'').toLowerCase();
    if(/slides_url|lecture_notes_url/.test(path))return 'slides';
    if(/pdf_url/.test(path))return 'papers';
    if(/image|photo|icon|og_?image|custom_icon|default_image/.test(path))return 'images';
    return '';
  }
  function insertionPath(item,kind){
    if(kind==='images')return item.path;
    return '/'+String(item.path||'').replace(/^\/+/, '');
  }
  function relatedText(input){
    const root=input.closest('#addEditor,#siteSettingsTab,form,.panel')||document;
    const values=[...root.querySelectorAll('input,textarea,select')]
      .filter(field=>field!==input&&field.offsetParent!==null&&field.type!=='password')
      .map(field=>field.value||field.textContent||'').join(' ');
    return normalize(values);
  }
  function score(item,query,context){
    const hay=normalize(`${item.name} ${item.label} ${item.path}`);
    let score=0;
    if(query){
      if(hay===query)score+=120;
      else if(hay.startsWith(query))score+=90;
      else if(hay.includes(query))score+=65;
      for(const token of tokens(query))if(hay.includes(token))score+=18;
    }
    for(const token of tokens(context).slice(0,20))if(hay.includes(token))score+=5;
    return score;
  }
  function ensurePopup(input){
    let popup=input.parentElement?.querySelector(':scope > .media-suggestion-popup');
    if(popup)return popup;
    popup=document.createElement('div');popup.className='media-suggestion-popup';popup.hidden=true;
    input.insertAdjacentElement('afterend',popup);
    return popup;
  }
  async function show(input){
    const kind=kindFor(input);if(!kind)return;
    const popup=ensurePopup(input),query=normalize(input.value),context=relatedText(input);
    try{
      const manifest=await loadManifest(),items=Array.isArray(manifest[kind])?manifest[kind]:[];
      const ranked=items.map(item=>({item,score:score(item,query,context)}))
        .filter(row=>!query||row.score>0)
        .sort((a,b)=>b.score-a.score||a.item.name.localeCompare(b.item.name))
        .slice(0,8);
      if(!ranked.length){popup.hidden=true;popup.innerHTML='';return;}
      popup.innerHTML=`<div class="media-suggestion-title">Repository 檔案建議</div>${ranked.map(({item})=>`<button type="button" data-media-value="${escapeHtml(insertionPath(item,kind))}"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.path)}</span></button>`).join('')}`;
      popup.hidden=false;
    }catch{popup.hidden=true;}
  }
  document.addEventListener('focusin',event=>{const input=event.target.closest('input');if(input&&kindFor(input))show(input);});
  document.addEventListener('input',event=>{const input=event.target.closest('input');if(input&&kindFor(input))show(input);});
  document.addEventListener('click',event=>{
    const choice=event.target.closest('[data-media-value]');
    if(choice){const popup=choice.closest('.media-suggestion-popup'),input=popup?.previousElementSibling;if(input){input.value=choice.dataset.mediaValue;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));input.focus();}if(popup)popup.hidden=true;return;}
    document.querySelectorAll('.media-suggestion-popup').forEach(popup=>{if(!popup.contains(event.target)&&popup.previousElementSibling!==event.target)popup.hidden=true;});
  });
  const style=document.createElement('style');style.textContent=`
    .field:has(.media-suggestion-popup){position:relative}.media-suggestion-popup{position:absolute;left:0;right:0;top:100%;z-index:100;max-height:310px;overflow:auto;margin-top:4px;border:1px solid #cfc4bb;border-radius:11px;background:#fff;box-shadow:0 16px 38px #3d2b2322}.media-suggestion-popup[hidden]{display:none!important}.media-suggestion-title{padding:7px 10px;background:#f5eee8;color:#6e625a;font-size:.72rem;font-weight:850}.media-suggestion-popup button{display:grid;width:100%;gap:2px;padding:9px 10px;border:0;border-top:1px solid #eee6df;background:#fff;color:#2d2926;text-align:left;cursor:pointer}.media-suggestion-popup button:hover,.media-suggestion-popup button:focus{background:#f8f1ec;outline:none}.media-suggestion-popup strong{font-size:.82rem}.media-suggestion-popup span{color:#766c65;font:11px ui-monospace,monospace;overflow-wrap:anywhere}`;
  document.head.append(style);
  window.refreshMediaManifest=()=>{manifestPromise=null;};
})();
