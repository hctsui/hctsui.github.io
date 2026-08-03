'use strict';

/*
 * Generate common search aliases for the existing People database.
 * Generated aliases are used only for search and author matching; they never
 * replace the displayed English or Chinese name.
 */
(function installAutomaticPeopleAliases(){
  const ROW_SELECTOR='[data-person-index]';
  const AUTO_SOURCE_EN='autoAliasSourceEn';
  const AUTO_SOURCE_ZH='autoAliasSourceZh';
  let scheduled=false;
  let syncing=false;

  const clean=value=>String(value||'').trim().replace(/\s+/g,' ');
  const key=value=>clean(value)
    .normalize('NFKC')
    .toLowerCase()
    .replace(/\s*[-–—]\s*/g,'-');

  const unique=(values,excluded=[])=>{
    const seen=new Set(excluded.map(key).filter(Boolean));
    const result=[];
    for(const value of values){
      const text=clean(value),normalized=key(text);
      if(!text||!normalized||seen.has(normalized))continue;
      seen.add(normalized);result.push(text);
    }
    return result;
  };

  const initial=token=>{
    const match=clean(token).match(/[\p{L}\p{N}]/u);
    return match?match[0].toUpperCase():'';
  };
  const dotted=letters=>letters.filter(Boolean).map(letter=>`${letter}.`).join(' ');
  const plain=letters=>letters.filter(Boolean).join(' ');

  function splitWesternName(name){
    const text=clean(name);if(!text)return null;
    if(text.includes(',')){
      const [surnamePart,...rest]=text.split(','),surname=clean(surnamePart),given=clean(rest.join(' ')),parts=given.split(/\s+/).filter(Boolean);
      if(!surname||!parts.length)return null;
      return {surname,first:parts[0],middle:parts.slice(1),canonical:text};
    }
    const parts=text.split(/\s+/).filter(Boolean);
    if(parts.length<2)return null;
    return {surname:parts.at(-1),first:parts[0],middle:parts.slice(1,-1),canonical:text};
  }

  function chineseRomanizationAliases(name){
    const text=clean(name);if(!text)return[];
    let surname='',givenText='';
    if(text.includes(',')){
      const [surnamePart,...rest]=text.split(',');
      surname=clean(surnamePart);givenText=clean(rest.join(' '));
    }else{
      const tokens=text.split(/\s+/).filter(Boolean);
      if(tokens.length<2)return[];
      surname=tokens.at(-1);givenText=tokens.slice(0,-1).join(' ');
    }
    const givenParts=givenText.split(/[\s-]+/).map(clean).filter(Boolean);
    if(!surname||!givenParts.length)return[];
    const givenHyphen=givenParts.join('-'),givenSpace=givenParts.join(' '),givenJoined=givenParts.join('');
    return unique([
      `${givenHyphen} ${surname}`,`${givenSpace} ${surname}`,`${givenJoined} ${surname}`,
      `${surname} ${givenHyphen}`,`${surname}, ${givenHyphen}`,
      `${surname} ${givenSpace}`,`${surname}, ${givenSpace}`,
      `${surname} ${givenJoined}`,`${surname}, ${givenJoined}`,
    ],[text]);
  }

  function foreignNameAliases(name){
    const parsed=splitWesternName(name);if(!parsed)return[];
    const {surname,first,middle,canonical}=parsed,allGiven=[first,...middle],letters=allGiven.map(initial),middleLetters=middle.map(initial),fullGiven=allGiven.join(' ');
    const firstAndMiddleDotted=[first,...middleLetters.map(letter=>`${letter}.`)].join(' ');
    const firstAndMiddlePlain=[first,...middleLetters].join(' ');
    const values=[
      `${fullGiven} ${surname}`,`${surname}, ${fullGiven}`,`${surname} ${fullGiven}`,
      `${first} ${surname}`,`${surname}, ${first}`,`${surname} ${first}`,
      `${dotted(letters)} ${surname}`,`${plain(letters)} ${surname}`,
      `${surname}, ${dotted(letters)}`,`${surname}, ${plain(letters)}`,
      `${initial(first)}. ${surname}`,`${initial(first)} ${surname}`,
    ];
    if(middle.length)values.push(
      `${firstAndMiddleDotted} ${surname}`,`${firstAndMiddlePlain} ${surname}`,
      `${surname}, ${firstAndMiddleDotted}`,`${surname}, ${firstAndMiddlePlain}`,
    );
    return unique(values,[canonical]);
  }

  function automaticAliases(enName,zhName){
    const english=clean(enName);if(!english)return[];
    return clean(zhName)?chineseRomanizationAliases(english):foreignNameAliases(english);
  }
  function lines(value){return String(value||'').split(/\n+/).map(clean).filter(Boolean)}
  function sameLines(left,right){return left.length===right.length&&left.every((value,index)=>value===right[index])}

  function rowState(row){
    const enInput=row.querySelector('[data-person-field="name.en"]');
    const zhInput=row.querySelector('[data-person-field="name.zh"]');
    const aliasInput=row.querySelector('[data-person-field="aliases"]');
    if(!enInput||!zhInput||!aliasInput)return null;
    const previousEn=row.dataset[AUTO_SOURCE_EN]??enInput.value;
    const previousZh=row.dataset[AUTO_SOURCE_ZH]??zhInput.value;
    const oldAuto=new Set(automaticAliases(previousEn,previousZh).map(key));
    return {
      row,enInput,zhInput,aliasInput,
      manual:lines(aliasInput.value).filter(value=>!oldAuto.has(key(value))),
      generated:automaticAliases(enInput.value,zhInput.value),
    };
  }

  function syncAll(){
    scheduled=false;if(syncing)return;
    if(clean(document.querySelector('#peopleSearch')?.value))return;
    syncing=true;
    try{
      const states=[...document.querySelectorAll(`#peopleRows ${ROW_SELECTOR}`)].map(rowState).filter(Boolean);
      const reserved=new Map(),generatedOwners=new Map();
      const claim=(map,value,index)=>{
        const normalized=key(value);if(!normalized)return;
        let owners=map.get(normalized);if(!owners){owners=new Set();map.set(normalized,owners)}owners.add(index);
      };
      states.forEach((state,index)=>{
        claim(reserved,state.enInput.value,index);claim(reserved,state.zhInput.value,index);
        state.manual.forEach(value=>claim(reserved,value,index));
        state.generated.forEach(value=>claim(generatedOwners,value,index));
      });
      states.forEach((state,index)=>{
        const allowed=state.generated.filter(value=>{
          const normalized=key(value),generated=generatedOwners.get(normalized),occupied=reserved.get(normalized);
          return generated?.size===1&&(!occupied||[...occupied].every(owner=>owner===index));
        });
        const merged=unique([...state.manual,...allowed],[state.enInput.value,state.zhInput.value]);
        state.row.dataset[AUTO_SOURCE_EN]=state.enInput.value;
        state.row.dataset[AUTO_SOURCE_ZH]=state.zhInput.value;
        const hint=state.aliasInput.closest('.field')?.querySelector('.field-hint');
        const hintText=`其他拼法只用於搜尋與作者比對，不會改變網站顯示。系統已依姓名自動加入 ${allowed.length} 種不衝突的常見拼法，可在此增刪。`;
        if(hint&&hint.textContent!==hintText)hint.textContent=hintText;
        if(sameLines(lines(state.aliasInput.value),merged))return;
        state.aliasInput.value=merged.join('\n');
        state.aliasInput.dispatchEvent(new Event('input',{bubbles:true}));
      });
    }finally{syncing=false}
  }
  function schedule(){if(scheduled)return;scheduled=true;queueMicrotask(syncAll)}

  document.addEventListener('input',event=>{
    const field=event.target.closest('[data-person-field="name.en"],[data-person-field="name.zh"]');
    if(field?.closest(ROW_SELECTOR))schedule();
  });
  document.addEventListener('input',event=>{
    if(event.target.matches('#peopleSearch')&&!clean(event.target.value))setTimeout(schedule,0);
  });
  document.addEventListener('click',event=>{
    if(event.target.closest('[data-database-type="people"]'))setTimeout(schedule,0);
  });

  function installObserver(){
    const root=document.querySelector('#peopleRows');
    if(!root||root.dataset.peopleAliasObserverInstalled)return false;
    root.dataset.peopleAliasObserverInstalled='1';
    new MutationObserver(schedule).observe(root,{childList:true});
    schedule();return true;
  }
  if(!installObserver()){
    const observer=new MutationObserver(()=>{if(installObserver())observer.disconnect()});
    observer.observe(document.body,{childList:true,subtree:true});
  }
  window.peopleAutomaticAliases=automaticAliases;
})();

/* Detailed People preview and one canonical clear-all-drafts action. */
(function installDraftPreviewExtension(){
  if(window.__hctsuiDraftPreviewExtensionInstalled)return;
  window.__hctsuiDraftPreviewExtensionInstalled=true;

  const ACTIVE_DRAFT_KEYS=[
    'hctsui-batch-v12',
    'hctsui-translations-draft-v1',
    'hctsui-translations-stale-v1',
    'hctsui-headings-draft-v1',
    'hctsui-homepage-draft-v1',
    'hctsui-layout-draft-v3',
    'hctsui-general-layout-links-v1',
    'hctsui-people-draft',
    'hctsui-people-draft-recovery-v1',
    'hctsui-people-draft-backup-v2',
    'hctsui-people-draft-safety-backup-v1',
    'hctsui-site-settings-draft',
    'hctsui-arxiv-suggestions-draft-v1',
    'hctsui-general-notifications-draft-v1',
    'hctsui-personal-profile-draft-v1',
  ];

  const cloneValue=value=>{
    if(typeof structuredClone==='function')return structuredClone(value);
    return JSON.parse(JSON.stringify(value));
  };
  const escapeHtml=value=>{
    if(typeof window.esc==='function')return window.esc(String(value??''));
    return String(value??'').replace(/[&<>"']/g,char=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    })[char]);
  };
  const clean=value=>String(value??'').trim().replace(/\s+/g,' ');
  const display=value=>clean(value)||'（未設定）';
  const normalizedAliases=value=>{
    const source=Array.isArray(value)?value:String(value||'').split(/[\n,，]+/);
    const seen=new Set(),result=[];
    for(const raw of source){
      const text=clean(raw),key=text.normalize('NFKC').toLocaleLowerCase();
      if(!text||seen.has(key))continue;
      seen.add(key);result.push(text);
    }
    return result;
  };
  function normalizePeople(value){
    const rows=Array.isArray(value?.people)?value.people:[];
    return rows.filter(row=>row&&typeof row==='object').map((row,index)=>({
      id:clean(row.id)||`person-${index+1}`,
      name:{en:clean(row.name?.en),zh:clean(row.name?.zh)},
      aliases:normalizedAliases(row.aliases),
      url:clean(row.url),
    }));
  }
  const personTitle=person=>person?.name?.en||person?.name?.zh||person?.id||'未命名作者';
  function aliasDifference(before,after){
    const beforeKeys=new Map(before.map(value=>[value.normalize('NFKC').toLocaleLowerCase(),value]));
    const afterKeys=new Map(after.map(value=>[value.normalize('NFKC').toLocaleLowerCase(),value]));
    return {
      added:after.filter(value=>!beforeKeys.has(value.normalize('NFKC').toLocaleLowerCase())),
      removed:before.filter(value=>!afterKeys.has(value.normalize('NFKC').toLocaleLowerCase())),
    };
  }
  function chips(values,kind){
    if(!values.length)return '<span class="people-diff-empty">無</span>';
    return `<span class="people-diff-chips">${values.map(value=>`<span class="people-diff-chip ${kind}">${escapeHtml(value)}</span>`).join('')}</span>`;
  }
  function fieldChange(label,before,after){
    if(clean(before)===clean(after))return '';
    return `<div class="people-diff-field changed"><strong>${escapeHtml(label)}</strong><div class="people-diff-values"><span class="before">${escapeHtml(display(before))}</span><span class="people-diff-arrow">→</span><span class="after">${escapeHtml(display(after))}</span></div></div>`;
  }
  function fullPersonFields(person){
    return `<div class="people-diff-field"><strong>英文姓名</strong><span>${escapeHtml(display(person.name.en))}</span></div>
      <div class="people-diff-field"><strong>中文姓名</strong><span>${escapeHtml(display(person.name.zh))}</span></div>
      <div class="people-diff-field"><strong>學術網頁</strong><span>${escapeHtml(display(person.url))}</span></div>
      <div class="people-diff-field"><strong>別名</strong>${chips(person.aliases,'neutral')}</div>`;
  }
  function addedOrRemovedCard(person,kind){
    const label=kind==='added'?'新增':'刪除';
    return `<article class="people-diff-card ${kind}"><div class="people-diff-card-head"><strong>${escapeHtml(personTitle(person))}</strong><span class="people-diff-status">${label}</span></div>${fullPersonFields(person)}</article>`;
  }
  function modifiedCard(before,after){
    const aliases=aliasDifference(before.aliases,after.aliases);
    const fields=[
      fieldChange('英文姓名',before.name.en,after.name.en),
      fieldChange('中文姓名',before.name.zh,after.name.zh),
      fieldChange('學術網頁',before.url,after.url),
    ].filter(Boolean);
    if(aliases.added.length||aliases.removed.length){
      fields.push(`<div class="people-diff-field changed"><strong>別名變更</strong><div class="people-diff-alias-groups"><div><span class="people-diff-label added">新增別名</span>${chips(aliases.added,'added')}</div><div><span class="people-diff-label removed">刪除別名</span>${chips(aliases.removed,'removed')}</div></div></div>`);
    }
    if(!fields.length)return '';
    return `<article class="people-diff-card changed"><div class="people-diff-card-head"><strong>${escapeHtml(personTitle(after))}</strong><span class="people-diff-status">修改</span></div>${fields.join('')}</article>`;
  }
  function detailedPeoplePreview(operation){
    const before=normalizePeople(operation?.before),after=normalizePeople(operation?.after);
    const beforeMap=new Map(before.map(person=>[person.id,person]));
    const afterMap=new Map(after.map(person=>[person.id,person]));
    const added=after.filter(person=>!beforeMap.has(person.id));
    const removed=before.filter(person=>!afterMap.has(person.id));
    const modified=after
      .filter(person=>beforeMap.has(person.id))
      .map(person=>modifiedCard(beforeMap.get(person.id),person))
      .filter(Boolean);
    const beforeOrder=before.map(person=>person.id).join('\u0001');
    const afterOrder=after.map(person=>person.id).join('\u0001');
    const orderChanged=beforeOrder!==afterOrder&&!added.length&&!removed.length;
    const total=added.length+removed.length+modified.length+(orderChanged?1:0);
    const cards=[
      ...added.map(person=>addedOrRemovedCard(person,'added')),
      ...modified,
      ...removed.map(person=>addedOrRemovedCard(person,'removed')),
    ].join('');
    const orderNotice=orderChanged?'<div class="notice"><strong>順序調整：</strong>人名項目的排列順序已變更。</div>':'';
    return `<details class="diff people-diff-preview" open><summary><strong>人名連結資料</strong>：${before.length} → ${after.length} 人；${total} 項變更</summary><p class="people-diff-guide">逐欄顯示英文姓名、中文姓名、學術網頁，以及別名的新增與刪除。</p>${orderNotice}${cards||'<p class="muted">沒有實際變更。</p>'}</details>`;
  }

  function installPeoplePreview(){
    if(typeof window.peoplePreviewHtml!=='function')return false;
    window.peoplePreviewHtml=detailedPeoplePreview;
    window.peopleHistoryPreviewHtml=history=>detailedPeoplePreview({before:history?.before,after:history?.after});
    return true;
  }

  function removeDraftStorage(){
    for(const key of ACTIVE_DRAFT_KEYS)localStorage.removeItem(key);
    sessionStorage.removeItem('hctsui-submission-pending');
  }
  function callClearer(name){
    const fn=window[name];
    if(typeof fn==='function'){
      try{fn(false);}catch(error){console.warn(`Unable to run ${name}`,error);}
    }
  }
  function resetSharedDraftState(){
    try{if(typeof draft!=='undefined')draft=[];}catch{}
    try{
      if(typeof translations!=='undefined'&&typeof originalTranslations!=='undefined')translations=cloneValue(originalTranslations);
    }catch{}
    try{
      if(typeof layoutBase!=='undefined'&&layoutBase&&typeof layoutDraft!=='undefined')layoutDraft=cloneValue(layoutBase);
    }catch{}
    for(const name of [
      'clearHomepageDraft',
      'clearPeopleDraft',
      'clearArxivSuggestionsDraft',
      'clearGeneralNotificationsDraft',
      'clearSiteSettingsDraft',
    ])callClearer(name);
  }
  function clearAllCmsDrafts({reload=false,showMessage=true}={}){
    removeDraftStorage();
    resetSharedDraftState();
    if(reload){location.reload();return;}
    if(typeof window.renderAll==='function')window.renderAll();
    else if(typeof window.renderPreview==='function')window.renderPreview(false);
    if(showMessage&&typeof window.flash==='function')window.flash('已清空所有內容、排序、首頁、個人資料、資料庫、通知中心與網站設定草稿');
  }
  window.clearAllCmsDrafts=clearAllCmsDrafts;
  window.cmsDraftStorageKeys=[...ACTIVE_DRAFT_KEYS];

  function installClearButton(){
    const button=document.querySelector('#clearDraft');
    if(!button)return false;
    button.dataset.clearsAllCmsDrafts='1';
    button.onclick=()=>{
      if(!confirm('清空所有內容、排序、首頁、個人資料、資料庫、通知中心與網站設定草稿？'))return;
      clearAllCmsDrafts({reload:true,showMessage:false});
    };
    return true;
  }
  function installSubmittedDraftWrapper(){
    const current=window.clearSubmittedDraft;
    if(typeof current!=='function')return false;
    if(current.__clearsAllCmsDrafts)return true;
    const wrapped=function(){
      const result=current.apply(this,arguments);
      clearAllCmsDrafts({reload:false,showMessage:false});
      return result;
    };
    wrapped.__clearsAllCmsDrafts=true;
    window.clearSubmittedDraft=wrapped;
    try{clearSubmittedDraft=wrapped;}catch{}
    return true;
  }
  function installAll(){
    const previewReady=installPeoplePreview();
    const buttonReady=installClearButton();
    const submittedReady=installSubmittedDraftWrapper();
    return previewReady&&buttonReady&&submittedReady;
  }

  const style=document.createElement('style');
  style.textContent=`
    .people-diff-preview{display:grid;gap:10px}
    .people-diff-guide{margin:0;padding:9px 11px;border-radius:8px;background:#fff7dc;color:#654b10;font-size:.78rem}
    .people-diff-card{display:grid;gap:7px;padding:11px;border:1px solid #ded3ca;border-radius:11px;background:#fff}
    .people-diff-card.added{border-left:5px solid #247a46}.people-diff-card.removed{border-left:5px solid #a1342b}.people-diff-card.changed{border-left:5px solid #c58a32}
    .people-diff-card-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .people-diff-status{border-radius:999px;background:#eee5de;padding:2px 8px;font-size:.7rem;font-weight:900}
    .people-diff-card.added .people-diff-status{background:#dff2e5;color:#1f6539}.people-diff-card.removed .people-diff-status{background:#f9dfdc;color:#8c2f26}.people-diff-card.changed .people-diff-status{background:#f2dfb8;color:#68420b}
    .people-diff-field{display:grid;grid-template-columns:minmax(90px,130px) minmax(0,1fr);gap:8px;align-items:start;padding-top:7px;border-top:1px solid #eee6df}
    .people-diff-field>strong{font-size:.76rem;color:#6e625a}.people-diff-field.changed{margin:0 -5px;padding:7px 5px 0;border-radius:7px;background:#fff9ec}
    .people-diff-values{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:7px;align-items:start}.people-diff-values span{overflow-wrap:anywhere}.people-diff-values .before{color:#8c2f26}.people-diff-values .after{color:#1f6539}.people-diff-arrow{font-weight:900;color:#766c65}
    .people-diff-alias-groups{display:grid;gap:8px}.people-diff-label{display:block;margin-bottom:4px;font-size:.7rem;font-weight:900}.people-diff-label.added{color:#1f6539}.people-diff-label.removed{color:#8c2f26}
    .people-diff-chips{display:flex;flex-wrap:wrap;gap:5px}.people-diff-chip{display:inline-block;border-radius:999px;padding:3px 8px;background:#eee5de;font-size:.74rem;overflow-wrap:anywhere}.people-diff-chip.added{background:#dff2e5;color:#1f6539}.people-diff-chip.removed{background:#f9dfdc;color:#8c2f26;text-decoration:line-through}.people-diff-empty{color:#766c65;font-size:.76rem}
    @media(max-width:700px){.people-diff-field,.people-diff-values{grid-template-columns:1fr}.people-diff-arrow{transform:rotate(90deg);justify-self:start}}
  `;
  document.head.append(style);

  if(!installAll()){
    let attempts=0;
    const timer=setInterval(()=>{
      attempts+=1;
      if(installAll()||attempts>=80)clearInterval(timer);
    },50);
  }
})();

/* Load inline navigation ordering and website-identity placement help. */
(function(){
  if(document.getElementById('navigationSettingsInlineScript'))return;
  const script=document.createElement('script');
  script.id='navigationSettingsInlineScript';
  script.src='navigation-settings.js?v=20260802-1';
  script.async=false;
  document.body.append(script);
})();

/* Load the authenticated Cloudflare R2 storage manager. */
(function(){
  if(document.getElementById('r2MediaLibraryScript'))return;
  const script=document.createElement('script');
  script.id='r2MediaLibraryScript';
  script.src='r2-media.js?v=r5';
  script.async=false;
  document.body.append(script);
})();
