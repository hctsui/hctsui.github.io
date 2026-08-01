'use strict';

/* Generate common name variants in the existing "其他拼法" field.
   The variants participate in the canonical people.js search and exact-match
   flow, but never replace the displayed English or Chinese name. */
(function installAutomaticPeopleAliases(){
  const ROW_SELECTOR='[data-person-index]';
  const AUTO_SOURCE_EN='autoAliasSourceEn';
  const AUTO_SOURCE_ZH='autoAliasSourceZh';
  let scheduled=false;

  const clean=value=>String(value||'').trim().replace(/\s+/g,' ');
  const key=value=>clean(value).normalize('NFKC').toLowerCase().replace(/\s*[-–—]\s*/g,'-');
  const unique=(values,excluded=[])=>{
    const seen=new Set(excluded.map(key).filter(Boolean)),result=[];
    for(const value of values){const text=clean(value),normalized=key(text);if(!text||!normalized||seen.has(normalized))continue;seen.add(normalized);result.push(text)}
    return result;
  };
  const initial=token=>{const match=clean(token).match(/[\p{L}\p{N}]/u);return match?match[0].toUpperCase():''};
  const dotted=letters=>letters.filter(Boolean).map(letter=>`${letter}.`).join(' ');
  const plain=letters=>letters.filter(Boolean).join(' ');

  function splitWesternName(name){
    const text=clean(name);if(!text)return null;
    if(text.includes(',')){
      const [surnamePart,...rest]=text.split(','),surname=clean(surnamePart),given=clean(rest.join(' ')),parts=given.split(/\s+/).filter(Boolean);
      if(!surname||!parts.length)return null;
      return {surname,first:parts[0],middle:parts.slice(1),canonical:text};
    }
    const parts=text.split(/\s+/).filter(Boolean);if(parts.length<2)return null;
    return {surname:parts.at(-1),first:parts[0],middle:parts.slice(1,-1),canonical:text};
  }

  function chineseRomanizationAliases(name){
    const text=clean(name);if(!text)return[];
    let surname='',givenText='';
    if(text.includes(',')){
      const [surnamePart,...rest]=text.split(',');surname=clean(surnamePart);givenText=clean(rest.join(' '));
    }else{
      const tokens=text.split(/\s+/).filter(Boolean);if(tokens.length<2)return[];
      if(tokens.length===2&&tokens[1].includes('-')&&!tokens[0].includes('-')){surname=tokens[0];givenText=tokens[1]}
      else{surname=tokens.at(-1);givenText=tokens.slice(0,-1).join(' ')}
    }
    const givenParts=givenText.split(/[\s-]+/).map(clean).filter(Boolean);if(!surname||!givenParts.length)return[];
    const givenHyphen=givenParts.join('-'),givenSpace=givenParts.join(' '),givenJoined=givenParts.join('');
    return unique([
      `${givenHyphen} ${surname}`,
      `${givenSpace} ${surname}`,
      `${givenJoined} ${surname}`,
      `${surname} ${givenHyphen}`,
      `${surname}, ${givenHyphen}`,
      `${surname} ${givenSpace}`,
      `${surname}, ${givenSpace}`,
      `${surname} ${givenJoined}`,
      `${surname}, ${givenJoined}`,
    ],[text]);
  }

  function foreignNameAliases(name){
    const parsed=splitWesternName(name);if(!parsed)return[];
    const {surname,first,middle,canonical}=parsed,allGiven=[first,...middle],letters=allGiven.map(initial),middleLetters=middle.map(initial);
    const fullGiven=allGiven.join(' '),firstAndMiddleDotted=[first,...middleLetters.map(letter=>`${letter}.`)].join(' '),firstAndMiddlePlain=[first,...middleLetters].join(' ');
    const values=[
      `${fullGiven} ${surname}`,
      `${surname}, ${fullGiven}`,
      `${surname} ${fullGiven}`,
      `${first} ${surname}`,
      `${surname}, ${first}`,
      `${surname} ${first}`,
      `${dotted(letters)} ${surname}`,
      `${plain(letters)} ${surname}`,
      `${surname}, ${dotted(letters)}`,
      `${surname}, ${plain(letters)}`,
      `${initial(first)}. ${surname}`,
      `${initial(first)} ${surname}`,
    ];
    if(middle.length){
      values.push(
        `${firstAndMiddleDotted} ${surname}`,
        `${firstAndMiddlePlain} ${surname}`,
        `${surname}, ${firstAndMiddleDotted}`,
        `${surname}, ${firstAndMiddlePlain}`,
      );
    }
    return unique(values,[canonical]);
  }

  function automaticAliases(enName,zhName){
    const english=clean(enName);if(!english)return[];
    return clean(zhName)?chineseRomanizationAliases(english):foreignNameAliases(english);
  }

  function lines(value){return String(value||'').split(/\n+/).map(clean).filter(Boolean)}
  function sameLines(left,right){return left.length===right.length&&left.every((value,index)=>value===right[index])}

  function rowState(row){
    const enInput=row.querySelector('[data-person-field="name.en"]'),zhInput=row.querySelector('[data-person-field="name.zh"]'),aliasInput=row.querySelector('[data-person-field="aliases"]');
    if(!enInput||!zhInput||!aliasInput)return null;
    const previousEn=row.dataset[AUTO_SOURCE_EN]??enInput.value,previousZh=row.dataset[AUTO_SOURCE_ZH]??zhInput.value;
    const oldAuto=new Set(automaticAliases(previousEn,previousZh).map(key));
    const manual=lines(aliasInput.value).filter(value=>!oldAuto.has(key(value)));
    return {row,enInput,zhInput,aliasInput,manual,generated:automaticAliases(enInput.value,zhInput.value)};
  }

  function syncAll(){
    scheduled=false;
    const states=[...document.querySelectorAll(`#peopleRows ${ROW_SELECTOR}`)].map(rowState).filter(Boolean);
    const reserved=new Map(),generatedOwners=new Map();
    const claim=(map,value,index)=>{const normalized=key(value);if(!normalized)return;let owners=map.get(normalized);if(!owners)map.set(normalized,owners=new Set());owners.add(index)};
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
      state.row.dataset.autoAliasCount=String(allowed.length);
      const hint=state.aliasInput.closest('.field')?.querySelector('.field-hint');
      if(hint)hint.textContent=`其他拼法只用於搜尋與作者比對，不會改變網站顯示。系統已依姓名自動加入 ${allowed.length} 種不衝突的常見拼法，可在此增刪。`;
      if(sameLines(lines(state.aliasInput.value),merged))return;
      state.aliasInput.value=merged.join('\n');
      state.aliasInput.dispatchEvent(new Event('input',{bubbles:true}));
    });
  }

  function schedule(){if(scheduled)return;scheduled=true;queueMicrotask(syncAll)}

  document.addEventListener('input',event=>{
    const field=event.target.closest('[data-person-field="name.en"],[data-person-field="name.zh"]');if(!field)return;
    if(field.closest(ROW_SELECTOR))schedule();
  });
  document.addEventListener('click',event=>{
    const databaseButton=event.target.closest('[data-database-type="people"]');if(databaseButton)setTimeout(schedule,0);
  });

  const installObserver=()=>{
    const root=document.querySelector('#peopleRows');if(!root)return false;
    new MutationObserver(schedule).observe(root,{childList:true,subtree:true});schedule();return true;
  };
  if(!installObserver()){
    const observer=new MutationObserver(()=>{if(installObserver())observer.disconnect()});
    observer.observe(document.body,{childList:true,subtree:true});
  }

  window.peopleAutomaticAliases=automaticAliases;
})();
