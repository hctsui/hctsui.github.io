'use strict';

/*
 * Generate common search aliases for the existing People database.
 *
 * Important:
 * - people.json intentionally remains schema_version 1.
 * - Generated aliases only affect search / author matching.
 * - They never replace the displayed English or Chinese name.
 * - The observer watches only direct row-list replacements. It must not watch
 *   the whole subtree, because updating the hint text would then trigger the
 *   observer again and create an endless render loop.
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
      const text=clean(value);
      const normalized=key(text);
      if(!text||!normalized||seen.has(normalized))continue;
      seen.add(normalized);
      result.push(text);
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
    const text=clean(name);
    if(!text)return null;

    if(text.includes(',')){
      const [surnamePart,...rest]=text.split(',');
      const surname=clean(surnamePart);
      const given=clean(rest.join(' '));
      const parts=given.split(/\s+/).filter(Boolean);
      if(!surname||!parts.length)return null;
      return {surname,first:parts[0],middle:parts.slice(1),canonical:text};
    }

    const parts=text.split(/\s+/).filter(Boolean);
    if(parts.length<2)return null;
    return {
      surname:parts.at(-1),
      first:parts[0],
      middle:parts.slice(1,-1),
      canonical:text
    };
  }

  function chineseRomanizationAliases(name){
    const text=clean(name);
    if(!text)return[];

    let surname='';
    let givenText='';

    if(text.includes(',')){
      const [surnamePart,...rest]=text.split(',');
      surname=clean(surnamePart);
      givenText=clean(rest.join(' '));
    }else{
      const tokens=text.split(/\s+/).filter(Boolean);
      if(tokens.length<2)return[];

      /*
       * Canonical records currently use given-name first:
       * Chieh-Yu Chang, Ting-Wei Chang, etc.
       */
      if(tokens.length===2&&tokens[1].includes('-')&&!tokens[0].includes('-')){
        surname=tokens[0];
        givenText=tokens[1];
      }else{
        surname=tokens.at(-1);
        givenText=tokens.slice(0,-1).join(' ');
      }
    }

    const givenParts=givenText.split(/[\s-]+/).map(clean).filter(Boolean);
    if(!surname||!givenParts.length)return[];

    const givenHyphen=givenParts.join('-');
    const givenSpace=givenParts.join(' ');
    const givenJoined=givenParts.join('');

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
    const parsed=splitWesternName(name);
    if(!parsed)return[];

    const {surname,first,middle,canonical}=parsed;
    const allGiven=[first,...middle];
    const letters=allGiven.map(initial);
    const middleLetters=middle.map(initial);
    const fullGiven=allGiven.join(' ');
    const firstAndMiddleDotted=[
      first,
      ...middleLetters.map(letter=>`${letter}.`)
    ].join(' ');
    const firstAndMiddlePlain=[first,...middleLetters].join(' ');

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
    const english=clean(enName);
    if(!english)return[];
    return clean(zhName)
      ?chineseRomanizationAliases(english)
      :foreignNameAliases(english);
  }

  function lines(value){
    return String(value||'').split(/\n+/).map(clean).filter(Boolean);
  }

  function sameLines(left,right){
    return left.length===right.length
      && left.every((value,index)=>value===right[index]);
  }

  function rowState(row){
    const enInput=row.querySelector('[data-person-field="name.en"]');
    const zhInput=row.querySelector('[data-person-field="name.zh"]');
    const aliasInput=row.querySelector('[data-person-field="aliases"]');
    if(!enInput||!zhInput||!aliasInput)return null;

    const previousEn=row.dataset[AUTO_SOURCE_EN]??enInput.value;
    const previousZh=row.dataset[AUTO_SOURCE_ZH]??zhInput.value;
    const oldAuto=new Set(automaticAliases(previousEn,previousZh).map(key));
    const manual=lines(aliasInput.value).filter(value=>!oldAuto.has(key(value)));

    return {
      row,
      enInput,
      zhInput,
      aliasInput,
      manual,
      generated:automaticAliases(enInput.value,zhInput.value)
    };
  }

  function syncAll(){
    scheduled=false;
    if(syncing)return;

    /*
     * A filtered list does not contain every person, so collision checking
     * would be incomplete. Wait until the full list is visible.
     */
    if(clean(document.querySelector('#peopleSearch')?.value))return;

    syncing=true;
    try{
      const states=[...document.querySelectorAll(`#peopleRows ${ROW_SELECTOR}`)]
        .map(rowState)
        .filter(Boolean);

      const reserved=new Map();
      const generatedOwners=new Map();

      const claim=(map,value,index)=>{
        const normalized=key(value);
        if(!normalized)return;
        let owners=map.get(normalized);
        if(!owners){
          owners=new Set();
          map.set(normalized,owners);
        }
        owners.add(index);
      };

      states.forEach((state,index)=>{
        claim(reserved,state.enInput.value,index);
        claim(reserved,state.zhInput.value,index);
        state.manual.forEach(value=>claim(reserved,value,index));
        state.generated.forEach(value=>claim(generatedOwners,value,index));
      });

      states.forEach((state,index)=>{
        const allowed=state.generated.filter(value=>{
          const normalized=key(value);
          const generated=generatedOwners.get(normalized);
          const occupied=reserved.get(normalized);
          return generated?.size===1
            &&(!occupied||[...occupied].every(owner=>owner===index));
        });

        const merged=unique(
          [...state.manual,...allowed],
          [state.enInput.value,state.zhInput.value]
        );

        state.row.dataset[AUTO_SOURCE_EN]=state.enInput.value;
        state.row.dataset[AUTO_SOURCE_ZH]=state.zhInput.value;
        state.row.dataset.autoAliasCount=String(allowed.length);

        const hint=state.aliasInput.closest('.field')?.querySelector('.field-hint');
        const hintText=`其他拼法只用於搜尋與作者比對，不會改變網站顯示。系統已依姓名自動加入 ${allowed.length} 種不衝突的常見拼法，可在此增刪。`;

        /*
         * Avoid mutating the DOM when the text is already correct.
         */
        if(hint&&hint.textContent!==hintText)hint.textContent=hintText;

        if(sameLines(lines(state.aliasInput.value),merged))return;

        state.aliasInput.value=merged.join('\n');
        state.aliasInput.dispatchEvent(new Event('input',{bubbles:true}));
      });
    }finally{
      syncing=false;
    }
  }

  function schedule(){
    if(scheduled)return;
    scheduled=true;
    queueMicrotask(syncAll);
  }

  document.addEventListener('input',event=>{
    const field=event.target.closest(
      '[data-person-field="name.en"],[data-person-field="name.zh"]'
    );
    if(field?.closest(ROW_SELECTOR))schedule();
  });

  document.addEventListener('input',event=>{
    if(event.target.matches('#peopleSearch')&&!clean(event.target.value)){
      setTimeout(schedule,0);
    }
  });

  document.addEventListener('click',event=>{
    if(event.target.closest('[data-database-type="people"]')){
      setTimeout(schedule,0);
    }
  });

  function installObserver(){
    const root=document.querySelector('#peopleRows');
    if(!root||root.dataset.peopleAliasObserverInstalled)return false;

    root.dataset.peopleAliasObserverInstalled='1';

    /*
     * Observe only replacement/addition/removal of person rows.
     * Do NOT use subtree:true: hint text changes live inside the rows and would
     * otherwise cause the observer to trigger itself forever.
     */
    new MutationObserver(schedule).observe(root,{childList:true});
    schedule();
    return true;
  }

  if(!installObserver()){
    const observer=new MutationObserver(()=>{
      if(installObserver())observer.disconnect();
    });
    observer.observe(document.body,{childList:true,subtree:true});
  }

  window.peopleAutomaticAliases=automaticAliases;
})();
