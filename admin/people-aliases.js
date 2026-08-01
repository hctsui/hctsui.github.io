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

/* Reliable person-record opening across initial load, stale cache and deploy races. */
(function installReliablePeopleOpening(){
  const PENDING_KEY='hctsui-pending-person-record-v1';
  const RELOAD_KEY='hctsui-people-reload-once-v1';
  const baseOpen=window.openPeopleRecord;
  if(typeof baseOpen!=='function'||baseOpen.reliablePeopleOpeningInstalled)return;
  let serial=0;

  const esc=value=>String(value||'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  function visibleRows(){return document.querySelectorAll('#peopleRows [data-person-index]').length}
  function showError(message){
    const status=document.querySelector('#peopleStatus');
    if(status){status.className='notice error';status.innerHTML=`<strong>人名連結資料尚未正確載入。</strong>${esc(message)}`}
  }
  async function fetchCurrentPeople(){
    let lastError=null;
    for(let attempt=0;attempt<3;attempt+=1){
      try{
        const url=new URL('../content/people.json',location.href);
        url.searchParams.set('_',`${Date.now()}-${attempt}`);
        const response=await fetch(url,{cache:'no-store'});
        if(!response.ok)throw new Error(`HTTP ${response.status}`);
        const data=await response.json();
        if(!data||!Array.isArray(data.people))throw new Error('people.json 格式不正確');
        return data;
      }catch(error){lastError=error;if(attempt<2)await sleep(250*(attempt+1))}
    }
    throw lastError||new Error('無法讀取 people.json');
  }

  async function reliableOpen(personId){
    const id=String(personId||'');if(!id)return;
    const current=++serial;
    sessionStorage.setItem(PENDING_KEY,id);
    baseOpen(id);

    for(let attempt=0;attempt<45;attempt+=1){
      if(current!==serial)return;
      await sleep(Math.min(350,70+attempt*8));
      if(visibleRows()){
        sessionStorage.removeItem(PENDING_KEY);
        sessionStorage.removeItem(RELOAD_KEY);
        document.querySelector('#peopleRows [data-person-index]')?.scrollIntoView({behavior:'smooth',block:'center'});
        document.querySelector('#peopleRows input')?.focus({preventScroll:true});
        return;
      }
      baseOpen(id);
    }

    try{
      const remote=await fetchCurrentPeople();
      const exists=remote.people.some(person=>String(person?.id||'')===id);
      if(!exists){showError(`正式檔案中找不到 ID「${id}」。`);return}
      if(sessionStorage.getItem(RELOAD_KEY)!=='1'){
        sessionStorage.setItem(RELOAD_KEY,'1');
        const url=new URL(location.href);
        url.searchParams.set('_people_retry',Date.now());
        location.replace(url.href);
        return;
      }
      showError('已重新載入一次，但 Admin 仍沒有取得目前的人名資料。請確認部署完成後強制重新整理。');
    }catch(error){showError(`讀取 content/people.json 失敗：${error?.message||error}`)}
  }

  reliableOpen.reliablePeopleOpeningInstalled=true;
  window.openPeopleRecord=reliableOpen;
  const pending=sessionStorage.getItem(PENDING_KEY);
  if(pending)setTimeout(()=>reliableOpen(pending),120);
})();
