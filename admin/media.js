
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
    if(choice){
      const popup=choice.closest('.media-suggestion-popup'),input=popup?.previousElementSibling;
      if(input){
        input.value=choice.dataset.mediaValue;
        input.dispatchEvent(new Event('input',{bubbles:true}));
        input.dispatchEvent(new Event('change',{bubbles:true}));
        input.focus();
      }
      if(popup)popup.hidden=true;
      return;
    }
    document.querySelectorAll('.media-suggestion-popup').forEach(popup=>{
      if(!popup.contains(event.target)&&popup.previousElementSibling!==event.target)popup.hidden=true;
    });
  });
  const style=document.createElement('style');style.textContent=`
    .field:has(.media-suggestion-popup){position:relative}
    .media-suggestion-popup{position:absolute;left:0;right:0;top:100%;z-index:100;max-height:310px;overflow:auto;margin-top:4px;border:1px solid #cfc4bb;border-radius:11px;background:#fff;box-shadow:0 16px 38px #3d2b2322}
    .media-suggestion-popup[hidden]{display:none!important}
    .media-suggestion-title{padding:7px 10px;background:#f5eee8;color:#6e625a;font-size:.72rem;font-weight:850}
    .media-suggestion-popup button{display:grid;width:100%;gap:2px;padding:9px 10px;border:0;border-top:1px solid #eee6df;background:#fff;color:#2d2926;text-align:left;cursor:pointer}
    .media-suggestion-popup button:hover,.media-suggestion-popup button:focus{background:#f8f1ec;outline:none}
    .media-suggestion-popup strong{font-size:.82rem}
    .media-suggestion-popup span{color:#766c65;font:11px ui-monospace,monospace;overflow-wrap:anywhere}`;
  document.head.append(style);
  window.refreshMediaManifest=()=>{manifestPromise=null;};
})();

(function installCmsCompatibilityFixes(){
  const DOSSIER_PAGE={
    id:'dossier',
    name:{en:'Dossier',zh:'審查資料'},
    path:{en:'dossier.html',zh:'zh/dossier.html'},
    header:{
      label:{en:'Academic dossier',zh:'審查資料'},
      title:{en:'Academic Dossier',zh:'學術審查資料'},
      intro:{
        en:'A concise overview of research, publications, talks, teaching, and academic background.',
        zh:'彙整研究、論文、報告、教學與學術背景的審查資料。'
      }
    },
    color:'#5b5876',
    show_in_navigation:false,
    order:99,
    languages:['en','zh']
  };
  const PEOPLE_KEY='hctsui-people-draft';
  const PEOPLE_BACKUP_KEY='hctsui-people-draft-backup-v2';
  const savedPeopleDraft=localStorage.getItem(PEOPLE_KEY);
  if(savedPeopleDraft)localStorage.setItem(PEOPLE_BACKUP_KEY,savedPeopleDraft);

  function ensureDossierPage(data){
    if(!data||typeof data!=='object')return data;
    data.settings=data.settings||{};
    const pages=Array.isArray(data.settings.pages)?data.settings.pages:(data.settings.pages=[]);
    if(!pages.some(page=>page?.id==='dossier')){
      const next=structuredClone(DOSSIER_PAGE);
      next.order=pages.length;
      pages.push(next);
    }
    return data;
  }

  const nativeFetch=window.fetch.bind(window);
  window.fetch=async function(input,init){
    const response=await nativeFetch(input,init);
    const url=typeof input==='string'?input:input?.url||'';
    if(!/\/content\/site\.json(?:[?#]|$)/.test(url)||!response.ok)return response;
    try{
      const data=ensureDossierPage(await response.clone().json());
      return new Response(JSON.stringify(data),{
        status:response.status,
        statusText:response.statusText,
        headers:response.headers
      });
    }catch{return response;}
  };

  if(typeof initLayoutState==='function'){
    const baseInitLayoutState=initLayoutState;
    initLayoutState=function(){
      if(typeof site!=='undefined'&&site)ensureDossierPage(site);
      return baseInitLayoutState.apply(this,arguments);
    };
    window.initLayoutState=initLayoutState;
  }

  const baseRenderAll=window.renderAll;
  if(typeof baseRenderAll==='function'){
    window.renderAll=function(){
      if(typeof site!=='undefined'&&site)ensureDossierPage(site);
      return baseRenderAll.apply(this,arguments);
    };
  }

  function safeInternalPath(value){
    const text=String(value||'').trim();
    return /^\/(?!\/)/.test(text)&&!/\s|\\|\.\.(?:\/|$)/.test(text);
  }

  const baseValidate=window.validateEditorObject;
  if(typeof baseValidate==='function'){
    window.validateEditorObject=function(type,object){
      const errors=baseValidate(type,object);
      const allowed=new Set();
      for(const [key,value] of Object.entries(object||{})){
        if((key==='url'||key.endsWith('_url'))&&safeInternalPath(value)){
          allowed.add(`${key} 不是有效網址`);
          allowed.add(`${key} 只允許 http 或 https`);
        }
      }
      return errors.filter(error=>!allowed.has(error));
    };
  }

  const baseRenderDrafts=window.renderDrafts;
  if(typeof baseRenderDrafts==='function'){
    window.renderDrafts=function(){
      baseRenderDrafts.apply(this,arguments);
      if(typeof peopleDirty!=='function'||!peopleDirty())return;
      const box=document.querySelector('#drafts');
      if(!box||box.querySelector('[data-people-main-draft]'))return;
      const empty=box.querySelector('.muted:only-child');
      if(empty&&/尚無草稿/.test(empty.textContent||''))empty.remove();
      box.insertAdjacentHTML('beforeend',`
        <div class="row draft-row" data-people-main-draft>
          <span class="tag">人名連結</span>
          <strong>人名連結資料</strong>
          <span class="muted">姓名、別名與學術網頁；會和其他草稿一起送出。</span>
          <div class="actions">
            <button class="button" data-edit-people-main-draft>修改草稿</button>
            <button class="button" data-preview-people-main-draft>預覽</button>
            <button class="button danger" data-drop-people-main-draft>移除</button>
          </div>
        </div>`);
    };
  }

  document.querySelector('#drafts')?.addEventListener('click',event=>{
    const button=event.target.closest('button');
    if(!button)return;
    if(button.hasAttribute('data-edit-people-main-draft')){
      if(typeof switchTab==='function')switchTab('dictionary');
      document.querySelector('[data-database-type="people"]')?.click();
      document.querySelector('#peopleDatabasePane')?.scrollIntoView({behavior:'smooth',block:'start'});
      return;
    }
    if(button.hasAttribute('data-preview-people-main-draft')){
      const op=typeof peopleOperation==='function'?peopleOperation():null;
      if(op&&typeof peoplePreviewHtml==='function'){
        document.querySelector('#editorPreview').innerHTML=
          '<div class="notice"><strong>草稿預覽 · 人名連結</strong></div>'+peoplePreviewHtml(op);
      }
      return;
    }
    if(button.hasAttribute('data-drop-people-main-draft')){
      if(confirm('放棄尚未送出的人名連結修改？')&&typeof clearPeopleDraft==='function'){
        clearPeopleDraft(true);
        if(typeof renderPreview==='function')renderPreview(false);
      }
    }
  });

  function rowMap(data){
    return new Map((data?.people||[]).filter(Boolean).map(row=>[String(row.id||''),row]));
  }
  function stable(value){return JSON.stringify(value);}
  function mergePeople(base,data,remote){
    const before=rowMap(base),local=rowMap(data),latest=rowMap(remote);
    const result=new Map();
    const conflicts=[];
    for(const id of new Set([...before.keys(),...local.keys(),...latest.keys()])){
      const b=before.get(id),l=local.get(id),r=latest.get(id);
      const localChanged=stable(l)!==stable(b);
      const remoteChanged=stable(r)!==stable(b);
      if(localChanged&&remoteChanged&&stable(l)!==stable(r)){
        if(!b&&l&&r)result.set(id,{...r,...l,name:{...(r.name||{}),...(l.name||{})}});
        else conflicts.push(id);
      }else if(localChanged){
        if(l)result.set(id,l);
      }else if(r)result.set(id,r);
    }
    return {data:{schema_version:1,people:[...result.values()]},conflicts};
  }

  setTimeout(async()=>{
    let saved;
    try{saved=JSON.parse(localStorage.getItem(PEOPLE_BACKUP_KEY)||'null');}catch{return;}
    if(!saved?.base||!saved?.data)return;
    try{
      const remote=await nativeFetch('../content/people.json',{cache:'no-store'}).then(r=>r.json());
      if(stable(saved.base)===stable(remote))return;
      const merged=mergePeople(saved.base,saved.data,remote);
      if(merged.conflicts.length){
        if(typeof flash==='function')flash('人名資料已更新；舊草稿已保留備份，部分同一筆資料需要人工確認。');
        return;
      }
      const next=JSON.stringify({base:remote,data:merged.data});
      if(localStorage.getItem(PEOPLE_KEY)!==next){
        localStorage.setItem(PEOPLE_KEY,next);
        if(!sessionStorage.getItem('hctsui-people-merge-reloaded')){
          sessionStorage.setItem('hctsui-people-merge-reloaded','1');
          location.reload();
        }
      }
    }catch{}
  },500);
})();
