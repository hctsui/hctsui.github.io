'use strict';

/* Authenticated Cloudflare R2 storage manager integrated into Website Settings. */
(function installR2StorageManager(){
  if(window.__hctsuiR2StorageInstalled)return;
  window.__hctsuiR2StorageInstalled=true;

  const SESSION_KEY='hctsui-github-submit-session-v1';
  const DEFAULT_WORKER='https://hctsui-website-worker.hctsui-math.workers.dev';
  const MAX_UPLOAD_BYTES=100*1024*1024;
  const MAX_IMAGE_SOURCE=25*1024*1024;
  let configPromise=null;
  let libraryPromise=null;
  let currentInput=null;
  let r2Active=false;
  let nativePaneState=null;
  let nativeSection='general';
  const POPUP_SAFE_GAP=18;
  const POPUP_MAX_HEIGHT=310;
  const POPUP_ITEM_HEIGHT=52;
  const POPUP_HEADER_HEIGHT=38;
  const POPUP_MATCH_LIMIT=5;
  const POPUP_FOLDER_LIMIT=8;

  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);
  const normalize=value=>String(value||'').normalize('NFKC').toLowerCase().replace(/[^a-z0-9\u3400-\u9fff]+/g,' ').trim();
  const session=()=>{try{return JSON.parse(localStorage.getItem(SESSION_KEY)||'null')}catch{return null}};
  const humanSize=value=>{
    let size=Number(value)||0,index=0;const units=['B','KB','MB','GB'];
    while(size>=1024&&index<units.length-1){size/=1024;index+=1;}
    return `${size>=10||index===0?size.toFixed(0):size.toFixed(1)} ${units[index]}`;
  };
  const safePrefix=value=>String(value||'').normalize('NFKC').split('/').map(part=>part.trim().toLowerCase().replace(/[^a-z0-9._-]+/g,'-').replace(/^[-.]+|[-.]+$/g,'')).filter(Boolean).join('/').slice(0,300);

  async function config(){
    if(configPromise)return configPromise;
    configPromise=(async()=>{
      let file={};
      try{const response=await fetch('../content/media-config.json',{cache:'no-store'});if(response.ok)file=await response.json();}catch{}
      const configured=String(window.site?.settings?.contact_form?.worker_url||file.worker_origin||DEFAULT_WORKER).trim();
      let origin=DEFAULT_WORKER;
      try{origin=new URL(configured).origin}catch{}
      return {
        ...file,
        bucket_name:String(file.bucket_name||'hctsui-website-media'),
        worker_origin:origin,
        public_base:String(file.public_base||`${origin}/media`).replace(/\/$/,'')
      };
    })();
    return configPromise;
  }

  async function api(path,options={}){
    const saved=session();
    if(!saved?.token)throw new Error('請先在 Admin 登入 GitHub');
    const cfg=await config();
    const headers=new Headers(options.headers||{});
    headers.set('authorization',`Bearer ${saved.token}`);
    const response=await fetch(`${cfg.worker_origin}${path}`,{...options,headers});
    const result=await response.json().catch(()=>({}));
    if(response.status===401)throw new Error('GitHub 登入已過期，請重新登入');
    if(!response.ok||result.success===false)throw new Error(result.message||`R2 服務錯誤（${response.status}）`);
    return result;
  }

  function normalizeLibrary(payload){
    const items=(Array.isArray(payload?.items)?payload.items:[]).filter(item=>item?.key&&!String(item.key).endsWith('/.keep')).map(item=>{
      const key=String(item.key),folder=String(item.folder||key.split('/')[0]||'other');
      return {...item,key,folder,name:item.name||key.split('/').pop()||key};
    });
    items.sort((a,b)=>a.key.localeCompare(b.key));
    const groups={};
    for(const item of items)(groups[item.folder]||(groups[item.folder]=[])).push(item);
    const folders=[...new Set([...(payload?.folders||[]),...Object.keys(groups)])].filter(Boolean).sort();
    return {schema_version:payload?.schema_version||2,bucket:payload?.bucket||'',items,groups,folders};
  }

  async function loadLibrary(force=false){
    if(force)libraryPromise=null;
    if(!libraryPromise)libraryPromise=api('/cms/media').then(normalizeLibrary).catch(reason=>{libraryPromise=null;throw reason;});
    return libraryPromise;
  }

  function preferredFolder(input){
    if(!input)return'';
    if(input.dataset.mediaKind)return safePrefix(input.dataset.mediaKind).split('/')[0];
    const raw=String(input.dataset.path||input.dataset.footerField||input.dataset.pageField||input.dataset.seoGlobal||input.name||input.id||'').toLowerCase();
    if(/lecture[_-]?notes?_url|handout_url|course[_-]?notes?_url/.test(raw))return'lecturenotes';
    if(/slides?_url|presentation_url|poster_url/.test(raw))return'slides';
    if(/pdf_url|paper_url|manuscript_url|preprint_url/.test(raw))return'papers';
    if(/image|photo|icon|og_?image|thumbnail/.test(raw))return'images';
    if(/(?:attachment|supplement|document|file|recording)_url/.test(raw))return'files';
    return'';
  }

  function queryParts(value){
    const raw=String(value||'').trim();
    if(!raw)return[];
    const values=[raw];
    try{
      const url=new URL(raw);
      values.push(decodeURIComponent(url.pathname));
      values.push(decodeURIComponent(url.pathname.split('/').pop()||''));
    }catch{}
    return [...new Set(values.flatMap(value=>normalize(value).split(/\s+/)).filter(Boolean))];
  }

  function score(item,query,folder){
    const hay=normalize(`${item.name} ${item.key} ${item.folder} ${item.url||''}`);
    const tokens=queryParts(query);
    let value=item.folder===folder?90:0;
    if(!tokens.length)return value;
    const normalizedQuery=normalize(query);
    if(hay===normalizedQuery)value+=420;
    else if(hay.startsWith(normalizedQuery))value+=280;
    else if(normalizedQuery&&hay.includes(normalizedQuery))value+=190;
    for(const token of tokens){
      if(normalize(item.name)===token)value+=180;
      else if(normalize(item.name).startsWith(token))value+=110;
      else if(hay.includes(token))value+=32;
    }
    return value;
  }

  function popupAnchor(popup){
    const sibling=popup?.previousElementSibling;
    if(sibling instanceof HTMLElement)return sibling;
    return popup?.closest('.field')?.querySelector('input,textarea,button')||null;
  }

  function fitPopup(popup,anchor=popupAnchor(popup)){
    if(!popup||popup.hidden||!(anchor instanceof HTMLElement))return;
    popup.classList.remove('opens-upward');
    popup.style.top='100%';
    popup.style.bottom='auto';
    popup.style.marginTop='4px';
    popup.style.marginBottom='0';
    const rect=anchor.getBoundingClientRect();
    const below=Math.max(0,window.innerHeight-rect.bottom-POPUP_SAFE_GAP);
    const above=Math.max(0,rect.top-POPUP_SAFE_GAP);
    const twoItems=POPUP_HEADER_HEIGHT+POPUP_ITEM_HEIGHT*2;
    const openUpward=below<twoItems&&above>below;
    const available=Math.max(36,Math.floor(openUpward?above:below));
    popup.style.maxHeight=`${Math.min(POPUP_MAX_HEIGHT,available)}px`;
    if(openUpward){
      popup.classList.add('opens-upward');
      popup.style.top='auto';
      popup.style.bottom='100%';
      popup.style.marginTop='0';
      popup.style.marginBottom='4px';
    }
  }

  function refitVisiblePopups(){
    document.querySelectorAll('.r2-media-suggestion-popup:not([hidden]),.media-suggestion-popup:not([hidden]),.suggestion-popup:not([hidden]),.autocomplete-popup:not([hidden]),[role="listbox"]:not([hidden])').forEach(popup=>fitPopup(popup));
  }

  function ensureSuggestion(input){
    let popup=input.parentElement?.querySelector(':scope > .r2-media-suggestion-popup');
    if(popup)return popup;
    popup=document.createElement('div');
    popup.className='r2-media-suggestion-popup';
    popup.hidden=true;
    input.insertAdjacentElement('afterend',popup);
    return popup;
  }

  function suggestionHeader(label,extra=''){
    return `<div class="r2-media-suggestion-title"><span>${esc(label)}</span><span class="r2-media-suggestion-actions">${extra}<button type="button" data-r2-open-settings>管理／上傳</button></span></div>`;
  }

  function folderSuggestionRows(library,preferred){
    const folders=[...library.folders].sort((a,b)=>(a===preferred?-1:b===preferred?1:a.localeCompare(b))).slice(0,POPUP_FOLDER_LIMIT);
    return folders.map(folder=>`<button type="button" class="r2-media-choice r2-folder-choice" data-r2-folder-choice="${esc(folder)}"><strong>${esc(folder)}/</strong><span>${library.groups[folder]?.length||0} 個檔案</span></button>`).join('');
  }

  function fileSuggestionRows(items){
    return items.map(item=>`<button type="button" class="r2-media-choice" data-r2-media-url="${esc(item.url)}"><strong>${esc(item.name)}</strong><span>${esc(item.folder)} · ${humanSize(item.size)}</span></button>`).join('');
  }

  function renderSuggestions(popup,input,library){
    const preferred=preferredFolder(input).trim();
    const query=String(input.value||'').trim();
    const selectedFolder=String(popup.dataset.r2Folder||'');
    if(!query&&!selectedFolder){
      const rows=folderSuggestionRows(library,preferred);
      popup.innerHTML=suggestionHeader('選擇資料夾')+(rows||'<p>目前沒有資料夾</p>');
    }else{
      const source=selectedFolder&&!query?(library.groups[selectedFolder]||[]):library.items;
      const ranked=source.map(item=>({item,score:score(item,query,preferred)}))
        .filter(row=>!query||row.score>0)
        .sort((a,b)=>b.score-a.score||a.item.name.localeCompare(b.item.name))
        .slice(0,POPUP_MATCH_LIMIT).map(row=>row.item);
      const label=selectedFolder&&!query?`${selectedFolder}/`:'最符合目前輸入';
      const back=selectedFolder&&!query?'<button type="button" data-r2-folder-back>資料夾</button>':'';
      popup.innerHTML=suggestionHeader(label,back)+(fileSuggestionRows(ranked)||'<p>沒有符合的檔案</p>');
    }
    popup.hidden=false;
    requestAnimationFrame(()=>fitPopup(popup,input));
  }

  async function showSuggestions(input,{resetFolder=false}={}){
    if(!input||input.type==='password'||input.closest('#r2SettingsPane'))return;
    const folder=preferredFolder(input).trim();
    if(!folder)return;
    const popup=ensureSuggestion(input);
    if(resetFolder)delete popup.dataset.r2Folder;
    try{
      renderSuggestions(popup,input,await loadLibrary());
    }catch(reason){
      popup.innerHTML=suggestionHeader(reason.message||'R2 讀取失敗');
      popup.hidden=false;
      requestAnimationFrame(()=>fitPopup(popup,input));
    }
  }

  function settingsPaneHtml(){
    return `<div class="settings-intro"><strong>R2 儲存桶</strong><span>直接管理 Cloudflare R2 的檔案。</span></div>
      <div class="site-settings-card r2-settings-card">
        <div class="r2-settings-head"><div><h3>檔案管理</h3><p data-r2-bucket-label>Bucket：hctsui-website-media</p></div><button class="button" type="button" data-r2-refresh>重新整理</button></div>
        <div class="r2-media-toolbar"><input type="search" data-r2-search placeholder="搜尋檔名、路徑或資料夾"><select data-r2-folder-filter><option value="">所有資料夾</option></select></div>
      </div>
      <div class="site-settings-card r2-settings-card">
        <h3>上傳檔案</h3>
        <div class="r2-media-upload-grid"><label>R2 資料夾<input data-r2-upload-folder value="papers" placeholder="例如 papers、slides、lecturenotes"></label><label>選擇檔案<input data-r2-upload-files type="file" multiple></label><button class="button primary" type="button" data-r2-upload>上傳</button></div>
        <p class="field-hint">可輸入不存在的新資料夾名稱；第一次上傳時就會建立。也可使用巢狀路徑，例如 <code>lecturenotes/algebra</code>。單檔上限 100 MB。</p>
      </div>
      <div class="site-settings-card r2-settings-card">
        <h3>首頁封面照片</h3>
        <div class="r2-media-upload-grid photo"><label>選擇照片<input data-r2-home-photo type="file" accept="image/jpeg,image/png,image/webp"></label><button class="button primary" type="button" data-r2-upload-photo>產生尺寸並上傳</button></div>
        <p class="field-hint">接受 25 MB 以下 JPEG、PNG、WebP。會在 images/ 產生 photo-original.webp、photo-640.webp、photo-960.webp、photo-1440.webp，並自動建立封面與 OG 圖片的網站設定草稿。</p>
      </div>
      <div class="notice" data-r2-status hidden></div>
      <div class="r2-media-list" data-r2-list></div>`;
  }

  function topLevelSettingsTabs(panel){
    const rows=[...panel.querySelectorAll('.site-settings-tabs')];
    return rows.find(row=>[...row.children].some(child=>child.matches?.('[data-site-settings-section]')))||null;
  }

  function cleanupR2Mounts(panel,tabs){
    let button=null;
    for(const node of document.querySelectorAll('[data-r2-settings-section]')){
      if(!button&&node.parentElement===tabs&&node.closest('#siteSettingsTab')===panel)button=node;
      else node.remove();
    }
    let pane=null;
    for(const node of document.querySelectorAll('[id="r2SettingsPane"],[data-r2-settings-pane]')){
      if(!pane&&node.closest('#siteSettingsTab')===panel)pane=node;
      else node.remove();
    }
    return {button,pane};
  }

  function installSettingsPane(){
    const panel=document.querySelector('#siteSettingsTab');
    if(!panel)return false;
    const tabs=topLevelSettingsTabs(panel);
    if(!tabs)return false;
    let {button,pane}=cleanupR2Mounts(panel,tabs);
    if(!button){
      button=document.createElement('button');
      button.className='button';
      button.type='button';
      button.dataset.r2SettingsSection='';
      button.textContent='R2 儲存桶';
      tabs.append(button);
    }
    if(!pane){
      pane=document.createElement('div');
      pane.id='r2SettingsPane';
      pane.dataset.r2SettingsPane='';
      pane.hidden=true;
      pane.innerHTML=settingsPaneHtml();
    }
    if(pane.parentElement!==panel)panel.append(pane);
    return true;
  }

  const nativePaneIds=['generalSettingsPane','contactFormSettingsPane','seoSettingsPane','analyticsSettingsPane'];
  const sectionPaneIds={general:'generalSettingsPane',contactForm:'contactFormSettingsPane',seo:'seoSettingsPane',analytics:'analyticsSettingsPane'};

  function rememberNativeVisualState(){
    const panel=document.querySelector('#siteSettingsTab'),tabs=panel&&topLevelSettingsTabs(panel);
    if(!panel||!tabs)return;
    const active=tabs.querySelector(':scope > [data-site-settings-section].active');
    if(active?.dataset.siteSettingsSection)nativeSection=active.dataset.siteSettingsSection;
    nativePaneState=Object.fromEntries(nativePaneIds.map(id=>{
      const node=panel.querySelector(`#${id}`);
      return [id,node?Boolean(node.hidden):null];
    }));
  }

  function restoreNativeVisualState(){
    const panel=document.querySelector('#siteSettingsTab'),tabs=panel&&topLevelSettingsTabs(panel);
    if(!panel||!tabs)return;
    for(const id of nativePaneIds){
      const node=panel.querySelector(`#${id}`);
      if(!node)continue;
      const remembered=nativePaneState?.[id];
      node.hidden=remembered===null||remembered===undefined?id!==sectionPaneIds[nativeSection]:remembered;
    }
    [...tabs.children].filter(button=>button.matches?.('[data-site-settings-section]')).forEach(button=>{
      button.classList.toggle('active',button.dataset.siteSettingsSection===nativeSection);
    });
  }

  function setR2VisualState(){
    const panel=document.querySelector('#siteSettingsTab'),tabs=panel&&topLevelSettingsTabs(panel),pane=panel?.querySelector(':scope > #r2SettingsPane');
    if(!panel||!tabs||!pane)return;
    [...tabs.children].filter(button=>button.matches?.('[data-site-settings-section]')).forEach(button=>button.classList.remove('active'));
    tabs.querySelector(':scope > [data-r2-settings-section]')?.classList.toggle('active',r2Active);
    for(const id of nativePaneIds){
      const node=panel.querySelector(`#${id}`);if(node&&r2Active)node.hidden=true;
    }
    pane.hidden=!r2Active;
  }

  async function activateR2(input=null,force=false){
    currentInput=input;
    const outerTab=document.querySelector('[data-tab="siteSettings"]');
    if(outerTab&&!outerTab.classList.contains('active'))outerTab.click();
    installSettingsPane();
    if(!r2Active)rememberNativeVisualState();
    r2Active=true;
    setR2VisualState();
    await renderLibrary(force).catch(reason=>setStatus(reason.message,'error'));
    setR2VisualState();
  }

  function deactivateR2({restore=true}={}){
    const wasActive=r2Active;
    r2Active=false;
    currentInput=null;
    const pane=document.querySelector('#siteSettingsTab > #r2SettingsPane');if(pane)pane.hidden=true;
    document.querySelector('[data-r2-settings-section]')?.classList.remove('active');
    if(wasActive&&restore)restoreNativeVisualState();
  }

  function setStatus(message,kind=''){
    const node=document.querySelector('#siteSettingsTab > #r2SettingsPane [data-r2-status]');
    if(!node)return;
    node.hidden=!message;
    node.className=`notice ${kind}`.trim();
    node.textContent=message||'';
  }

  async function renderLibrary(force=false){
    if(!installSettingsPane())return;
    const pane=document.querySelector('#siteSettingsTab > #r2SettingsPane'),library=await loadLibrary(force),filter=pane.querySelector('[data-r2-folder-filter]');
    const previous=filter.value;
    filter.innerHTML='<option value="">所有資料夾</option>'+library.folders.map(folder=>`<option value="${esc(folder)}">${esc(folder)} (${library.groups[folder]?.length||0})</option>`).join('');
    if(library.folders.includes(previous))filter.value=previous;
    const cfg=await config();
    pane.querySelector('[data-r2-bucket-label]').textContent=`Bucket：${library.bucket||cfg.bucket_name}`;
    const query=normalize(pane.querySelector('[data-r2-search]').value),folder=filter.value;
    const rows=library.items.filter(item=>(!folder||item.folder===folder)&&(!query||normalize(`${item.name} ${item.key} ${item.url||''}`).includes(query)));
    pane.querySelector('[data-r2-list]').innerHTML=rows.map(item=>`<article class="r2-media-row">
      <div><strong>${esc(item.name)}</strong><span>${esc(item.key)} · ${humanSize(item.size)}</span></div>
      <div class="actions">${currentInput?`<button class="button primary" type="button" data-r2-use="${esc(item.url)}">使用</button>`:''}<button class="button" type="button" data-r2-copy="${esc(item.url)}">複製網址</button><a class="button" href="${esc(item.url)}" target="_blank" rel="noopener">開啟</a><button class="button danger" type="button" data-r2-delete="${esc(item.key)}">刪除</button></div>
    </article>`).join('')||'<p class="muted">這個篩選條件下沒有檔案。</p>';
    setStatus('');
  }

  function useUrl(url,input=currentInput,{keepR2=r2Active}={}){
    if(!input||!url)return;
    input.value=url;
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    if(!keepR2&&input.offsetParent!==null)input.focus();
    currentInput=null;
    if(keepR2){
      setR2VisualState();
      if(typeof window.flash==='function')window.flash('已把 R2 網址填入原欄位');
    }
  }

  async function uploadFile(file,prefix,key=''){
    if(file.size>MAX_UPLOAD_BYTES)throw new Error(`${file.name} 超過 100 MB`);
    const path=key||`${safePrefix(prefix)}/${file.name}`.replace(/^\/+/, '');
    if(!path||path.startsWith('/'))throw new Error('資料夾或檔名不正確');
    return api(`/cms/media?key=${encodeURIComponent(path)}`,{
      method:'PUT',
      headers:{'content-type':file.type||'application/octet-stream','x-media-size':String(file.size)},
      body:file
    });
  }

  async function uploadGeneral(){
    const pane=document.querySelector('#siteSettingsTab > #r2SettingsPane'),prefix=safePrefix(pane.querySelector('[data-r2-upload-folder]').value),files=[...pane.querySelector('[data-r2-upload-files]').files];
    if(!prefix)return setStatus('請輸入有效的資料夾名稱','error');
    if(!files.length)return setStatus('請先選擇檔案','error');
    try{
      const library=await loadLibrary(),known=new Set(library.items.map(item=>item.key));
      const overwrites=files.map(file=>`${prefix}/${file.name}`).filter(key=>known.has(key));
      if(overwrites.length&&!confirm(`下列檔案已存在，繼續會覆蓋：\n${overwrites.join('\n')}`))return;
      for(let index=0;index<files.length;index++){
        setStatus(`正在上傳 ${index+1}/${files.length}：${files[index].name}`);
        await uploadFile(files[index],prefix);
      }
      pane.querySelector('[data-r2-upload-files]').value='';
      setStatus(`已上傳 ${files.length} 個檔案`,'success');
      await renderLibrary(true);
    }catch(reason){setStatus(reason.message,'error');}
  }

  async function imageBitmap(file){
    if('createImageBitmap'in window)return createImageBitmap(file);
    return new Promise((resolve,reject)=>{const image=new Image(),url=URL.createObjectURL(file);image.onload=()=>{URL.revokeObjectURL(url);resolve(image)};image.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('瀏覽器無法讀取這張照片'))};image.src=url;});
  }

  function canvasBlob(canvas,type='image/webp',quality=.86){
    return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('照片轉換失敗')),type,quality));
  }

  async function resizedWebp(source,width,name){
    const naturalWidth=source.width||source.naturalWidth,naturalHeight=source.height||source.naturalHeight;
    const targetWidth=Math.min(width,naturalWidth),targetHeight=Math.max(1,Math.round(naturalHeight*targetWidth/naturalWidth));
    const canvas=document.createElement('canvas');canvas.width=targetWidth;canvas.height=targetHeight;
    canvas.getContext('2d',{alpha:false}).drawImage(source,0,0,targetWidth,targetHeight);
    return new File([await canvasBlob(canvas)],name,{type:'image/webp'});
  }

  function updateSiteSettingsField(selector,value){
    const input=document.querySelector(selector);
    if(!input)return false;
    input.value=value;
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
    return true;
  }

  async function applyHomePhotoSettings(urls){
    const keepR2=r2Active;
    if(typeof window.openSiteSettingsSection==='function')window.openSiteSettingsSection('general','cover');
    await new Promise(resolve=>setTimeout(resolve,0));
    updateSiteSettingsField('[data-general-field="cover.image"]',urls.medium);
    updateSiteSettingsField('[data-general-field="cover.fallback"]',urls.original);
    updateSiteSettingsField('[data-seo-global="default_image"]',urls.large);
    if(keepR2){
      r2Active=true;
      installSettingsPane();
      setR2VisualState();
    }
    if(typeof window.flash==='function')window.flash('封面照片已上傳，並建立網站設定草稿');
  }

  async function uploadHomePhoto(){
    const pane=document.querySelector('#siteSettingsTab > #r2SettingsPane'),file=pane.querySelector('[data-r2-home-photo]').files[0];
    if(!file)return setStatus('請先選擇封面照片','error');
    if(!/^image\/(jpeg|png|webp)$/i.test(file.type)||file.size>MAX_IMAGE_SOURCE)return setStatus('只接受 25 MB 以下的 JPEG、PNG 或 WebP','error');
    let source;
    try{
      setStatus('正在產生首頁照片尺寸…');
      source=await imageBitmap(file);
      const naturalWidth=source.width||source.naturalWidth||1440;
      const outputs=[
        await resizedWebp(source,Math.min(2400,naturalWidth),'photo-original.webp'),
        await resizedWebp(source,640,'photo-640.webp'),
        await resizedWebp(source,960,'photo-960.webp'),
        await resizedWebp(source,1440,'photo-1440.webp')
      ];
      if(typeof source.close==='function')source.close();source=null;
      for(let index=0;index<outputs.length;index++){
        setStatus(`正在上傳封面照片 ${index+1}/${outputs.length}…`);
        await uploadFile(outputs[index],'images',`images/${outputs[index].name}`);
      }
      pane.querySelector('[data-r2-home-photo]').value='';
      const cfg=await config(),urls={
        original:`${cfg.public_base}/images/photo-original.webp`,
        medium:`${cfg.public_base}/images/photo-960.webp`,
        large:`${cfg.public_base}/images/photo-1440.webp`
      };
      await renderLibrary(true);
      await applyHomePhotoSettings(urls);
    }catch(reason){if(source&&typeof source.close==='function')source.close();setStatus(reason.message,'error');}
  }

  async function deleteItem(key){
    if(!confirm(`確定刪除 R2 檔案？\n${key}`))return;
    try{
      setStatus(`正在刪除 ${key}…`);
      await api(`/cms/media?key=${encodeURIComponent(key)}`,{method:'DELETE'});
      await renderLibrary(true);
      setStatus('檔案已刪除','success');
    }catch(reason){setStatus(reason.message,'error');}
  }

  async function copyUrl(url){
    try{await navigator.clipboard.writeText(url);setStatus('已複製公開網址','success');}
    catch{setStatus('無法自動複製，請用「開啟」後複製網址','error');}
  }

  document.addEventListener('click',event=>{
    const panel=event.target.closest('#siteSettingsTab');
    if(panel&&r2Active&&!event.target.closest('#r2SettingsPane')&&!event.target.closest('[data-r2-settings-section]')){
      const nativeButton=event.target.closest('[data-site-settings-section]');
      if(nativeButton?.dataset.siteSettingsSection)nativeSection=nativeButton.dataset.siteSettingsSection;
      deactivateR2();
    }
    const button=event.target.closest('[data-r2-settings-section]');
    if(!button)return;
    event.preventDefault();
    event.stopImmediatePropagation();
    activateR2(null,true);
  },true);

  document.addEventListener('focusin',event=>{
    const input=event.target.closest('input');
    if(input)showSuggestions(input,{resetFolder:true});
  });
  document.addEventListener('input',event=>{
    const input=event.target.closest('input');
    if(input&&!input.closest('#r2SettingsPane'))showSuggestions(input,{resetFolder:true});
    if(event.target.matches('#r2SettingsPane [data-r2-search]'))renderLibrary().catch(reason=>setStatus(reason.message,'error'));
  });
  document.addEventListener('change',event=>{if(event.target.matches('#r2SettingsPane [data-r2-folder-filter]'))renderLibrary().catch(reason=>setStatus(reason.message,'error'));});
  document.addEventListener('click',event=>{
    const existing=event.target.closest('[data-site-settings-section]');
    if(existing){
      if(existing.dataset.siteSettingsSection)nativeSection=existing.dataset.siteSettingsSection;
      deactivateR2({restore:false});
      return;
    }
    const folderChoice=event.target.closest('[data-r2-folder-choice]');
    if(folderChoice){
      const popup=folderChoice.closest('.r2-media-suggestion-popup'),input=popupAnchor(popup);
      popup.dataset.r2Folder=folderChoice.dataset.r2FolderChoice;
      loadLibrary().then(library=>renderSuggestions(popup,input,library));
      return;
    }
    const folderBack=event.target.closest('[data-r2-folder-back]');
    if(folderBack){
      const popup=folderBack.closest('.r2-media-suggestion-popup'),input=popupAnchor(popup);
      delete popup.dataset.r2Folder;
      loadLibrary().then(library=>renderSuggestions(popup,input,library));
      return;
    }
    const choice=event.target.closest('[data-r2-media-url]');
    if(choice){
      const popup=choice.closest('.r2-media-suggestion-popup');
      useUrl(choice.dataset.r2MediaUrl,popupAnchor(popup),{keepR2:false});
      popup.hidden=true;
      return;
    }
    if(event.target.closest('[data-r2-open-settings]')){const input=popupAnchor(event.target.closest('.r2-media-suggestion-popup'));activateR2(input,true);return;}
    if(event.target.closest('[data-r2-refresh]')){renderLibrary(true).catch(reason=>setStatus(reason.message,'error'));return;}
    if(event.target.closest('[data-r2-upload]')){uploadGeneral();return;}
    if(event.target.closest('[data-r2-upload-photo]')){uploadHomePhoto();return;}
    const use=event.target.closest('[data-r2-use]');if(use){useUrl(use.dataset.r2Use,currentInput,{keepR2:true});return;}
    const copy=event.target.closest('[data-r2-copy]');if(copy){copyUrl(copy.dataset.r2Copy);return;}
    const del=event.target.closest('[data-r2-delete]');if(del){deleteItem(del.dataset.r2Delete);return;}
    document.querySelectorAll('.r2-media-suggestion-popup').forEach(popup=>{if(!popup.contains(event.target)&&popupAnchor(popup)!==event.target)popup.hidden=true;});
  });

  let refitQueued=false;
  const queueRefit=()=>{
    if(refitQueued)return;
    refitQueued=true;
    requestAnimationFrame(()=>{refitQueued=false;refitVisiblePopups();});
  };
  window.addEventListener('resize',queueRefit);
  document.addEventListener('scroll',queueRefit,true);

  const style=document.createElement('style');
  style.id='r2-storage-settings-styles';
  style.textContent=`
    .media-suggestion-popup{display:none!important}.field:has(.r2-media-suggestion-popup){position:relative}
    .r2-media-suggestion-popup{position:absolute;left:0;right:0;top:100%;z-index:210;max-height:330px;overflow:auto;margin-top:4px;border:1px solid #cfc4bb;border-radius:11px;background:#fff;box-shadow:0 16px 38px #3d2b2333}.r2-media-suggestion-popup[hidden]{display:none!important}.r2-media-suggestion-title{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 10px;background:#f5eee8;color:#6e625a;font-size:.72rem;font-weight:850}.r2-media-suggestion-actions{display:flex;align-items:center;gap:8px}.r2-media-suggestion-title button{border:0;background:none;color:#6f3628;font-weight:900;cursor:pointer}.r2-media-choice{display:grid;width:100%;gap:2px;padding:9px 10px;border:0;border-top:1px solid #eee6df;background:#fff;color:#2d2926;text-align:left;cursor:pointer}.r2-folder-choice strong{font-family:ui-monospace,monospace}.r2-media-choice:hover,.r2-media-choice:focus{background:#f8f1ec;outline:none}.r2-media-choice span{color:#766c65;font:11px ui-monospace,monospace}.r2-media-suggestion-popup>p{padding:10px;margin:0;color:#766c65}
    #r2SettingsPane{display:grid;gap:14px}#r2SettingsPane[hidden]{display:none!important}.r2-settings-card{margin:0}.r2-settings-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.r2-settings-head h3{margin:0}.r2-settings-head p{margin:3px 0 0;color:#766c65;font-size:.78rem}.r2-media-toolbar{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:10px;margin-top:12px}.r2-media-toolbar input,.r2-media-toolbar select,.r2-media-upload-grid input{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cec3ba;border-radius:9px;background:#fff;font:inherit}.r2-media-upload-grid{display:grid;grid-template-columns:240px minmax(0,1fr) auto;gap:10px;align-items:end}.r2-media-upload-grid.photo{grid-template-columns:minmax(0,1fr) auto}.r2-media-upload-grid label{display:grid;gap:5px;font-size:.78rem;font-weight:850;color:#6e625a}.r2-media-list{display:grid;gap:8px}.r2-media-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:12px;border:1px solid #e4dad2;border-radius:11px;background:#fff}.r2-media-row>div:first-child{display:grid;gap:3px;min-width:0}.r2-media-row strong,.r2-media-row span{overflow-wrap:anywhere}.r2-media-row span{color:#766c65;font:11px ui-monospace,monospace}
    @media(max-width:760px){.r2-media-toolbar,.r2-media-upload-grid,.r2-media-upload-grid.photo{grid-template-columns:1fr}.r2-settings-head,.r2-media-row{align-items:flex-start;grid-template-columns:1fr;display:grid}.r2-media-row .actions{justify-content:flex-start}}
  `;
  document.head.append(style);

  let attempts=0;
  const timer=setInterval(()=>{
    attempts+=1;
    if(installSettingsPane()||attempts>=120)clearInterval(timer);
  },50);

  const settingsRoot=document.querySelector('#siteSettingsTab')||document.body;
  let repairQueued=false;
  new MutationObserver(()=>{
    if(repairQueued)return;
    repairQueued=true;
    queueMicrotask(()=>{
      repairQueued=false;
      installSettingsPane();
      if(r2Active)setR2VisualState();
      queueRefit();
    });
  }).observe(settingsRoot,{childList:true,subtree:true});
})();

/* Load the notification-specific deployment bridge after the R2 manager. */
(function loadNotificationDeploymentBridge(){
  if(document.getElementById('notificationDeploymentBridgeScript'))return;
  const script=document.createElement('script');
  script.id='notificationDeploymentBridgeScript';
  script.src='notifications-deployment.js?v=worker-status-1';
  script.async=false;
  document.body.append(script);
})();
