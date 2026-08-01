'use strict';

/* Protect the person-link database from an incomplete browser draft silently
   replacing the repository copy. The canonical data remains content/people.json. */
(function installPeopleDraftSafety(){
  const DRAFT_KEY='hctsui-people-draft';
  const LEGACY_BACKUP_KEY='hctsui-people-draft-backup-v2';
  const SAFETY_BACKUP_KEY='hctsui-people-draft-safety-backup-v1';
  const ALLOW_KEY='hctsui-people-allow-removal-once';
  let remote={schema_version:1,people:[]};
  let ready=false;

  const normalize=value=>{
    const rows=Array.isArray(value?.people)?value.people:[];
    return {schema_version:1,people:rows.filter(row=>row&&typeof row==='object').map(row=>({
      id:String(row.id||''),
      name:{en:String(row.name?.en||''),zh:String(row.name?.zh||'')},
      aliases:Array.isArray(row.aliases)?row.aliases.map(String):[],
      url:String(row.url||''),
    })).filter(row=>row.id)};
  };
  function savedEnvelope(){
    try{return JSON.parse(localStorage.getItem(DRAFT_KEY)||'null')}catch{return null}
  }
  function activeDraft(){
    const saved=savedEnvelope();
    return saved?.data?normalize(saved.data):normalize(remote);
  }
  function missingRows(){
    const draftIds=new Set(activeDraft().people.map(row=>row.id));
    return remote.people.filter(row=>!draftIds.has(row.id));
  }
  function personLabel(row){return row.name?.zh&&row.name?.en?`${row.name.en}／${row.name.zh}`:row.name?.en||row.name?.zh||row.id}
  function backupDraft(){
    const raw=localStorage.getItem(DRAFT_KEY)||localStorage.getItem(LEGACY_BACKUP_KEY);
    if(raw)localStorage.setItem(SAFETY_BACKUP_KEY,JSON.stringify({saved_at:new Date().toISOString(),draft:raw}));
  }
  function ensurePanel(){
    const pane=document.querySelector('#peopleDatabasePane');if(!pane)return null;
    let panel=pane.querySelector('[data-people-safety]');
    if(!panel){
      panel=document.createElement('div');panel.dataset.peopleSafety='';panel.className='notice people-safety-panel';
      const toolbar=pane.querySelector('.toolbar');toolbar?.insertAdjacentElement('afterend',panel);
      panel.addEventListener('click',event=>{
        if(event.target.closest('[data-reload-official-people]')){
          if(!confirm('重新載入 GitHub 正式人名資料？目前瀏覽器草稿會先備份，再從正式資料重新開始。'))return;
          backupDraft();localStorage.removeItem(DRAFT_KEY);sessionStorage.removeItem(ALLOW_KEY);location.reload();
        }
        if(event.target.closest('[data-allow-people-removal]')){
          const missing=missingRows();
          if(!missing.length)return;
          if(confirm(`目前草稿會刪除 ${missing.length} 位正式人名。確定只允許這一次送出嗎？`)){
            sessionStorage.setItem(ALLOW_KEY,'1');render();
          }
        }
      });
    }
    return panel;
  }
  function render(){
    if(!ready)return;const panel=ensurePanel();if(!panel)return;
    const draft=activeDraft(),missing=missingRows(),allowed=sessionStorage.getItem(ALLOW_KEY)==='1';
    panel.className='notice people-safety-panel '+(missing.length&&!allowed?'error':missing.length?'':'success');
    panel.innerHTML=`<div class="people-safety-head"><div><strong>人名資料：GitHub 正式 ${remote.people.length} 人／目前草稿 ${draft.people.length} 人</strong><span>${missing.length?`草稿缺少 ${missing.length} 位正式資料：${missing.slice(0,8).map(personLabel).join('、')}${missing.length>8?'…':''}`:'目前草稿沒有漏掉正式人名。'}</span></div><div class="actions"><button class="button" type="button" data-reload-official-people>重新載入正式資料</button>${missing.length?`<button class="button ${allowed?'':'danger'}" type="button" data-allow-people-removal>${allowed?'本次已允許刪除':'確認本次刪除'}</button>`:''}</div></div>`;
  }
  function shouldBlockSubmission(){return ready&&missingRows().length>0&&sessionStorage.getItem(ALLOW_KEY)!=='1'}

  document.addEventListener('click',event=>{
    const submit=event.target.closest('#submitBatch');if(!submit||!shouldBlockSubmission())return;
    event.preventDefault();event.stopImmediatePropagation();
    const names=missingRows().slice(0,8).map(personLabel).join('、');
    if(typeof flash==='function')flash(`已阻止送出：人名草稿少了正式資料（${names}）。請先重新載入正式資料，或明確確認本次刪除。`);
    document.querySelector('[data-people-safety]')?.scrollIntoView({behavior:'smooth',block:'center'});
  },true);
  document.addEventListener('input',event=>{if(event.target.closest('#peopleDatabasePane'))setTimeout(render,0)});
  document.addEventListener('change',event=>{if(event.target.closest('#peopleDatabasePane'))setTimeout(render,0)});
  document.addEventListener('click',event=>{if(event.target.closest('#peopleDatabasePane'))setTimeout(render,0)});
  window.addEventListener('storage',event=>{if(event.key===DRAFT_KEY)render()});

  const style=document.createElement('style');style.textContent=`
    .people-safety-panel{margin:12px 0}.people-safety-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.people-safety-head>div:first-child{display:grid;gap:4px}.people-safety-head span{color:#6c625c}.people-safety-panel.error .people-safety-head span{color:#8b2723}@media(max-width:720px){.people-safety-head{align-items:flex-start;flex-direction:column}}`;
  document.head.append(style);

  fetch('../content/people.json',{cache:'no-store'}).then(response=>response.ok?response.json():{schema_version:1,people:[]}).catch(()=>({schema_version:1,people:[]})).then(value=>{
    remote=normalize(value);ready=true;ensurePanel();render();
    new MutationObserver(render).observe(document.querySelector('#peopleDatabasePane')||document.body,{childList:true,subtree:true});
  });
})();
