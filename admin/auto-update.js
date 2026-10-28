/* Daily build scheduler: editable alongside R2 within Website Settings. */
(function installAutomaticUpdateSettings(){
  'use strict';
  if(window.__autoUpdateSettingsInstalled)return;
  window.__autoUpdateSettingsInstalled=true;
  const KEY='hctsui-auto-update-draft-v1';
  const FALLBACK={enabled:true,time:'00:15',timezone:'Asia/Tokyo'};
  let remote={...FALLBACK},draft={...FALLBACK},siteSettings=null,ready=false,active=false;
  const clone=x=>structuredClone(x);
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function normalize(value){
    const x=value&&typeof value==='object'?value:{};
    return {enabled:x.enabled!==false,time:/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(x.time||'')?x.time:FALLBACK.time,
      timezone:String(x.timezone||FALLBACK.timezone).trim()};
  }
  function valid(){
    if(!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(draft.time))return '時間必須使用 24 小時制 HH:MM';
    try{new Intl.DateTimeFormat('en-US',{timeZone:draft.timezone});return '';}catch{return '請填入有效的 IANA 時區，例如 Asia/Taipei';}
  }
  function changed(){return ready&&!same(remote,draft);}
  function save(){
    if(changed())localStorage.setItem(KEY,JSON.stringify({base:remote,data:draft}));else localStorage.removeItem(KEY);
    renderPane();
    if(typeof window.renderPreview==='function')window.renderPreview(false);
  }
  function sectionTabs(){return document.querySelector('#siteSettingsTab .site-settings-tabs');}
  function panel(){return document.querySelector('#siteSettingsTab');}
  function ensureUi(){
    const tabs=sectionTabs(),root=panel();if(!tabs||!root)return;
    const r2=tabs.querySelector('[data-r2-settings-section]');
    if(r2?.classList.contains('active'))active=false;
    let button=tabs.querySelector('[data-auto-update-settings-section]');
    if(!button){button=document.createElement('button');button.type='button';button.className='button';
      button.dataset.autoUpdateSettingsSection='';button.textContent='自動更新';}
    // The button is always immediately after R2 if the R2 module has loaded.
    if(r2){if(button.previousElementSibling!==r2)r2.after(button);}
    else if(button.parentElement!==tabs)tabs.append(button);
    let pane=root.querySelector('#autoUpdateSettingsPane');
    if(!pane){pane=document.createElement('div');pane.id='autoUpdateSettingsPane';pane.hidden=true;root.append(pane);}
    pane.hidden=!active;
    if(active){
      root.querySelectorAll('#generalSettingsPane,#contactFormSettingsPane,#seoSettingsPane,#analyticsSettingsPane,#r2SettingsPane').forEach(el=>el.hidden=true);
      tabs.querySelectorAll(':scope > .button.active').forEach(el=>{if(el!==button)el.classList.remove('active');});
    }
    if(button.classList.contains('active')!==active)button.classList.toggle('active',active);
  }
  function setVisibility(on){
    active=on;ensureUi();const root=panel();if(!root)return;
    const pane=root.querySelector('#autoUpdateSettingsPane');if(pane)pane.hidden=!on;
    const button=sectionTabs()?.querySelector('[data-auto-update-settings-section]');if(button&&button.classList.contains('active')!==on)button.classList.toggle('active',on);
    if(on){
      root.querySelectorAll('#generalSettingsPane,#contactFormSettingsPane,#seoSettingsPane,#analyticsSettingsPane,#r2SettingsPane').forEach(el=>el.hidden=true);
      sectionTabs()?.querySelectorAll(':scope > .button.active').forEach(el=>{if(el!==button)el.classList.remove('active');});
      renderPane();
    }
  }
  const ZONES=['Asia/Taipei','Asia/Tokyo','UTC','Asia/Hong_Kong','Asia/Singapore','Asia/Shanghai','Asia/Seoul','Europe/London','Europe/Paris','America/New_York','America/Los_Angeles','Australia/Sydney'];
  function renderPane(){
    const root=panel()?.querySelector('#autoUpdateSettingsPane');if(!root)return;
    const isDirty=changed(),error=valid();
    // Preserve focused input while typing: only replace when not focused in pane.
    if(document.activeElement?.closest('#autoUpdateSettingsPane')&&document.activeElement?.matches('input')){
      const status=root.querySelector('[data-auto-update-status]');if(status){status.textContent=error|| (isDirty?'有尚未送出的自動更新設定。':'目前沒有未送出的變更。');status.className='notice '+(error?'error':isDirty?'success':'');}
      return;
    }
    root.innerHTML=`<div class="settings-intro"><strong>每日自動更新</strong><span>設定活動自動轉入歷史紀錄、首頁 Upcoming 與 CV 的每日重建時間。未選入 Upcoming 的未來活動只會留在後台。</span></div>
      <div class="site-settings-card" style="max-width:760px">
        <h3>排程設定</h3>
        <label class="switch"><input data-auto-field="enabled" type="checkbox" ${draft.enabled?'checked':''}>啟用每日自動更新</label>
        <div class="pair-grid" style="margin-top:16px">
          <div class="field"><label for="autoDailyTime">每天執行時間</label><input id="autoDailyTime" data-auto-field="time" type="time" step="60" value="${esc(draft.time)}"></div>
          <div class="field"><label for="autoDailyZone">時區（IANA）</label><input id="autoDailyZone" data-auto-field="timezone" list="autoDailyTimezones" value="${esc(draft.timezone)}" spellcheck="false"><datalist id="autoDailyTimezones">${ZONES.map(x=>`<option value="${esc(x)}"></option>`).join('')}</datalist></div>
        </div>
        <p class="field-hint">預設為每天 00:15（Asia/Tokyo）。儲存後 GitHub Actions 會把每日排程改為指定時間及時區，不需要反覆檢查。GitHub 可能延遲啟動；時區也會用於網站日期判斷。首次使用需要設定具備 Workflows 寫入權限的 GitHub Token。</p>
        <div class="site-settings-subnote"><strong>預計時間</strong><span data-auto-summary></span></div>
        <div data-auto-update-status class="notice ${error?'error':isDirty?'success':''}" role="status">${esc(error|| (isDirty?'有尚未送出的自動更新設定，請使用上方 Batch 送出。':'目前沒有未送出的變更。'))}</div>
        <div class="actions" style="margin-top:14px"><button class="button" data-auto-revert type="button" ${isDirty?'':'disabled'}>還原此項設定</button></div>
      </div>`;
    const summary=root.querySelector('[data-auto-summary]');if(summary){
      try{const formatter=new Intl.DateTimeFormat('zh-TW',{timeZone:draft.timezone,dateStyle:'full',timeStyle:'short'});
        summary.textContent=`${draft.enabled?'啟用':'已關閉'}｜${draft.time}（${draft.timezone}）｜該時區目前：${formatter.format(new Date())}`;
      }catch{summary.textContent='時區尚未驗證';}
    }
  }
  function composeOperation(){
    const native=window.__originalSiteSettingsOperation?.()||null;
    if(!changed())return native;
    if(native){native.before.auto_update=clone(remote);native.after.auto_update=clone(draft);return native;}
    if(!siteSettings)return null;
    const before=clone(siteSettings),after=clone(siteSettings);
    before.auto_update=clone(remote);after.auto_update=clone(draft);
    return {op:'site_settings',before,after};
  }
  function bridge(){
    if(typeof window.siteSettingsOperation!=='function'||window.__originalSiteSettingsOperation)return;
    window.__originalSiteSettingsOperation=window.siteSettingsOperation;
    window.siteSettingsOperation=composeOperation;
    const oldDirty=window.siteSettingsDirty;
    window.siteSettingsDirty=()=>Boolean(oldDirty?.()||changed());
    const oldValidate=window.validateSiteSettingsDraft;
    window.validateSiteSettingsDraft=()=>[...(oldValidate?.()||[]),...(changed()&&valid()?[valid()]:[])];
    const oldClear=window.clearSiteSettingsDraft;
    window.clearSiteSettingsDraft=(reload=false)=>{oldClear?.(reload);draft=clone(remote);localStorage.removeItem(KEY);renderPane();};
    const oldPreview=window.siteSettingsPreviewHtml;
    window.siteSettingsPreviewHtml=operation=>{
      const value=oldPreview?.(operation)||'';
      const before=operation?.before?.auto_update,after=operation?.after?.auto_update;
      if(!before||!after||same(before,after))return value;
      return value+`<div class="settings-diff-section"><h4>每日自動更新</h4><p>${esc(before.enabled?'啟用':'停用')} · ${esc(before.time)} · ${esc(before.timezone)} → ${esc(after.enabled?'啟用':'停用')} · ${esc(after.time)} · ${esc(after.timezone)}</p></div>`;
    };
  }
  document.addEventListener('click',event=>{
    const autoButton=event.target.closest('[data-auto-update-settings-section]');
    if(autoButton){event.preventDefault();setVisibility(true);return;}
    if(event.target.closest('[data-site-settings-section],[data-r2-settings-section]')){if(active)setVisibility(false);return;}
    if(event.target.closest('[data-auto-revert]')){draft=clone(remote);save();return;}
  });
  document.addEventListener('input',event=>{
    const field=event.target.closest('[data-auto-field]');if(!field)return;
    draft[field.dataset.autoField]=field.type==='checkbox'?field.checked:field.value;
    save();
  });
  // Repair only if the Settings tab, R2 button, or this pane is replaced.
  // Do NOT observe class attributes: ensureUi() changes the selected tab's
  // classes, and observing those writes can cause an infinite microtask loop
  // that freezes the entire Admin page when 自動更新 is opened.
  const settingsRoot=panel();
  if(settingsRoot){
    const observer=new MutationObserver(()=>{
      const tabs=sectionTabs(),root=panel();
      if(!tabs||!root)return;
      const button=tabs.querySelector(':scope > [data-auto-update-settings-section]');
      const r2=tabs.querySelector(':scope > [data-r2-settings-section]');
      const pane=root.querySelector('#autoUpdateSettingsPane');
      // An ordinary pane update never requires repair; the UI must remain
      // untouched or this observer would observe its own changes repeatedly.
      if(button&&pane&&(!r2||button.previousElementSibling===r2))return;
      ensureUi();
    });
    observer.observe(settingsRoot,{childList:true,subtree:true});
  }
  fetch('../content/site.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('HTTP '+response.status);return response.json();}).then(data=>{
    const s=data.settings||{};
    siteSettings=Object.fromEntries(['general','footer','seo','analytics','contact_form','error_page'].map(key=>[key,clone(s[key]||{})]));
    remote=normalize(s.auto_update||{...FALLBACK,timezone:s.timezone||FALLBACK.timezone});
    try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');draft=saved&&same(saved.base,remote)?normalize(saved.data):clone(remote);}catch{draft=clone(remote);}
    ready=true;bridge();ensureUi();renderPane();
  }).catch(error=>{console.error('Auto-update settings could not load:',error);});
  bridge();ensureUi();
})();
