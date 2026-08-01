'use strict';

/* One canonical personal-profile form. The batch processor synchronizes these
   values to all managed profile/contact items after submission. */
(function installPersonalProfileManager(){
  const DRAFT_KEY='hctsui-personal-profile-draft-v1';
  const PROFILE_CATEGORY_ID='personal-profile';
  const KEY_LABELS={name:'Name／姓名',affiliation:'Affiliation／所屬單位',position:'Position／職位'};
  let profileBase=null,profileDraft=null,profileReady=false;

  const copy=value=>structuredClone(value);
  const own=(object,key)=>Object.prototype.hasOwnProperty.call(object||{},key);
  const pair=(value,fallback={en:'',zh:''})=>({en:String(own(value,'en')?value.en:fallback.en||'').trim(),zh:String(own(value,'zh')?value.zh:fallback.zh||'').trim()});
  const stable=value=>JSON.stringify(value&&typeof value==='object'?Object.keys(value).sort().reduce((out,key)=>(out[key]=value[key]&&typeof value[key]==='object'&&!Array.isArray(value[key])?JSON.parse(stable(value[key])):value[key],out),{}):value);
  function findItem(id){return (site?.profile_items||[]).find(item=>item?.id===id)||null}
  function description(id){return pair(findItem(id)?.description)}
  function inferProfile(){
    const source=site?.settings?.personal_profile||{},seoName=site?.settings?.seo?.site_name||{};
    return {
      schema_version:1,
      name:pair(source.name,pair(seoName,{en:'Hung-Chun Tsui',zh:'崔鴻竣'})),
      affiliation:pair(source.affiliation,description('contact-affiliation')),
      position:pair(source.position,description('profile-position').en||description('profile-position').zh?description('profile-position'):{en:'PhD Student',zh:'博士生'}),
      institutional_email:String(source.institutional_email||findItem('contact-institutional-email')?.description?.en||'').trim(),
      personal_email:String(source.personal_email||findItem('contact-personal-email')?.description?.en||'').trim(),
      website:String(source.website||findItem('personal-website')?.description?.en||findItem('personal-website')?.url||'https://hctsui.github.io').trim(),
      orcid:String(source.orcid||findItem('personal-orcid')?.description?.en||'').trim(),
      address:pair(source.address,description('personal-address')),
      office:pair(source.office,description('contact-address-office')),
      languages:pair(source.languages,description('personal-languages')),
    };
  }
  function normalize(value){
    const fallback=inferProfile(),source=value&&typeof value==='object'?value:{};
    return {schema_version:1,name:pair(source.name,fallback.name),affiliation:pair(source.affiliation,fallback.affiliation),position:pair(source.position,fallback.position),institutional_email:String('institutional_email'in source?source.institutional_email:fallback.institutional_email).trim(),personal_email:String('personal_email'in source?source.personal_email:fallback.personal_email).trim(),website:String('website'in source?source.website:fallback.website).trim(),orcid:String('orcid'in source?source.orcid:fallback.orcid).trim(),address:pair(source.address,fallback.address),office:pair(source.office,fallback.office),languages:pair(source.languages,fallback.languages)};
  }

  function placementRows(value,primary=''){
    const seen=new Set(),rows=[];
    for(const [index,row] of (Array.isArray(value)?value:[]).entries()){
      const categoryId=String(typeof row==='string'?row:row?.category_id||'');
      if(!categoryId||categoryId===primary||seen.has(categoryId))continue;
      seen.add(categoryId);rows.push({category_id:categoryId,order:Number.isFinite(Number(row?.order))?Number(row.order):index});
    }
    return rows;
  }
  function ensureSiteProfileCategory(){
    site.settings=site.settings||{};const categories=Array.isArray(site.settings.categories)?site.settings.categories:(site.settings.categories=[]);
    let category=categories.find(row=>row?.id===PROFILE_CATEGORY_ID);
    if(!category){category={id:PROFILE_CATEGORY_ID,page_id:'cv',kind:'mixed',label:{en:'Profile',zh:'個人資料'},title:{en:'Personal Information',zh:'個人資料'},intro:{en:'',zh:''},order:categories.filter(row=>row?.page_id==='cv').length,show_on_web:false,show_on_cv:false};categories.push(category)}
    category.kind='mixed';category.page_id=category.page_id||'cv';category.label=pair(category.label,{en:'Profile',zh:'個人資料'});category.title=pair(category.title,{en:'Personal Information',zh:'個人資料'});category.intro=pair(category.intro);category.show_on_web=false;category.show_on_cv=false;return category;
  }
  function upsertProfileItem(items,id){let item=items.find(row=>row?.id===id);if(!item){item={id};items.push(item)}return item}
  function setProfileItem(item,{type,title,description,key,style,url='',defaults=[],order}){
    const merged=new Map(placementRows(item.display_placements,PROFILE_CATEGORY_ID).map(row=>[row.category_id,row]));
    for(const row of defaults)if(!merged.has(row.category_id))merged.set(row.category_id,row);
    if(key==='affiliation')merged.delete('home-contact');
    Object.assign(item,{type,category_id:PROFILE_CATEGORY_ID,order,title:pair(title),description:pair(description),personal_key:key,display_style:style,display_placements:[...merged.values()]});
    if(url)item.url=url;else delete item.url;
  }
  function syncClientProfileData(profile){
    if(!site)return;site.settings=site.settings||{};site.settings.personal_profile=copy(profile);ensureSiteProfileCategory();
    const items=Array.isArray(site.profile_items)?site.profile_items:(site.profile_items=[]),managed=new Set(['profile-name','contact-affiliation','profile-position','contact-institutional-email','contact-personal-email','contact-address-office','personal-languages','personal-address','personal-email','personal-website','personal-orcid']);
    for(const item of items){
      if(!item||(!managed.has(item.id)&&!['personal','contact'].includes(item.type)))continue;
      const old=String(item.category_id||''),rows=placementRows(item.display_placements,PROFILE_CATEGORY_ID);
      if(old&&old!==PROFILE_CATEGORY_ID&&!(item.id==='contact-affiliation'&&old==='home-contact')&&!rows.some(row=>row.category_id===old))rows.push({category_id:old,order:Number(item.order)||0});
      item.category_id=PROFILE_CATEGORY_ID;item.display_placements=rows;
    }
    const combined=[profile.institutional_email,profile.personal_email].filter(Boolean).join(' | '),orcidUrl=profile.orcid?(String(profile.orcid).startsWith('http')?profile.orcid:`https://orcid.org/${profile.orcid}`):'';
    const specs=[
      ['profile-name',{type:'personal',title:{en:'Name',zh:'姓名'},description:profile.name,key:'name',style:'contact',order:0}],
      ['contact-affiliation',{type:'personal',title:{en:'Affiliation',zh:'所屬單位'},description:profile.affiliation,key:'affiliation',style:'contact',order:1}],
      ['profile-position',{type:'personal',title:{en:'Position',zh:'職位'},description:profile.position,key:'position',style:'contact',order:2}],
      ['contact-institutional-email',{type:'contact',title:{en:'Institutional email',zh:'學校信箱'},description:{en:profile.institutional_email,zh:profile.institutional_email},key:'institutional_email',style:'contact',url:profile.institutional_email?`mailto:${profile.institutional_email}`:'',defaults:[{category_id:'home-contact',order:0}],order:3}],
      ['contact-personal-email',{type:'contact',title:{en:'Personal email',zh:'個人信箱'},description:{en:profile.personal_email,zh:profile.personal_email},key:'personal_email',style:'contact',url:profile.personal_email?`mailto:${profile.personal_email}`:'',defaults:[{category_id:'home-contact',order:1}],order:4}],
      ['contact-address-office',{type:'contact',title:{en:'Address & office',zh:'地址與辦公室'},description:profile.office,key:'office',style:'contact',defaults:[{category_id:'home-contact',order:2}],order:5}],
      ['personal-languages',{type:'personal',title:{en:'Languages',zh:'語言'},description:profile.languages,key:'languages',style:'personal',defaults:[{category_id:'cv-personal',order:0}],order:6}],
      ['personal-address',{type:'personal',title:{en:'Address',zh:'地址'},description:profile.address,key:'address',style:'personal',defaults:[{category_id:'cv-personal',order:1}],order:7}],
      ['personal-email',{type:'personal',title:{en:'Email',zh:'電子郵件'},description:{en:combined,zh:combined},key:'email',style:'personal',defaults:[{category_id:'cv-personal',order:2}],order:8}],
      ['personal-website',{type:'personal',title:{en:'Website',zh:'網站'},description:{en:profile.website,zh:profile.website},key:'website',style:'personal',url:profile.website,defaults:[{category_id:'cv-personal',order:3}],order:9}],
      ['personal-orcid',{type:'personal',title:{en:'ORCID',zh:'ORCID'},description:{en:profile.orcid,zh:profile.orcid},key:'orcid',style:'personal',url:orcidUrl,defaults:[{category_id:'cv-personal',order:4}],order:10}],
    ];
    for(const [id,spec] of specs)setProfileItem(upsertProfileItem(items,id),spec);
  }
  function ensureCategory(){
    if(typeof initLayoutState!=='function'||!site)return;ensureSiteProfileCategory();initLayoutState();
    const category=copy(site.settings.categories.find(row=>row.id===PROFILE_CATEGORY_ID));
    const migrateBundle=bundle=>{
      if(!bundle.categories.some(row=>row.id===PROFILE_CATEGORY_ID))bundle.categories.push(copy(category));
      bundle.assignments=bundle.assignments||{};bundle.placements=bundle.placements||{};
      for(const item of site.profile_items||[]){
        if(!item?.id)continue;
        if(item.category_id===PROFILE_CATEGORY_ID||['personal','contact'].includes(item.type)){
          bundle.assignments[item.id]={category_id:PROFILE_CATEGORY_ID,order:Number(item.order)||0};
          bundle.placements[item.id]=placementRows(item.display_placements,PROFILE_CATEGORY_ID);
        }
      }
      return normalizeLayoutBundle(bundle);
    };
    layoutBase=migrateBundle(layoutBase);layoutDraft=migrateBundle(layoutDraft);
  }
  function init(){
    if(profileReady||!site)return;profileBase=normalize(inferProfile());syncClientProfileData(profileBase);profileDraft=copy(profileBase);
    try{const saved=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');if(saved?.base_signature===stable(profileBase)&&saved?.draft)profileDraft=normalize(saved.draft);else if(saved)localStorage.removeItem(DRAFT_KEY)}catch{localStorage.removeItem(DRAFT_KEY)}
    profileReady=true;ensureCategory();
  }
  function dirty(){init();return stable(profileDraft)!==stable(profileBase)}
  function saveLocal(message='已儲存個人資料草稿'){init();if(dirty())localStorage.setItem(DRAFT_KEY,JSON.stringify({base_signature:stable(profileBase),draft:profileDraft}));else localStorage.removeItem(DRAFT_KEY);flash(message);renderAll()}
  function profileOperation(){return{op:'personal_profile',before:copy(profileBase),after:copy(profileDraft)}}

  function fieldPair(label,key,textarea=false){
    const en=esc(profileDraft[key]?.en||''),zh=esc(profileDraft[key]?.zh||'');
    const control=(lang,value)=>textarea
      ?`<textarea data-profile-field="${key}.${lang}">${value}</textarea>`
      :`<input data-profile-field="${key}.${lang}" value="${value}">`;
    return `<div class="pair-grid"><div class="field"><label>${label}（英文）</label>${control('en',en)}</div><div class="field"><label>${label}（中文）</label>${control('zh',zh)}</div></div>`;
  }
  function setInputValues(root){root.querySelectorAll('input[data-profile-field]').forEach(input=>{const [key,lang]=input.dataset.profileField.split('.');input.value=lang?profileDraft[key][lang]:profileDraft[key]||''})}
  function profilePlacementHtml(){
    if(typeof layoutDraft==='undefined'||!layoutDraft)return'';
    const excluded=new Set(['featured_publications','upcoming']),items=(site.profile_items||[]).filter(item=>item?.personal_key),categories=layoutDraft.categories.filter(category=>category.id!==PROFILE_CATEGORY_ID&&!excluded.has(category.kind));
    const rows=items.map(item=>{
      const current=new Set((layoutDraft.placements?.[item.id]||item.display_placements||[]).map(row=>String(row.category_id||'')));
      const allowed=categories.filter(category=>(category.kind==='mixed'||category.kind===item.type||category.kind===item.display_style)&&!(item.personal_key==='affiliation'&&category.id==='home-contact'));
      if(!allowed.length)return'';
      return `<details class="profile-placement-row" data-profile-placement-item="${esc(item.id)}"><summary><strong>${esc(item.title?.zh||item.title?.en||item.id)}</strong><span class="muted">${current.size} 個額外位置</span></summary><div class="placement-options">${allowed.map(category=>`<label class="switch"><input type="checkbox" value="${esc(category.id)}" ${current.has(category.id)?'checked':''}><span>${esc(pageName(category.page_id))} → ${esc(categoryName(category))}</span></label>`).join('')}</div></details>`;
    }).filter(Boolean).join('');
    return rows?`<details class="personal-profile-placements"><summary><strong>個人資料顯示位置</strong><span class="muted">主要資料統一放在「個人資料」類別；這裡只設定額外引用。</span></summary><div>${rows}</div></details>`:'';
  }
  function applyProfilePlacements(root){
    if(typeof layoutDraft==='undefined'||!layoutDraft)return;
    layoutDraft.placements=layoutDraft.placements||{};
    root.querySelectorAll('[data-profile-placement-item]').forEach(group=>{
      const id=group.dataset.profilePlacementItem,old=new Map((layoutDraft.placements[id]||[]).map(row=>[row.category_id,Number(row.order)||0]));
      layoutDraft.placements[id]=[...group.querySelectorAll('input[type="checkbox"]:checked')].map((input,index)=>({category_id:input.value,order:old.has(input.value)?old.get(input.value):index}));
    });
    layoutDraft=normalizeLayoutBundle(layoutDraft);
  }
  function formHtml(){
    init();return `<h3>個人資料編輯</h3><div class="notice"><strong>這裡是個人資料的唯一來源。</strong><p>儲存並送出後，Name、Affiliation、Position、Email、Website、ORCID、地址與語言會同步到所有引用位置。項目本身統一歸在「個人資料」類別，其他頁面只保留引用。</p></div>
      ${fieldPair('姓名','name')}${fieldPair('所屬單位','affiliation',true)}${fieldPair('職位','position')}
      <div class="pair-grid"><div class="field"><label>學校信箱</label><input data-profile-field="institutional_email" type="email"></div><div class="field"><label>個人信箱</label><input data-profile-field="personal_email" type="email"></div></div>
      <div class="pair-grid"><div class="field"><label>個人網站</label><input data-profile-field="website" placeholder="https://..."></div><div class="field"><label>ORCID</label><input data-profile-field="orcid" placeholder="0000-0000-0000-0000"></div></div>
      ${fieldPair('地址','address',true)}${fieldPair('辦公室／聯絡地址','office',true)}${fieldPair('語言','languages',true)}
      ${profilePlacementHtml()}
      <div class="actions"><button class="button primary" id="savePersonalProfileDraft">儲存個人資料草稿</button><button class="button" id="resetPersonalProfileDraft">還原目前網站資料</button></div>`;
  }
  function openForm(){
    init();const box=document.createElement('div');box.innerHTML=formHtml();$('#addEditor').replaceChildren(box);currentEditor={type:'personal_profile',record:null,root:box};setInputValues(box);switchTab('add');
    box.querySelector('#savePersonalProfileDraft').onclick=()=>{const next=copy(profileDraft);box.querySelectorAll('[data-profile-field]').forEach(input=>{const path=input.dataset.profileField.split('.');if(path.length===2)next[path[0]][path[1]]=input.value.trim();else next[path[0]]=input.value.trim()});if(!next.name.en||!next.name.zh)return flash('姓名的中英文都不能留白');applyProfilePlacements(box);profileDraft=normalize(next);saveLocal();if(typeof saveLayoutDraft==='function'&&layoutDirty())saveLayoutDraft('已儲存個人資料與顯示位置草稿')};
    box.querySelector('#resetPersonalProfileDraft').onclick=()=>{profileDraft=copy(profileBase);localStorage.removeItem(DRAFT_KEY);if(typeof layoutDraft!=='undefined'&&layoutDraft&&layoutBase){for(const item of site.profile_items||[])if(item?.personal_key)layoutDraft.placements[item.id]=copy(layoutBase.placements?.[item.id]||[]);layoutDraft=normalizeLayoutBundle(layoutDraft)}openForm();renderAll();flash('已還原目前網站的個人資料與顯示位置')};
  }

  function injectSettingsButton(){
    const tab=document.querySelector('#siteSettingsTab');if(!tab||tab.querySelector('[data-personal-profile-settings]'))return;
    const card=document.createElement('div');card.className='notice personal-profile-settings-card';card.dataset.personalProfileSettings='';card.innerHTML='<div><strong>個人資料</strong><p>集中管理姓名、所屬單位、職位、Email、網站、ORCID、地址與語言。</p></div><button class="button primary" type="button" data-open-personal-profile>個人資料編輯</button>';tab.prepend(card);card.querySelector('button').onclick=openForm;
  }
  new MutationObserver(injectSettingsButton).observe(document.body,{childList:true,subtree:true});setTimeout(injectSettingsButton,0);

  const baseLayoutCatalogRecords=layoutCatalogRecords;
  layoutCatalogRecords=function(){
    init();const rows=baseLayoutCatalogRecords(),data=typeof effectiveSite==='function'?effectiveSite():site,actual=data?.profile_items||[];
    const specs=[['name','profile-name',{en:'Name',zh:'姓名'}],['affiliation','contact-affiliation',{en:'Affiliation',zh:'所屬單位'}],['position','profile-position',{en:'Position',zh:'職位'}]];
    for(const [key,id,title] of specs)if(!actual.some(item=>item?.id===id))rows.push({id:`personal-profile:${key}`,type:'personal',_personal_profile_key:key,title:copy(title),description:copy(profileDraft[key]),category_id:PROFILE_CATEGORY_ID,order:-20+specs.findIndex(row=>row[0]===key)});
    return rows;
  };

  const baseOpenEditor=openEditor;
  openEditor=function(type,record,options={}){if(record?._personal_profile_key||['name','affiliation','position'].includes(record?.personal_key)){openForm();return}return baseOpenEditor(type,record,options)};

  const basePayload=payload;
  payload=function(){const result=basePayload();if(dirty())result.operations.push(profileOperation());return result};

  const baseRenderDrafts=renderDrafts;
  renderDrafts=function(){baseRenderDrafts();if(!dirty())return;const box=$('#drafts');if(!box||box.querySelector('[data-personal-profile-draft]'))return;const empty=box.querySelector('.muted:only-child');if(empty&&/尚無草稿/.test(empty.textContent||''))empty.remove();box.insertAdjacentHTML('beforeend','<div class="row draft-row" data-personal-profile-draft><span class="tag">個人資料</span><strong>個人資料主檔</strong><span class="muted">會同步更新所有個人資料項目與引用位置。</span><div class="actions"><button class="button" data-edit-personal-profile>修改草稿</button><button class="button danger" data-drop-personal-profile>移除</button></div></div>')};
  document.querySelector('#drafts')?.addEventListener('click',event=>{const button=event.target.closest('button');if(button?.hasAttribute('data-edit-personal-profile'))openForm();else if(button?.hasAttribute('data-drop-personal-profile')){profileDraft=copy(profileBase);localStorage.removeItem(DRAFT_KEY);renderAll();flash('已移除個人資料草稿')}});

  const baseRenderPreview=renderPreview;
  renderPreview=function(refreshDictionary=true){baseRenderPreview(refreshDictionary);if(dirty()){const fields=[];for(const key of ['name','affiliation','position','institutional_email','personal_email','website','orcid','address','office','languages'])if(stable(profileBase[key])!==stable(profileDraft[key]))fields.push(KEY_LABELS[key]||key);$('#preview').insertAdjacentHTML('beforeend',`<details class="diff"><summary><strong>個人資料</strong>：${esc(fields.join('、')||'有變更')}</summary><div class="preview-card"><dl class="profile-draft-preview"><dt>Name</dt><dd>${esc(profileDraft.name.en)}／${esc(profileDraft.name.zh)}</dd><dt>Affiliation</dt><dd>${esc(profileDraft.affiliation.en)}／${esc(profileDraft.affiliation.zh)}</dd><dt>Position</dt><dd>${esc(profileDraft.position.en)}／${esc(profileDraft.position.zh)}</dd></dl></div></details>`);$('#payload').textContent=JSON.stringify(payload(),null,2)}};

  const baseClearSubmittedDraft=clearSubmittedDraft;
  clearSubmittedDraft=function(){localStorage.removeItem(DRAFT_KEY);profileReady=false;return baseClearSubmittedDraft()};

  const style=document.createElement('style');style.textContent=`.personal-profile-settings-card{display:flex;align-items:center;justify-content:space-between;gap:14px}.personal-profile-settings-card p{margin:.25rem 0 0}.profile-draft-preview{display:grid;grid-template-columns:110px 1fr;gap:7px;margin:0}.profile-draft-preview dt{font-weight:800;color:#6e625a}.profile-draft-preview dd{margin:0}.personal-profile-placements{margin:14px 0;border:1px solid #ded3ca;border-radius:12px;padding:10px}.personal-profile-placements>summary,.profile-placement-row>summary{cursor:pointer;display:flex;justify-content:space-between;gap:10px}.profile-placement-row{padding:9px 0;border-top:1px solid #eee5de}.profile-placement-row:first-child{border-top:0}.profile-placement-row .placement-options{display:grid;gap:5px;margin-top:8px}.profile-placement-row .switch{margin:0}@media(max-width:650px){.personal-profile-settings-card{align-items:flex-start;flex-direction:column}.profile-draft-preview{grid-template-columns:1fr}}`;document.head.append(style);

  if(site){init();renderAll()}
})();
