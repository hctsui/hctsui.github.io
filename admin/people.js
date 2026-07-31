/* Person-link database and click-only author suggestions. */
(function installPeopleManager(){
  const PEOPLE_DRAFT_KEY='hctsui-people-draft';
  let peopleRemote={schema_version:1,people:[]};
  let peopleDraft={schema_version:1,people:[]};
  let peopleReady=false;

  function copy(value){return structuredClone(value);}
  function normalizeSpace(value){return String(value||'').trim().replace(/\s+/g,' ');}
  function normalizeKey(value){return normalizeSpace(value).normalize('NFKC').toLowerCase();}
  function empty(){return {schema_version:1,people:[]};}
  function slug(value){return normalizeKey(value).replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,64)||'person';}
  function normalizeAliases(value,names){
    const source=Array.isArray(value)?value:String(value||'').split(/[\n,，]+/);
    const seen=new Set(names.map(normalizeKey).filter(Boolean));
    const result=[];
    for(const raw of source){
      const text=normalizeSpace(raw),key=normalizeKey(text);
      if(!text||seen.has(key))continue;
      seen.add(key);result.push(text);
    }
    return result;
  }
  function normalizePeople(value){
    const source=value&&typeof value==='object'?value:empty();
    const rows=Array.isArray(source.people)?source.people:[];
    const used=new Set();
    const people=[];
    rows.forEach((raw,index)=>{
      if(!raw||typeof raw!=='object')return;
      const name={
        en:normalizeSpace(raw.name?.en),
        zh:normalizeSpace(raw.name?.zh),
      };
      let base=normalizeSpace(raw.id).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||slug(name.en||name.zh||`person-${index+1}`);
      let id=base,n=2;while(used.has(id))id=`${base}-${n++}`;used.add(id);
      people.push({id,name,aliases:normalizeAliases(raw.aliases,[name.en,name.zh]),url:normalizeSpace(raw.url)});
    });
    return {schema_version:1,people};
  }
  function peopleEqual(a,b){return JSON.stringify(normalizePeople(a))===JSON.stringify(normalizePeople(b));}
  function loadSaved(remote){
    try{
      const saved=JSON.parse(localStorage.getItem(PEOPLE_DRAFT_KEY)||'null');
      if(!saved?.base||!saved?.data)return copy(remote);
      if(peopleEqual(saved.base,remote))return normalizePeople(saved.data);
      localStorage.removeItem(PEOPLE_DRAFT_KEY);
      if(typeof flash==='function')flash('人名連結資料已在其他地方更新；舊草稿未自動套用。');
    }catch{localStorage.removeItem(PEOPLE_DRAFT_KEY);}
    return copy(remote);
  }
  function peopleDirty(){return peopleReady&&!peopleEqual(peopleRemote,peopleDraft);}
  function savePeopleLocal(rerender=true){
    peopleDraft=normalizePeople(peopleDraft);
    if(peopleDirty())localStorage.setItem(PEOPLE_DRAFT_KEY,JSON.stringify({base:peopleRemote,data:peopleDraft}));
    else localStorage.removeItem(PEOPLE_DRAFT_KEY);
    if(rerender)renderPeopleManager();else renderPeopleStatus();
    if(typeof renderPreview==='function')renderPreview(false);
  }
  function clearPeopleDraft(reload=false){
    localStorage.removeItem(PEOPLE_DRAFT_KEY);
    peopleDraft=copy(peopleRemote);
    if(reload)renderPeopleManager();
  }
  function validatePeopleDraft(){
    const errors=[],ids=new Set(),names=new Map();
    const rows=normalizePeople(peopleDraft).people;
    if(rows.length>1000)errors.push('人名連結資料最多 1000 人');
    rows.forEach((person,index)=>{
      const label=person.name.en||person.name.zh||`第 ${index+1} 人`;
      if(!person.name.en&&!person.name.zh)errors.push(`${label}：至少需要英文或中文姓名`);
      if(ids.has(person.id))errors.push(`${label}：ID 重複`);ids.add(person.id);
      if(person.url){
        try{const u=new URL(person.url);if(!['http:','https:'].includes(u.protocol))throw new Error();}
        catch{errors.push(`${label}：網址必須是完整的 http 或 https 網址`);}
      }
      for(const candidate of [person.name.en,person.name.zh,...person.aliases]){
        const key=normalizeKey(candidate);if(!key)continue;
        const owner=names.get(key);if(owner&&owner!==person.id)errors.push(`${candidate}：已同時分配給兩位作者`);else names.set(key,person.id);
      }
    });
    return [...new Set(errors)];
  }
  function peopleOperation(){
    if(!peopleDirty())return null;
    return {op:'people',before:copy(normalizePeople(peopleRemote)),after:copy(normalizePeople(peopleDraft))};
  }
  function peoplePreviewHtml(operation){
    const before=normalizePeople(operation?.before).people;
    const after=normalizePeople(operation?.after).people;
    const beforeMap=new Map(before.map(x=>[x.id,x]));
    const afterMap=new Map(after.map(x=>[x.id,x]));
    const changed=after.filter(row=>JSON.stringify(row)!==JSON.stringify(beforeMap.get(row.id)));
    const removed=before.filter(row=>!afterMap.has(row.id));
    const rowHtml=row=>`<div class="order-diff-row changed"><span class="order-diff-name"><strong>${esc(row.name.en||row.name.zh||row.id)}</strong>${row.name.en&&row.name.zh?`／${esc(row.name.zh)}`:''}<br><span class="muted">${esc(row.url||'未設定網址')}</span></span></div>`;
    return `<details class="diff"><summary><strong>人名連結資料</strong>：${before.length} → ${after.length} 人</summary><div class="preview-columns"><div><h4>新增／修改</h4>${changed.length?`<div class="order-diff-list">${changed.map(rowHtml).join('')}</div>`:'<p class="muted">沒有新增或修改</p>'}</div><div><h4>刪除</h4>${removed.length?`<div class="order-diff-list">${removed.map(rowHtml).join('')}</div>`:'<p class="muted">沒有刪除</p>'}</div></div></details>`;
  }
  function personRowHtml(person,index){
    return `<div class="person-manager-row" data-person-index="${index}"><div class="person-manager-head"><strong>${esc(person.name.en||person.name.zh||'未命名作者')}</strong><button class="button danger" type="button" data-remove-person="${index}">刪除</button></div><div class="pair-grid"><div class="field"><label>英文姓名</label><input data-person-field="name.en" value="${esc(person.name.en)}"></div><div class="field"><label>中文姓名</label><input data-person-field="name.zh" value="${esc(person.name.zh)}"></div></div><div class="field"><label>學術網頁 URL</label><input data-person-field="url" type="url" placeholder="https://..." value="${esc(person.url)}"></div><div class="field"><label>其他拼法</label><textarea data-person-field="aliases" placeholder="每行一個，例如 Tsui, Hung-Chun">${esc(person.aliases.join('\n'))}</textarea><p class="field-hint">只用於搜尋與精確比對，不會改變論文中實際顯示的姓名。</p></div></div>`;
  }
  function renderPeopleStatus(){
    const errors=validatePeopleDraft();
    const status=document.querySelector('#peopleStatus');
    if(status){status.className='notice '+(errors.length?'error':peopleDirty()?'success':'');status.innerHTML=errors.length?`<strong>不能送出：</strong>${errors.map(esc).join('；')}`:peopleDirty()?`已修改人名連結資料；目前 ${peopleDraft.people.length} 人，會和本次批次一起送出。`:`目前 ${peopleDraft.people.length} 人；尚未修改。`;}
  }
  function renderPeopleManager(){
    const root=document.querySelector('#peopleDatabasePane');if(!root)return;
    const q=normalizeKey(document.querySelector('#peopleSearch')?.value);
    const rows=normalizePeople(peopleDraft).people.map((person,index)=>({person,index})).filter(({person})=>!q||[person.name.en,person.name.zh,person.url,...person.aliases].some(v=>normalizeKey(v).includes(q)));
    renderPeopleStatus();
    const list=document.querySelector('#peopleRows');if(list)list.innerHTML=rows.length?rows.map(({person,index})=>personRowHtml(person,index)).join(''):'<p class="muted">沒有符合的人名。</p>';
  }
  function addPerson(){
    const used=new Set(peopleDraft.people.map(p=>p.id));let base='new-person',id=base,n=2;while(used.has(id))id=`${base}-${n++}`;
    peopleDraft.people.unshift({id,name:{en:'',zh:''},aliases:[],url:''});savePeopleLocal();
    document.querySelector('#peopleRows input')?.focus();
  }
  function candidateScore(person,query){
    const values=[person.name.en,person.name.zh,...person.aliases].map(normalizeKey).filter(Boolean);
    let best=99;for(const value of values){if(value===query)best=Math.min(best,0);else if(value.startsWith(query))best=Math.min(best,1);else if(value.split(/\s+/).some(x=>x.startsWith(query)))best=Math.min(best,2);else if(value.includes(query))best=Math.min(best,3);}return best;
  }
  function authorCandidates(query){
    const q=normalizeKey(query);if(!q)return [];
    return normalizePeople(peopleDraft).people.map(person=>({person,score:candidateScore(person,q)})).filter(x=>x.score<99).sort((a,b)=>a.score-b.score||(a.person.name.en||a.person.name.zh).localeCompare(b.person.name.en||b.person.name.zh)).slice(0,8).map(x=>x.person);
  }
  function closeSuggestions(except){document.querySelectorAll('[data-author-suggestions]').forEach(x=>{if(x!==except)x.hidden=true;});}
  function showSuggestions(input){
    const row=input.closest('[data-author-row]');if(!row)return;
    let box=row.querySelector('[data-author-suggestions]');
    if(!box){box=document.createElement('div');box.dataset.authorSuggestions='';box.className='author-suggestions';row.append(box);}
    const candidates=authorCandidates(input.value);
    if(!candidates.length){box.hidden=true;return;}
    box.innerHTML=`<div class="author-suggestions-label">可能的人名（點選後才會填入）</div>${candidates.map(person=>`<button type="button" class="author-suggestion" data-person-id="${esc(person.id)}"><span><strong>${esc(person.name.en||'—')}</strong><small>${esc(person.name.zh||'—')}</small></span>${person.url?'<span class="tag">有連結</span>':'<span class="muted">未設網址</span>'}</button>`).join('')}`;
    box.hidden=false;closeSuggestions(box);
  }
  function chooseSuggestion(button){
    const person=normalizePeople(peopleDraft).people.find(x=>x.id===button.dataset.personId);if(!person)return;
    const row=button.closest('[data-author-row]');
    const en=row?.querySelector('[data-author-en]'),zh=row?.querySelector('[data-author-zh]');
    if(en)en.value=person.name.en;if(zh)zh.value=person.name.zh;
    button.closest('[data-author-suggestions]').hidden=true;
    en?.dispatchEvent(new Event('change',{bubbles:true}));zh?.dispatchEvent(new Event('change',{bubbles:true}));
  }
  function installStyles(){
    if(document.querySelector('#people-manager-styles'))return;
    const style=document.createElement('style');style.id='people-manager-styles';style.textContent=`
      .person-manager-row{border:1px solid #dfd3ca;border-radius:12px;padding:12px;margin:10px 0;background:#fcfaf8}
      .person-manager-head{display:flex;justify-content:space-between;gap:10px;align-items:center}
      .author-suggestions{margin-top:8px;border:1px solid #cfc4bb;border-radius:11px;background:#fff;box-shadow:0 12px 28px rgba(45,41,38,.14);overflow:hidden;position:relative;z-index:8}
      .author-suggestions-label{padding:8px 10px;background:#f6f0eb;color:#6e625a;font-size:.75rem;font-weight:800}
      .author-suggestion{width:100%;display:flex;justify-content:space-between;gap:12px;align-items:center;border:0;border-top:1px solid #eee6df;background:#fff;padding:9px 10px;text-align:left;cursor:pointer;color:inherit}
      .author-suggestion:hover,.author-suggestion:focus{background:#faf3ed;outline:none}.author-suggestion span:first-child{display:grid}.author-suggestion small{color:#766c65}
      .bibtex-editor textarea{min-height:150px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem}
    `;document.head.append(style);
  }
  function setDatabaseType(type){
    const active=type==='people'?'people':'translations';
    document.querySelectorAll('[data-database-type]').forEach(button=>button.classList.toggle('active',button.dataset.databaseType===active));
    const translationsPane=document.querySelector('#translationDatabasePane');
    const peoplePane=document.querySelector('#peopleDatabasePane');
    if(translationsPane)translationsPane.hidden=active!=='translations';
    if(peoplePane)peoplePane.hidden=active!=='people';
    localStorage.setItem('hctsui-database-type',active);
    if(active==='people')renderPeopleManager();
  }
  function installPanel(){
    const dictionaryButton=document.querySelector('[data-tab="dictionary"]');
    if(dictionaryButton)dictionaryButton.textContent='資料庫';
    const dictionaryTab=document.querySelector('#dictionaryTab');
    if(!dictionaryTab)return;
    let translationPane=document.querySelector('#translationDatabasePane');
    if(!translationPane){
      translationPane=document.createElement('div');
      translationPane.id='translationDatabasePane';
      while(dictionaryTab.firstChild)translationPane.append(dictionaryTab.firstChild);
      dictionaryTab.append(translationPane);
    }
    if(!document.querySelector('#databaseTypeTabs')){
      dictionaryTab.insertAdjacentHTML('afterbegin',`<div class="database-type-shell"><div class="database-type-tabs" id="databaseTypeTabs"><button class="button active" type="button" data-database-type="translations">中英對照</button><button class="button" type="button" data-database-type="people">人名連結</button></div><p class="field-hint">資料庫分成中英對照與人名連結。兩種資料都會沿用草稿、預覽、Batch Issue、衝突檢查與還原流程。</p></div>`);
    }
    if(!document.querySelector('#peopleDatabasePane'))dictionaryTab.insertAdjacentHTML('beforeend',`<div id="peopleDatabasePane" hidden><p class="muted">集中管理中英文姓名、其他拼法與學術網址。整個網站的可見文字都會精確比對；作者欄位只顯示候選，必須手動點選才會填入。</p><div class="toolbar"><div class="field" style="flex:1"><label>搜尋姓名、其他拼法或 URL</label><input id="peopleSearch" autocomplete="off"></div><button class="button" id="addPerson" type="button">新增人名</button><button class="button" id="resetPeople" type="button">放棄修改</button></div><div id="peopleStatus" class="notice"></div><div id="peopleRows" class="scroll"></div></div>`);
    document.querySelector('#databaseTypeTabs')?.addEventListener('click',event=>{const button=event.target.closest('[data-database-type]');if(button)setDatabaseType(button.dataset.databaseType);});
    document.querySelector('#peopleSearch')?.addEventListener('input',renderPeopleManager);
    document.querySelector('#addPerson')?.addEventListener('click',addPerson);
    document.querySelector('#resetPeople')?.addEventListener('click',()=>{if(confirm('放棄尚未送出的人名連結修改？')){peopleDraft=copy(peopleRemote);savePeopleLocal();}});
    document.querySelector('#peopleRows')?.addEventListener('input',event=>{
      const field=event.target.closest('[data-person-field]');if(!field)return;
      const row=field.closest('[data-person-index]'),index=Number(row?.dataset.personIndex),person=peopleDraft.people[index];if(!person)return;
      const key=field.dataset.personField;
      if(key==='name.en')person.name.en=field.value;else if(key==='name.zh')person.name.zh=field.value;else if(key==='url')person.url=field.value;else if(key==='aliases')person.aliases=field.value.split(/\n+/).map(normalizeSpace).filter(Boolean);
      savePeopleLocal(false);
    });
    document.querySelector('#peopleRows')?.addEventListener('change',()=>renderPeopleManager());
    document.querySelector('#peopleRows')?.addEventListener('click',event=>{const button=event.target.closest('[data-remove-person]');if(!button)return;const index=Number(button.dataset.removePerson);if(confirm('刪除這筆人名連結？')){peopleDraft.people.splice(index,1);savePeopleLocal();}});
    setDatabaseType(localStorage.getItem('hctsui-database-type')||'translations');
  }

  document.addEventListener('input',event=>{const input=event.target.closest('[data-author-en],[data-author-zh]');if(input&&peopleReady)showSuggestions(input);});
  document.addEventListener('focusin',event=>{const input=event.target.closest('[data-author-en],[data-author-zh]');if(input&&peopleReady&&input.value)showSuggestions(input);});
  document.addEventListener('click',event=>{const choice=event.target.closest('[data-person-id]');if(choice){chooseSuggestion(choice);return;}if(!event.target.closest('[data-author-row]'))closeSuggestions();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')closeSuggestions();});

  window.peopleDirty=peopleDirty;
  window.peopleOperation=peopleOperation;
  window.peoplePreviewHtml=peoplePreviewHtml;
  window.validatePeopleDraft=validatePeopleDraft;
  window.clearPeopleDraft=clearPeopleDraft;
  window.renderPeopleManager=renderPeopleManager;
  window.peopleHistoryPreviewHtml=function(history){return peoplePreviewHtml({before:history.before,after:history.after});};

  installStyles();installPanel();
  fetch('../content/people.json',{cache:'no-store'}).then(response=>response.ok?response.json():empty()).catch(()=>empty()).then(remote=>{
    peopleRemote=normalizePeople(remote);peopleDraft=loadSaved(peopleRemote);peopleReady=true;renderPeopleManager();
  });
})();
