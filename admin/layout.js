'use strict';

/* Schema 3 page/category manager. This script intentionally sits outside the
   large legacy Admin script so the old content editor remains stable. */
const LAYOUT_DRAFT_KEY='hctsui-layout-draft-v3';
const CATEGORY_KIND_LABELS={
  featured_publications:'首頁精選論文',upcoming:'首頁近期活動',contact:'聯絡資訊',
  interest:'一般內容',education:'一般內容',honor:'榮譽',publication:'作品',
  visit:'學術訪問',talk:'學術報告',organization:'學術活動',conference:'學術會議',
  teaching:'教學',personal:'一般內容',generic:'一般內容'
};
const DIRECT_CATEGORY_KINDS=new Set(['contact','interest','education','honor','publication','visit','talk','organization','conference','teaching','personal','generic']);
const GENERAL_CATEGORY_KINDS=new Set(['contact','interest','education','honor','personal','generic']);
const GENERAL_FORMAT_ORDER=['generic','education','interest','contact','personal','honor'];
const GENERAL_FORMAT_LABELS={
  generic:'標準時間軸',
  education:'雙欄紀錄',
  interest:'標題清單',
  contact:'資訊卡片',
  personal:'標籤列表',
  honor:'精簡時間軸'
};
const ITEM_KIND={conference:'conference',talk:'talk',visit:'visit',organization:'organization',honor:'honor',publication:'publication',teaching:'teaching',interest:'interest',education:'education',generic:'generic',contact:'contact',personal:'personal'};
let layoutBase=null,layoutDraft=null,layoutReady=false,layoutPreviewSuppressed=false,layoutManagerPageId='';

function layoutPair(value){return{en:String(value?.en||''),zh:String(value?.zh||'')}}
function layoutItems(data){return allRecords(data||{}).filter(x=>x&&x.id)}
function layoutBundle(data){
  const settings=data?.settings||{};
  return normalizeLayoutBundle({
    pages:clone(settings.pages||[]),
    categories:clone(settings.categories||[]),
    cv_category_order:clone(settings.cv_category_order||[]),
    assignments:Object.fromEntries(layoutItems(data).map(x=>[String(x.id),{category_id:String(x.category_id||''),order:Number.isFinite(Number(x.order))?Number(x.order):999999}]))
  });
}
function normalizeLayoutBundle(bundle){
  const result={pages:clone(bundle?.pages||[]),categories:clone(bundle?.categories||[]),cv_category_order:clone(bundle?.cv_category_order||[]),assignments:clone(bundle?.assignments||{})};
  const defaultPageColors={home:'#a34f3b',cv:'#8b5a2b',publications:'#315f9b',activities:'#176b52',teaching:'#b14b86'};
  result.pages.sort((a,b)=>(Number(a.order)||0)-(Number(b.order)||0)||String(a.id).localeCompare(String(b.id)));
  result.pages.forEach((p,i)=>{p.order=i;p.name=layoutPair(p.name);p.path=layoutPair(p.path);p.languages=['en','zh'].filter(lang=>(Array.isArray(p.languages)?p.languages:['en','zh']).includes(lang));if(!p.languages.length)p.languages=['en','zh'];p.color=/^#[0-9a-f]{6}$/i.test(String(p.color||''))?String(p.color).toLowerCase():(defaultPageColors[p.id]||'#8b3d2e');p.show_in_navigation=p.show_in_navigation!==false;if(p.header){p.header={label:layoutPair(p.header.label),title:layoutPair(p.header.title),intro:layoutPair(p.header.intro)}}});
  const pageRank=new Map(result.pages.map((p,i)=>[p.id,i]));
  result.categories.sort((a,b)=>(pageRank.get(a.page_id)??999)-(pageRank.get(b.page_id)??999)||(Number(a.order)||0)-(Number(b.order)||0)||String(a.id).localeCompare(String(b.id)));
  const counters={};
  result.categories.forEach(c=>{c.label=layoutPair(c.label);c.title=layoutPair(c.title);c.intro=layoutPair(c.intro);c.show_on_web=c.show_on_web!==false;c.show_on_cv=!!c.show_on_cv;c.order=counters[c.page_id]||0;counters[c.page_id]=c.order+1});
  const known=new Set(result.categories.filter(c=>c.show_on_cv).map(c=>c.id));
  result.cv_category_order=[...new Set(result.cv_category_order.filter(id=>known.has(id)))];
  result.categories.filter(c=>c.show_on_cv).forEach(c=>{if(!result.cv_category_order.includes(c.id))result.cv_category_order.push(c.id)});
  const byCategory={};
  for(const [id,state] of Object.entries(result.assignments)){
    result.assignments[id]={category_id:String(state?.category_id||''),order:Number.isFinite(Number(state?.order))?Number(state.order):999999};
    (byCategory[result.assignments[id].category_id]??=[]).push(id);
  }
  for(const ids of Object.values(byCategory)){
    ids.sort((a,b)=>result.assignments[a].order-result.assignments[b].order||a.localeCompare(b));
    ids.forEach((id,i)=>result.assignments[id].order=i);
  }
  return result;
}
function layoutSignature(bundle){return JSON.stringify(normalizeLayoutBundle(bundle))}
function layoutStructuralSignature(bundle){return JSON.stringify({pages:normalizeLayoutBundle(bundle).pages,categories:normalizeLayoutBundle(bundle).categories,cv_category_order:normalizeLayoutBundle(bundle).cv_category_order})}
function layoutBaselineForCurrent(){
  const current=baseEffectiveSite();
  const currentItems=layoutItems(current);
  const assignments={};
  for(const item of currentItems){
    const existing=layoutBase?.assignments?.[item.id];
    assignments[item.id]=existing?clone(existing):{category_id:String(item.category_id||defaultCategoryForType(item.type)||''),order:Number(item.order??999999)};
  }
  return normalizeLayoutBundle({...clone(layoutBase),assignments});
}
function syncLayoutAssignments(){
  if(!layoutReady)return;
  const current=baseEffectiveSite(),ids=new Set(layoutItems(current).map(x=>String(x.id)));
  for(const id of Object.keys(layoutDraft.assignments||{}))if(!ids.has(id))delete layoutDraft.assignments[id];
  for(const item of layoutItems(current)){
    if(!layoutDraft.assignments[item.id])layoutDraft.assignments[item.id]={category_id:String(item.category_id||defaultCategoryForType(item.type)||''),order:Number(item.order??999999)};
  }
  layoutDraft=normalizeLayoutBundle(layoutDraft);
}
function initLayoutState(){
  if(layoutReady||!site)return;
  layoutBase=layoutBundle(site);
  layoutDraft=clone(layoutBase);
  try{
    const saved=JSON.parse(localStorage.getItem(LAYOUT_DRAFT_KEY)||'null');
    if(saved?.base_signature===layoutSignature(layoutBase)&&saved?.draft)layoutDraft=normalizeLayoutBundle(saved.draft);
    else if(saved)localStorage.removeItem(LAYOUT_DRAFT_KEY);
  }catch{localStorage.removeItem(LAYOUT_DRAFT_KEY)}
  layoutReady=true;
  syncLayoutAssignments();
}
function saveLayoutDraft(message=''){initLayoutState();syncLayoutAssignments();if(layoutDirty())localStorage.setItem(LAYOUT_DRAFT_KEY,JSON.stringify({base_signature:layoutSignature(layoutBase),draft:layoutDraft}));else localStorage.removeItem(LAYOUT_DRAFT_KEY);if(message)flash(message);renderAll()}
function layoutDirty(){if(!layoutReady)return false;syncLayoutAssignments();return layoutSignature(layoutDraft)!==layoutSignature(layoutBaselineForCurrent())}
function applyLayoutToData(data,bundle){
  const b=normalizeLayoutBundle(bundle);data.settings=data.settings||{};data.settings.pages=clone(b.pages);data.settings.categories=clone(b.categories);data.settings.cv_category_order=clone(b.cv_category_order);
  const map=new Map(layoutItems(data).map(x=>[String(x.id),x]));
  for(const [id,state] of Object.entries(b.assignments)){const item=map.get(id);if(item){item.category_id=state.category_id;item.order=state.order}}
  return data;
}
function defaultCategoryForType(type){initLayoutState();return layoutDraft.categories.find(c=>c.kind===ITEM_KIND[type])?.id||''}
function categoriesForType(type){initLayoutState();const kind=ITEM_KIND[type];return layoutDraft.categories.filter(c=>c.kind===kind).sort(categorySort)}
function categoriesForEditor(type,record){initLayoutState();if(type==='generic'&&!record)return layoutDraft.categories.filter(c=>GENERAL_CATEGORY_KINDS.has(c.kind)).sort(categorySort);return categoriesForType(type)}
function pageName(id){initLayoutState();const p=layoutDraft.pages.find(x=>x.id===id);return p?.name?.zh||p?.name?.en||id}
function categoryName(category){return category?.title?.zh||category?.title?.en||category?.id||'未命名類別'}
function categorySort(a,b){const pages=new Map(layoutDraft.pages.map((p,i)=>[p.id,i]));return(pages.get(a.page_id)??999)-(pages.get(b.page_id)??999)||(Number(a.order)||0)-(Number(b.order)||0)||String(a.id).localeCompare(String(b.id))}
function itemName(item){return title(item)||item?.id||'未命名項目'}
function itemMetaChinese(item){const parts=[];if(item?.type)parts.push(LABEL[item.type]||item.type);if(item?.start_date)parts.push(item.start_date);else if(item?.date)parts.push(item.date);else if(item?.year)parts.push(String(item.year));else if(item?.term?.zh||item?.term?.en)parts.push(item.term.zh||item.term.en);return parts.join(' · ')}
function compatibleCategory(category,item){return category?.kind===ITEM_KIND[item?.type]}
function uniqueCategoryId(seed){let id=slug(seed||'category'),base=id,n=2,used=new Set(layoutDraft.categories.map(c=>c.id));while(used.has(id))id=`${base}-${n++}`;return id}
function layoutOperation(){syncLayoutAssignments();return{op:'layout',before:clone(layoutBase),after:clone(layoutDraft)}}

const baseSaveLocal=saveLocal;
saveLocal=function(){
  if(site){initLayoutState();for(const op of contentOps()){const item=op?.after;if(['add','update'].includes(op?.op)&&item?.id&&item?.category_id){const existing=layoutDraft.assignments[item.id]||{};layoutDraft.assignments[item.id]={category_id:String(item.category_id),order:Number(item.order??existing.order??999999)}}}}
  baseSaveLocal();
};

const baseEffectiveSite=effectiveSite;
effectiveSite=function(){const data=baseEffectiveSite();initLayoutState();syncLayoutAssignments();return applyLayoutToData(data,layoutDraft)};

const basePayload=payload;
payload=function(){const result=basePayload();if(!layoutPreviewSuppressed&&layoutDirty())result.operations.push(layoutOperation());return result};

const baseOpenEditor=openEditor;
openEditor=function(type,record,options={}){
  if(record?._layout_kind==='system_page'){
    queueMicrotask(()=>{switchTab('siteSettings');if(typeof openSiteSettingsSection==='function')openSiteSettingsSection(record._settings_section,record._settings_panel)});
    return;
  }
  if(type==='academic_event'){openAcademicEventChooser();return}
  if(type==='page'||type==='category'){openLayoutEditor(type,record);return}
  baseOpenEditor(type,record,options);initLayoutState();
  const root=currentEditor?.root;if(!root)return;
  const cats=categoriesForEditor(type,record);
  const selected=record?.category_id||options?.draftOp?.after?.category_id||cats[0]?.id||'';
  const block=document.createElement('div');block.className='field category-selector-field';
  block.innerHTML=`<label>所屬類別</label><select data-path="category_id" id="itemCategorySelector">${cats.map(c=>`<option value="${esc(c.id)}" ${c.id===selected?'selected':''}>${esc(pageName(c.page_id))} → ${esc(categoryName(c))}</option>`).join('')}</select><p class="field-hint">項目會跟隨這個類別出現在對應頁面；移動類別時，所有項目會一起移動。</p>`;
  const optionsBox=root.querySelector('.form-options');(optionsBox||root.firstChild)?.after(block);
  if(type==='generic'&&!record){
    const formatBlock=document.createElement('div');formatBlock.className='field general-format-field';
    formatBlock.innerHTML=`<label>顯示風格</label><select id="generalContentFormat"><option value="">請選擇顯示風格…</option>${GENERAL_FORMAT_ORDER.map(kind=>`<option value="${esc(kind)}">${esc(GENERAL_FORMAT_LABELS[kind])}</option>`).join('')}</select><p class="field-hint">風格只描述版面，不限制內容用途；選擇後，「所屬類別」只顯示相同風格的類別。</p>`;
    block.before(formatBlock);
    const formatSelect=formatBlock.querySelector('#generalContentFormat'),categorySelect=block.querySelector('#itemCategorySelector'),hint=block.querySelector('.field-hint'),saveButton=root.querySelector('#saveEditor');
    const updateGeneralCategories=()=>{
      const kind=formatSelect.value,choices=cats.filter(c=>c.kind===kind);
      categorySelect.innerHTML=choices.map(c=>`<option value="${esc(c.id)}">${esc(pageName(c.page_id))} → ${esc(categoryName(c))}</option>`).join('');
      categorySelect.disabled=!choices.length;
      if(saveButton)saveButton.disabled=!choices.length;
      hint.textContent=!kind?'請先選擇顯示風格。':choices.length?'項目會跟隨這個類別出現在對應頁面；之後可在「排序」移到相同風格的其他類別。':'目前沒有使用這種風格的類別，請先在「新增」建立類別。';
    };
    formatSelect.onchange=updateGeneralCategories;
    updateGeneralCategories();
  }
  for(const id of ['publicationGroup','publicationCustom','teachingGroup','teachingCustom'])root.querySelector('#'+id)?.closest('.field,div')?.classList.add('legacy-category-hidden');
  if(type==='teaching'){
    const pages=layoutDraft.pages.filter(p=>p.id!=='home');
    const linkBlock=document.createElement('div');linkBlock.className='field';
    linkBlock.innerHTML=`<label>課程資訊頁面（選填）</label><select data-path="course_page_id"><option value="">無，維持目前顯示</option>${pages.map(p=>`<option value="${esc(p.id)}" ${p.id===String(record?.course_page_id||'')?'selected':''}>${esc(pageName(p.id))}</option>`).join('')}</select><p class="field-hint">選擇後，網站教學項目旁會出現「課程資訊」按鈕並連到該頁面。</p>`;
    block.after(linkBlock);
  }
  if(!cats.length){block.innerHTML='<div class="notice error">目前沒有可容納這種項目的類別。請先在「新增」選擇「類別」。</div>';root.querySelector('#saveEditor').disabled=true}
};

function openAcademicEventChooser(){
  initLayoutState();
  const box=document.createElement('div');
  box.innerHTML=`<h3>新增學術會議／訪問</h3><p class="field-hint">選擇資料種類後，會開啟對應欄位；兩種資料在網站與履歷中仍維持各自的類別。</p><div class="academic-event-choices"><button class="button academic-event-choice" data-academic-event-type="conference"><strong>學術會議</strong><span>會議、工作坊與參與身分</span></button><button class="button academic-event-choice" data-academic-event-type="visit"><strong>學術訪問</strong><span>訪問機構、地點與資助資訊</span></button></div>`;
  $('#addEditor').replaceChildren(box);currentEditor={type:'academic_event',record:null,root:box};
  box.onclick=event=>{const button=event.target.closest('[data-academic-event-type]');if(button)openEditor(button.dataset.academicEventType,null)};
}

const baseCollectEditor=collectEditor;
collectEditor=function(type,base){
  const result=baseCollectEditor(type,base);
  if(type==='generic'&&!base){
    const category=layoutDraft.categories.find(c=>c.id===result.o.category_id);
    if(category&&GENERAL_CATEGORY_KINDS.has(category.kind)){
      result.o.type=category.kind;
      if(category.kind==='honor'){
        const visibleYear=String(result.o.date_label?.en||result.o.date_label?.zh||result.o.start_date||'').match(/\d{4}/)?.[0];
        result.o.year=Number(visibleYear)||new Date().getFullYear();
        result.o.id=newId('honor',result.o.year,title(result.o));
      }
    }
  }
  return result;
};

function pageFormHtml(page){
  const p=page||{name:{en:'',zh:''},languages:['en','zh'],header:{label:{en:'',zh:''},title:{en:'',zh:''},intro:{en:'',zh:''}},color:'#8b3d2e',show_in_navigation:true};
  const editing=!!page,mode=p.languages?.length===1?p.languages[0]:'bilingual';
  return `<h3>${editing?'編輯':'新增'}頁面</h3><div class="field"><label>頁面語言版本</label><select data-page-field="language_mode" id="pageLanguageMode" ${editing?'disabled':''}><option value="bilingual" ${mode==='bilingual'?'selected':''}>雙語（英文＋中文）</option><option value="zh" ${mode==='zh'?'selected':''}>僅中文</option><option value="en" ${mode==='en'?'selected':''}>僅英文</option></select><p class="field-hint">${editing?'頁面建立後固定語言版本，避免留下失效網址。':'單語頁面不會顯示語言切換按鈕。'}</p></div>
  ${editing?'':`<div class="field"><label>網址代稱</label><input data-page-field="slug" placeholder="例如 algebra-course"><p class="field-hint">使用英文字母、數字與連字號；有英文導覽名稱時可留白自動產生，僅中文頁面請填寫。</p></div>`}
  <div class="pair-grid"><div class="field" data-page-language="en"><label>導覽名稱（英文）</label><input data-page-field="name.en" value="${esc(p.name?.en||'')}"></div><div class="field" data-page-language="zh"><label>導覽名稱（中文）</label><input data-page-field="name.zh" value="${esc(p.name?.zh||'')}"></div></div>
  <div class="pair-grid"><div class="field" data-page-language="en"><label>左上小字（英文）</label><input data-page-field="header.label.en" value="${esc(p.header?.label?.en||'')}"></div><div class="field" data-page-language="zh"><label>左上小字（中文）</label><input data-page-field="header.label.zh" value="${esc(p.header?.label?.zh||'')}"></div></div>
  <div class="pair-grid"><div class="field" data-page-language="en"><label>頁面標題（英文）</label><input data-page-field="header.title.en" value="${esc(p.header?.title?.en||'')}"></div><div class="field" data-page-language="zh"><label>頁面標題（中文）</label><input data-page-field="header.title.zh" value="${esc(p.header?.title?.zh||'')}"></div></div>
  <div class="pair-grid"><div class="field" data-page-language="en"><label>簡介（英文，可留白）</label><textarea data-page-field="header.intro.en">${esc(p.header?.intro?.en||'')}</textarea></div><div class="field" data-page-language="zh"><label>簡介（中文，可留白）</label><textarea data-page-field="header.intro.zh">${esc(p.header?.intro?.zh||'')}</textarea></div></div>
  <div class="field"><label>頁面主色</label><input type="color" data-page-field="color" value="${esc(p.color||'#8b3d2e')}"><p class="field-hint">頁首、按鈕與重點色會依這個顏色自動產生一致色階。</p></div>
  <div class="form-options"><label class="switch"><input type="checkbox" data-page-field="show_in_navigation" ${p.show_in_navigation!==false?'checked':''}>顯示於導覽列</label></div><p class="field-hint">關閉後頁面與網址仍保留，但不會出現在一般網站導覽列或 404 頁面的導覽列。</p>
  ${editing?`<div class="field"><label>網址</label><div class="preview-value">${[p.path?.en,p.path?.zh].filter(Boolean).map(esc).join(' ／ ')}</div></div>`:''}
  <div class="actions"><button class="button primary" data-save-layout-page="${esc(page?.id||'')}">${editing?'儲存頁面設定':'加入新增頁面草稿'}</button></div>`;
}
function updatePageLanguageFields(root){
  const mode=root.querySelector('#pageLanguageMode')?.value||'bilingual';
  root.querySelectorAll('[data-page-language]').forEach(field=>field.classList.toggle('page-language-hidden',mode!=='bilingual'&&field.dataset.pageLanguage!==mode));
}
function categoryFormHtml(category){
  const c=category||{label:{en:'',zh:''},title:{en:'',zh:''},intro:{en:'',zh:''},page_id:layoutDraft.pages.find(p=>p.id!=='home')?.id||'home',kind:'generic',show_on_web:true,show_on_cv:false};
  const pageOptions=layoutDraft.pages.map(p=>`<option value="${esc(p.id)}" ${p.id===c.page_id?'selected':''}>${esc(pageName(p.id))}</option>`).join('');
  const kindOrder=['publication','conference','talk','visit','organization','teaching','honor','generic','education','interest','contact','personal'];
  const formatLabels=Object.fromEntries(Object.entries(GENERAL_FORMAT_LABELS).map(([kind,label])=>[kind,`一般內容（${label}）`]));
  const kindOptions=kindOrder.map(id=>`<option value="${id}" ${id===c.kind?'selected':''}>${esc(formatLabels[id]||CATEGORY_KIND_LABELS[id])}</option>`).join('');
  return `<h3>${category?'編輯':'新增'}類別</h3><div class="notice">類別是頁面中的一個大區塊。左上小字、大標題與簡介都可分別填寫中英文。</div>
  <div class="pair-grid"><div class="field"><label>左上小字（英文）</label><input data-category-field="label.en" value="${esc(c.label?.en||'')}"></div><div class="field"><label>左上小字（中文）</label><input data-category-field="label.zh" value="${esc(c.label?.zh||'')}"></div></div>
  <div class="pair-grid"><div class="field"><label>大標題（英文）</label><input data-category-field="title.en" value="${esc(c.title?.en||'')}"></div><div class="field"><label>大標題（中文）</label><input data-category-field="title.zh" value="${esc(c.title?.zh||'')}"></div></div>
  <div class="pair-grid"><div class="field"><label>簡介（英文，可留白）</label><textarea data-category-field="intro.en">${esc(c.intro?.en||'')}</textarea></div><div class="field"><label>簡介（中文，可留白）</label><textarea data-category-field="intro.zh">${esc(c.intro?.zh||'')}</textarea></div></div>
  <div class="pair-grid"><div class="field"><label>所在頁面</label><select data-category-field="page_id">${pageOptions}</select></div><div class="field"><label>顯示風格</label><select data-category-field="kind" ${category?'disabled':''}>${kindOptions}</select><p class="field-hint">${category?'顯示風格決定網站與 PDF 的排版，因此建立後固定；項目可在「排序」移到使用相同風格的其他類別。':'顯示風格只描述版面，不限制內容用途；相同風格的類別可在「排序」互相搬移項目。'}</p></div></div>
  <div class="form-options"><label class="switch"><input type="checkbox" data-category-field="show_on_web" ${c.show_on_web!==false?'checked':''}>顯示於網站</label><label class="switch"><input type="checkbox" data-category-field="show_on_cv" ${c.show_on_cv?'checked':''}>顯示於 PDF 履歷</label></div>
  <div class="actions"><button class="button primary" data-save-layout-category="${esc(category?.id||'')}">${category?'儲存類別設定':'加入新增類別草稿'}</button>${category?`<button class="button danger" data-delete-layout-category="${esc(category.id)}">刪除類別</button>`:''}</div>`;
}
function openLayoutEditor(type,record){
  initLayoutState();const box=document.createElement('div');
  box.innerHTML=type==='page'?pageFormHtml(record?layoutDraft.pages.find(p=>p.id===record._layout_id):null):categoryFormHtml(record?layoutDraft.categories.find(c=>c.id===record._layout_id):null);
  $('#addEditor').replaceChildren(box);currentEditor={type,record,root:box};
  if(type==='page'){updatePageLanguageFields(box);box.querySelector('#pageLanguageMode')?.addEventListener('change',()=>updatePageLanguageFields(box))}
  box.onclick=event=>{
    const button=event.target.closest('button');if(!button)return;
    if(button.hasAttribute('data-save-layout-page'))saveLayoutPage(button.dataset.saveLayoutPage,box);
    else if(button.hasAttribute('data-save-layout-category'))saveLayoutCategory(button.dataset.saveLayoutCategory,box);
    else if(button.dataset.deleteLayoutCategory)deleteCategory(button.dataset.deleteLayoutCategory);
  };
}
function saveLayoutPage(id,root){
  const value=readNestedFields(root,'data-page-field'),languages=value.language_mode==='en'?['en']:value.language_mode==='zh'?['zh']:['en','zh'],required=languages.flatMap(lang=>[value.name?.[lang],value.header?.label?.[lang],value.header?.title?.[lang]]);
  if(required.some(v=>!String(v||'').trim()))return flash('使用中的語言必須填寫導覽名稱、左上小字與頁面標題');
  if(!id&&!String(value.slug||value.name?.en||'').trim())return flash('僅中文頁面請填寫網址代稱');
  if(id){const page=layoutDraft.pages.find(p=>p.id===id);if(!page)return;page.languages=languages;page.name=layoutPair(value.name);page.path={en:languages.includes('en')?(page.path.en||`${page.id}.html`):'',zh:languages.includes('zh')?(page.path.zh||`zh/${page.id}.html`):''};page.header={label:layoutPair(value.header.label),title:layoutPair(value.header.title),intro:layoutPair(value.header.intro)};page.color=value.color;page.show_in_navigation=value.show_in_navigation!==false;saveLayoutDraft('已儲存頁面設定');return}
  const pageId=uniquePageId(value.slug||value.name.en),page={id:pageId,name:layoutPair(value.name),languages,path:{en:languages.includes('en')?`${pageId}.html`:'',zh:languages.includes('zh')?`zh/${pageId}.html`:''},header:{label:layoutPair(value.header.label),title:layoutPair(value.header.title),intro:layoutPair(value.header.intro)},color:value.color,show_in_navigation:value.show_in_navigation!==false,order:layoutDraft.pages.length};
  layoutDraft.pages.push(page);saveLayoutDraft('已加入新增頁面草稿');openLayoutEditor('page',{_layout_id:pageId});renderRecords();
}
function uniquePageId(seed){let id=slug(seed||'page'),base=id,n=2,used=new Set(layoutDraft.pages.map(p=>p.id));while(used.has(id))id=`${base}-${n++}`;return id}
function saveLayoutCategory(id,root){
  const value=readNestedFields(root,'data-category-field'),required=[value.label?.en,value.label?.zh,value.title?.en,value.title?.zh];
  if(required.some(v=>!String(v||'').trim()))return flash('左上小字與大標題的中英文都不能留白');
  if(id){setCategoryFromEditor(id,root);renderRecords();return}
  const categoryId=uniqueCategoryId(value.title.en),same=layoutDraft.categories.filter(c=>c.page_id===value.page_id),category={id:categoryId,page_id:value.page_id,kind:value.kind||'generic',label:layoutPair(value.label),title:layoutPair(value.title),intro:layoutPair(value.intro),order:same.length,show_on_web:value.show_on_web!==false,show_on_cv:!!value.show_on_cv};
  layoutDraft.categories.push(category);if(category.show_on_cv)layoutDraft.cv_category_order.push(categoryId);saveLayoutDraft('已加入新增類別草稿');openLayoutEditor('category',{_layout_id:categoryId});renderRecords();
}

function categoryEditorHtml(category){
  const pageOptions=layoutDraft.pages.map(p=>`<option value="${esc(p.id)}" ${p.id===category.page_id?'selected':''}>${esc(pageName(p.id))}</option>`).join('');
  return `<div class="layout-category-editor" data-category-editor="${esc(category.id)}">
    <div class="pair-grid"><div class="field"><label>左上小字（英文）</label><input data-category-field="label.en" value="${esc(category.label.en)}"></div><div class="field"><label>左上小字（中文）</label><input data-category-field="label.zh" value="${esc(category.label.zh)}"></div></div>
    <div class="pair-grid"><div class="field"><label>大標題（英文）</label><input data-category-field="title.en" value="${esc(category.title.en)}"></div><div class="field"><label>大標題（中文）</label><input data-category-field="title.zh" value="${esc(category.title.zh)}"></div></div>
    <div class="pair-grid"><div class="field"><label>簡介（英文，可留白）</label><textarea data-category-field="intro.en">${esc(category.intro.en)}</textarea></div><div class="field"><label>簡介（中文，可留白）</label><textarea data-category-field="intro.zh">${esc(category.intro.zh)}</textarea></div></div>
    <div class="pair-grid"><div class="field"><label>所在頁面</label><select data-category-field="page_id">${pageOptions}</select></div><div class="field"><label>項目類型</label><input value="${esc(CATEGORY_KIND_LABELS[category.kind]||category.kind)}" disabled></div></div>
    <div class="form-options"><label class="switch"><input type="checkbox" data-category-field="show_on_web" ${category.show_on_web?'checked':''}>顯示於網站</label><label class="switch"><input type="checkbox" data-category-field="show_on_cv" ${category.show_on_cv?'checked':''}>顯示於 PDF 履歷</label></div>
    <div class="actions"><button class="button primary" data-save-category="${esc(category.id)}">儲存類別設定</button><button class="button danger" data-delete-category="${esc(category.id)}">刪除類別</button></div>
  </div>`;
}
function pageEditorHtml(page){
  if(!page.header)return `<div class="notice">首頁沒有一般頁首；首頁內容由下面各類別控制。</div>`;
  return `<div class="layout-page-editor" data-page-editor="${esc(page.id)}">
    <div class="pair-grid"><div class="field"><label>頁首小字（英文）</label><input data-page-field="header.label.en" value="${esc(page.header.label.en)}"></div><div class="field"><label>頁首小字（中文）</label><input data-page-field="header.label.zh" value="${esc(page.header.label.zh)}"></div></div>
    <div class="pair-grid"><div class="field"><label>頁面標題（英文）</label><input data-page-field="header.title.en" value="${esc(page.header.title.en)}"></div><div class="field"><label>頁面標題（中文）</label><input data-page-field="header.title.zh" value="${esc(page.header.title.zh)}"></div></div>
    <div class="pair-grid"><div class="field"><label>頁首簡介（英文）</label><textarea data-page-field="header.intro.en">${esc(page.header.intro.en)}</textarea></div><div class="field"><label>頁首簡介（中文）</label><textarea data-page-field="header.intro.zh">${esc(page.header.intro.zh)}</textarea></div></div>
    <div class="form-options"><label class="switch"><input type="checkbox" data-page-field="show_in_navigation" ${page.show_in_navigation!==false?'checked':''}>顯示於導覽列</label></div>
    <button class="button primary" data-save-page="${esc(page.id)}">儲存頁首設定</button>
  </div>`;
}
function renderLayoutManager(){
  initLayoutState();const box=$('#layoutManager');if(!box)return;
  if(!layoutDraft.pages.some(p=>p.id===layoutManagerPageId))layoutManagerPageId=layoutDraft.pages[0]?.id||'';
  const selectedPage=layoutDraft.pages.find(p=>p.id===layoutManagerPageId);
  const pageOptions=layoutDraft.pages.map(p=>`<option value="${esc(p.id)}" ${p.id===layoutManagerPageId?'selected':''}>${esc(pageName(p.id))}</option>`).join('');
  const kindOptions=Object.entries(CATEGORY_KIND_LABELS).map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join('');
  box.innerHTML=`<div class="notice"><strong>類別就是網站的大標題。</strong><p>所有項目都必須放在某個類別中。類別移到另一頁時，裡面的項目會一起移動；網站與 PDF 履歷共用同一套類別名稱。</p></div>
  <div class="toolbar layout-page-filter"><div class="field"><label>選擇頁面</label><select id="layoutManagerPage">${pageOptions}</select></div><p class="field-hint">下方只顯示所選頁面的頁首與類別。</p></div>
  <details class="layout-tool" open><summary><strong>新增類別</strong></summary><div class="layout-tool-body"><div class="pair-grid"><div class="field"><label>中文大標題</label><input id="newCategoryZh"></div><div class="field"><label>英文大標題</label><input id="newCategoryEn"></div></div><div class="pair-grid"><div class="field"><label>所在頁面</label><select id="newCategoryPage">${pageOptions}</select></div><div class="field"><label>項目類型</label><select id="newCategoryKind">${kindOptions}</select></div></div><button class="button primary" id="addCategoryButton">新增類別</button></div></details>
  ${selectedPage?`<details class="layout-page-card" open><summary><strong>${esc(pageName(selectedPage.id))}</strong><span class="tag">${layoutDraft.categories.filter(c=>c.page_id===selectedPage.id).length} 個類別</span></summary><div class="layout-tool-body"><h3>頁首設定</h3>${pageEditorHtml(selectedPage)}<h3>此頁類別</h3>${layoutDraft.categories.filter(c=>c.page_id===selectedPage.id).sort((a,b)=>a.order-b.order).map(categoryEditorHtml).join('')||'<p class="muted">此頁尚無類別。</p>'}</div></details>`:'<p class="muted">目前沒有可管理的頁面。</p>'}`;
  box.querySelector('#layoutManagerPage').onchange=event=>{layoutManagerPageId=event.target.value;renderLayoutManager()};
  box.querySelector('#addCategoryButton').onclick=addCategoryFromManager;
  box.onclick=layoutManagerClick;
}
function readNestedFields(root,attr){const out={};root.querySelectorAll(`[${attr}]`).forEach(input=>{const path=input.getAttribute(attr).split('.');let cursor=out;path.slice(0,-1).forEach(k=>cursor=cursor[k]??={});cursor[path.at(-1)]=input.type==='checkbox'?input.checked:input.value});return out}
function addCategoryFromManager(){
  const en=$('#newCategoryEn').value.trim(),zh=$('#newCategoryZh').value.trim(),page_id=$('#newCategoryPage').value,kind=$('#newCategoryKind').value;
  if(!en||!zh)return flash('中英文大標題都不能留白');
  const id=uniqueCategoryId(en||zh),same=layoutDraft.categories.filter(c=>c.page_id===page_id);
  layoutDraft.categories.push({id,page_id,kind,label:{en,zh},title:{en,zh},intro:{en:'',zh:''},order:same.length,show_on_web:true,show_on_cv:!['featured_publications','upcoming','contact'].includes(kind)});
  if(layoutDraft.categories.at(-1).show_on_cv)layoutDraft.cv_category_order.push(id);
  layoutManagerPageId=page_id;
  saveLayoutDraft('已新增類別草稿')
}
function setCategoryFromEditor(id,root){const category=layoutDraft.categories.find(c=>c.id===id);if(!category)return;const values=readNestedFields(root,'data-category-field');if(!values.label?.en?.trim()||!values.label?.zh?.trim()||!values.title?.en?.trim()||!values.title?.zh?.trim())return flash('類別的小字與大標題，中英文都不能留白');const oldPage=category.page_id;Object.assign(category,values);category.label=layoutPair(values.label);category.title=layoutPair(values.title);category.intro=layoutPair(values.intro);category.show_on_web=!!values.show_on_web;category.show_on_cv=!!values.show_on_cv;if(oldPage!==category.page_id)category.order=layoutDraft.categories.filter(c=>c.page_id===category.page_id&&c.id!==id).length;layoutDraft=normalizeLayoutBundle(layoutDraft);saveLayoutDraft('已儲存類別設定')}
function setPageFromEditor(id,root){const page=layoutDraft.pages.find(p=>p.id===id);if(!page?.header)return;const values=readNestedFields(root,'data-page-field');if(!values.header?.label?.en?.trim()||!values.header?.label?.zh?.trim()||!values.header?.title?.en?.trim()||!values.header?.title?.zh?.trim())return flash('頁首小字與頁面標題，中英文都不能留白');page.header={label:layoutPair(values.header.label),title:layoutPair(values.header.title),intro:layoutPair(values.header.intro)};page.show_in_navigation=values.show_in_navigation!==false;saveLayoutDraft('已儲存頁首設定')}
function chooseMoveTarget(category,items){const targets=layoutDraft.categories.filter(c=>c.id!==category.id&&c.kind===category.kind);if(!targets.length)return null;const answer=prompt(`這個類別有 ${items.length} 個項目。請輸入要移入的類別編號：\n`+targets.map((c,i)=>`${i+1}. ${pageName(c.page_id)} → ${categoryName(c)}`).join('\n'));if(answer===null)return undefined;const index=Number(answer)-1;return targets[index]||null}
function deleteCategory(id){const category=layoutDraft.categories.find(c=>c.id===id);if(!category)return;const items=layoutItems(effectiveSite()).filter(x=>layoutDraft.assignments[x.id]?.category_id===id);if(!confirm(`確定刪除類別「${categoryName(category)}」？${items.length?`\n其中 ${items.length} 個項目必須先移到同類型的其他類別。`:''}`))return;if(items.length){const target=chooseMoveTarget(category,items);if(target===undefined)return;if(!target)return flash('沒有可接收這些項目的同類型類別，請先新增類別');const start=Object.values(layoutDraft.assignments).filter(x=>x.category_id===target.id).length;items.forEach((item,i)=>layoutDraft.assignments[item.id]={category_id:target.id,order:start+i})}layoutDraft.categories=layoutDraft.categories.filter(c=>c.id!==id);layoutDraft.cv_category_order=layoutDraft.cv_category_order.filter(x=>x!==id);saveLayoutDraft('已刪除類別草稿')}
function layoutManagerClick(event){const button=event.target.closest('button');if(!button)return;if(button.dataset.saveCategory){const root=button.closest('[data-category-editor]');setCategoryFromEditor(button.dataset.saveCategory,root)}else if(button.dataset.deleteCategory)deleteCategory(button.dataset.deleteCategory);else if(button.dataset.savePage){const root=button.closest('[data-page-editor]');setPageFromEditor(button.dataset.savePage,root)}}

function setupUnifiedOrderUI(){
  const tab=$('#orderTab');if(!tab)return;
  tab.innerHTML=`<div class="toolbar"><div class="field"><label>選擇頁面</label><select id="layoutOrderPage"></select></div><button class="button" id="reloadLayoutOrder">依目前草稿重載</button></div><p class="field-hint">同一頁面的類別與項目會一起顯示。移動類別時，其下所有項目會跟著移動；每個項目的「移到其他類別」只會列出顯示風格相同、可安全接收的類別，例如預印本與期刊論文。</p><div id="layoutOrderEditor" class="scroll"></div><details class="order-homepage-panel"><summary><strong>首頁精選與近期活動</strong></summary><div id="homepageManager"></div></details>`;
  const selector=tab.querySelector('#layoutOrderPage');selector.onchange=renderUnifiedOrder;tab.querySelector('#reloadLayoutOrder').onclick=()=>{syncLayoutAssignments();renderUnifiedOrder();flash('已依目前草稿重新整理')};tab.querySelector('#layoutOrderEditor').onclick=unifiedOrderClick;tab.querySelector('#layoutOrderEditor').onchange=unifiedOrderChange;
  fillOrderPageSelector();renderUnifiedOrder();
}
const baseLoadOrder=loadOrder;
loadOrder=function(){
  if($('#layoutOrderPage')){renderUnifiedOrder();return}
  return baseLoadOrder()
};
function fillOrderPageSelector(){if(!site)return;initLayoutState();const select=$('#layoutOrderPage');if(!select||!layoutDraft)return;const old=select.value;select.innerHTML=layoutDraft.pages.map(p=>`<option value="${esc(p.id)}">${esc(pageName(p.id))}</option>`).join('')+'<option value="__cv__">PDF 履歷</option>';if([...select.options].some(o=>o.value===old))select.value=old}
function categoryItemIds(categoryId){return Object.entries(layoutDraft.assignments).filter(([,s])=>s.category_id===categoryId).sort((a,b)=>a[1].order-b[1].order||a[0].localeCompare(b[0])).map(([id])=>id)}
function orderCategoryCard(category,index,total,map,cvMode=false){
  const ids=categoryItemIds(category.id),compatible=layoutDraft.categories.filter(c=>c.kind===category.kind&&c.id!==category.id);
  return `<div class="layout-order-category" data-order-category="${esc(category.id)}"><div class="layout-order-category-head"><div><span class="tag">${esc(CATEGORY_KIND_LABELS[category.kind]||category.kind)}</span><strong>${index+1}. ${esc(categoryName(category))}</strong><span class="muted">${esc(pageName(category.page_id))} · ${ids.length} 個項目</span></div><div class="actions"><button class="button" data-category-up="${esc(category.id)}" ${index===0?'disabled':''}>類別 ↑</button><button class="button" data-category-down="${esc(category.id)}" ${index===total-1?'disabled':''}>類別 ↓</button><button class="button" data-edit-category-jump="${esc(category.id)}">編輯類別</button></div></div>${!cvMode?`<div class="order-sort-tools"><span class="muted">此類別快速排序：</span><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="newest">日期新到舊</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="oldest">日期舊到新</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="title">名稱</button></div>`:''}<div>${ids.map((id,i)=>{const item=map.get(id);if(!item)return'';return `<div class="layout-order-item"><div><strong>${i+1}. ${esc(itemName(item))}</strong><span class="muted">${esc(itemMetaChinese(item))}</span></div><div class="layout-order-item-actions"><button class="button" data-item-up="${esc(id)}" ${i===0?'disabled':''}>↑</button><button class="button" data-item-down="${esc(id)}" ${i===ids.length-1?'disabled':''}>↓</button>${compatible.length&&!cvMode?`<select data-move-item="${esc(id)}"><option value="">移到其他類別…</option>${compatible.map(c=>`<option value="${esc(c.id)}">${esc(pageName(c.page_id))} → ${esc(categoryName(c))}</option>`).join('')}</select>`:''}</div></div>`}).join('')||'<p class="muted">此類別目前沒有項目。</p>'}</div></div>`;
}
function renderUnifiedOrder(){if(!site)return;initLayoutState();syncLayoutAssignments();fillOrderPageSelector();const pageId=$('#layoutOrderPage')?.value||layoutDraft.pages[0]?.id,map=new Map(layoutItems(effectiveSite()).map(x=>[String(x.id),x])),cvMode=pageId==='__cv__';let categories;if(cvMode){const byId=new Map(layoutDraft.categories.map(c=>[c.id,c]));categories=layoutDraft.cv_category_order.map(id=>byId.get(id)).filter(Boolean)}else categories=layoutDraft.categories.filter(c=>c.page_id===pageId).sort((a,b)=>a.order-b.order);$('#layoutOrderEditor').innerHTML=categories.map((c,i)=>orderCategoryCard(c,i,categories.length,map,cvMode)).join('')||'<p class="muted">這個頁面目前沒有類別。</p>'}
function moveInArray(array,index,delta){const target=index+delta;if(index<0||target<0||target>=array.length)return false;[array[index],array[target]]=[array[target],array[index]];return true}
function moveCategory(id,delta){const page=$('#layoutOrderPage').value;if(page==='__cv__'){const i=layoutDraft.cv_category_order.indexOf(id);if(moveInArray(layoutDraft.cv_category_order,i,delta))saveLayoutDraft('已調整 PDF 履歷類別順序');return}const rows=layoutDraft.categories.filter(c=>c.page_id===page).sort((a,b)=>a.order-b.order),i=rows.findIndex(c=>c.id===id);if(!moveInArray(rows,i,delta))return;rows.forEach((c,n)=>c.order=n);layoutDraft=normalizeLayoutBundle(layoutDraft);saveLayoutDraft('已調整頁面類別順序')}
function moveItem(id,delta){const state=layoutDraft.assignments[id];if(!state)return;const ids=categoryItemIds(state.category_id),i=ids.indexOf(id);if(!moveInArray(ids,i,delta))return;ids.forEach((iid,n)=>layoutDraft.assignments[iid].order=n);saveLayoutDraft('已調整項目順序')}
function recordSortValue(item){return String(item?.start_date||item?.date||item?.year||item?.term?.en||item?.term?.zh||'')}
function sortCategory(id,mode){const map=new Map(layoutItems(effectiveSite()).map(x=>[String(x.id),x])),ids=categoryItemIds(id);ids.sort((a,b)=>{const x=map.get(a),y=map.get(b);if(mode==='title')return itemName(x).localeCompare(itemName(y),'zh-Hant');const result=recordSortValue(x).localeCompare(recordSortValue(y));return(mode==='newest'?-result:result)||itemName(x).localeCompare(itemName(y),'zh-Hant')});ids.forEach((iid,n)=>layoutDraft.assignments[iid].order=n);saveLayoutDraft('已套用類別內快速排序')}
function unifiedOrderClick(event){const button=event.target.closest('button');if(!button)return;if(button.dataset.categoryUp)moveCategory(button.dataset.categoryUp,-1);else if(button.dataset.categoryDown)moveCategory(button.dataset.categoryDown,1);else if(button.dataset.itemUp)moveItem(button.dataset.itemUp,-1);else if(button.dataset.itemDown)moveItem(button.dataset.itemDown,1);else if(button.dataset.sortCategory)sortCategory(button.dataset.sortCategory,button.dataset.sortMode);else if(button.dataset.editCategoryJump){const category=layoutDraft.categories.find(c=>c.id===button.dataset.editCategoryJump);if(category){openLayoutEditor('category',{_layout_id:category.id});switchTab('add')}}}
function unifiedOrderChange(event){const select=event.target.closest('[data-move-item]');if(!select||!select.value)return;const id=select.dataset.moveItem,target=select.value,state=layoutDraft.assignments[id];if(!state)return;state.category_id=target;state.order=categoryItemIds(target).length;saveLayoutDraft('已將項目移到另一類別')}

function layoutDiffSummary(before,after){
  const b=normalizeLayoutBundle(before),a=normalizeLayoutBundle(after),bc=new Map(b.categories.map(x=>[x.id,x])),ac=new Map(a.categories.map(x=>[x.id,x]));let added=0,removed=0,changed=0,moved=0,itemMoved=0;
  for(const id of new Set([...bc.keys(),...ac.keys()])){const x=bc.get(id),y=ac.get(id);if(!x)added++;else if(!y)removed++;else{if(JSON.stringify({label:x.label,title:x.title,intro:x.intro,show_on_web:x.show_on_web,show_on_cv:x.show_on_cv})!==JSON.stringify({label:y.label,title:y.title,intro:y.intro,show_on_web:y.show_on_web,show_on_cv:y.show_on_cv}))changed++;if(x.page_id!==y.page_id||x.order!==y.order)moved++}}
  for(const id of new Set([...Object.keys(b.assignments),...Object.keys(a.assignments)])){const x=b.assignments[id],y=a.assignments[id];if(x&&y&&(x.category_id!==y.category_id||x.order!==y.order))itemMoved++}
  const pageChanged=JSON.stringify(b.pages)!==JSON.stringify(a.pages)?1:0,cvChanged=JSON.stringify(b.cv_category_order)!==JSON.stringify(a.cv_category_order)?1:0;
  return{added,removed,changed,moved,itemMoved,pageChanged,cvChanged}
}
function layoutPreviewHtml(op){
  const before=normalizeLayoutBundle(op.before),after=normalizeLayoutBundle(op.after),stats=layoutDiffSummary(before,after),bc=new Map(before.categories.map(x=>[x.id,x])),ac=new Map(after.categories.map(x=>[x.id,x])),items=new Map(layoutItems(effectiveSite()).map(x=>[String(x.id),x]));
  const categoryRows=[];for(const id of new Set([...bc.keys(),...ac.keys()])){const b=bc.get(id),a=ac.get(id);if(JSON.stringify(b)===JSON.stringify(a))continue;categoryRows.push(`<div class="order-diff-row changed"><strong>${esc(categoryName(a||b))}</strong><span>${b?esc(pageNameFromBundle(before,b.page_id)+'／'+categoryName(b)):'不存在'} → ${a?esc(pageNameFromBundle(after,a.page_id)+'／'+categoryName(a)):'已刪除'}</span></div>`)}
  const assignmentRows=[];for(const id of new Set([...Object.keys(before.assignments),...Object.keys(after.assignments)])){const b=before.assignments[id],a=after.assignments[id];if(!b||!a||b.category_id!==a.category_id||b.order!==a.order){assignmentRows.push(`<div class="order-diff-row changed"><strong>${esc(itemName(items.get(id))||id)}</strong><span>${esc(layoutPosition(before,b))} → ${esc(layoutPosition(after,a))}</span></div>`)}}
  const summary=[stats.pageChanged?'頁首設定有變更':'',stats.added?`新增 ${stats.added} 個類別`:'',stats.removed?`刪除 ${stats.removed} 個類別`:'',stats.changed?`修改 ${stats.changed} 個類別`:'',stats.moved?`移動／排序 ${stats.moved} 個類別`:'',stats.itemMoved?`移動／排序 ${stats.itemMoved} 個項目`:'',stats.cvChanged?'PDF 履歷順序有變更':''].filter(Boolean).join('、')||'沒有結構差異';
  return `<details class="diff"><summary><strong>頁面、類別與項目排序</strong>：${esc(summary)}</summary><div class="preview-card"><h4>類別差異</h4>${categoryRows.join('')||'<p class="muted">類別本身沒有差異。</p>'}<h4>項目所屬與順序差異</h4>${assignmentRows.slice(0,80).join('')||'<p class="muted">項目位置沒有差異。</p>'}${assignmentRows.length>80?`<p class="muted">另有 ${assignmentRows.length-80} 筆未展開。</p>`:''}</div></details>`;
}
function pageNameFromBundle(bundle,id){const p=bundle.pages.find(x=>x.id===id);return p?.name?.zh||p?.name?.en||id}
function layoutPosition(bundle,state){if(!state)return'不存在';const c=bundle.categories.find(x=>x.id===state.category_id);return`${c?pageNameFromBundle(bundle,c.page_id)+' → '+categoryName(c):state.category_id}／第 ${Number(state.order)+1}`}


const baseSortedRecords=sortedRecords;
function layoutCatalogRecords(){
  if(!layoutDraft)return[];
  return[
    ...layoutDraft.pages.filter(p=>p.id!=='home').map(p=>({id:`page:${p.id}`,type:'page',_layout_kind:'page',_layout_id:p.id,title:clone(p.name),category_id:'',order:p.order})),
    {id:'system-page:contact',type:'page',_layout_kind:'system_page',_settings_section:'contactForm',_settings_panel:'design',title:{en:'Contact Form',zh:'聯絡表單頁面'},category_id:'',order:9000},
    {id:'system-page:404',type:'page',_layout_kind:'system_page',_settings_section:'errorPage',_settings_panel:'',title:{en:'404 Page',zh:'404 頁面'},category_id:'',order:9001},
    ...layoutDraft.categories.map(c=>({id:`category:${c.id}`,type:'category',_layout_kind:'category',_layout_id:c.id,title:clone(c.title),category_id:c.id,order:c.order,page_id:c.page_id}))
  ];
}
function adminFilterMatches(item,filter){
  if(!filter)return true;
  if(filter==='academic_event')return item.type==='conference'||item.type==='visit';
  if(filter==='generic')return GENERAL_CATEGORY_KINDS.has(item.type);
  return item.type===filter;
}
function findAdminRecord(id){return layoutCatalogRecords().find(x=>x.id===id)}
function deleteAdminRecord(record){if(record?._layout_kind==='category')deleteCategory(record._layout_id);else flash('系統頁面與一般頁面只能編輯，不能從這裡刪除。')}
sortedRecords=function(){
  if(!site)return baseSortedRecords();
  const data=effectiveSite(),query=norm($('#search').value),filter=$('#filter').value;
  const items=[...allRecords(data),...layoutCatalogRecords()].filter(item=>adminFilterMatches(item,filter)&&(!query||norm(JSON.stringify(item)).includes(query)));
  const sort=$('#viewSort').value;
  if(sort==='newest')return items.sort((a,b)=>recordDate(b).localeCompare(recordDate(a)));
  if(sort==='oldest')return items.sort((a,b)=>recordDate(a).localeCompare(recordDate(b)));
  if(sort==='title')return items.sort((a,b)=>itemName(a).localeCompare(itemName(b),'zh-Hant'));
  const pageRank=new Map(layoutDraft.pages.map((p,i)=>[p.id,i]));
  const categoryRank=new Map(layoutDraft.categories.map(c=>[c.id,[pageRank.get(c.page_id)??999,Number(c.order)||0]]));
  return items.sort((a,b)=>{
    if(a.type==='page'||b.type==='page'){
      if(a.type!==b.type)return a.type==='page'?-1:1;
      return Number(a.order)-Number(b.order);
    }
    if(a.type==='category'||b.type==='category'){
      if(a.type!==b.type)return a.type==='category'?-1:1;
      return (pageRank.get(a.page_id)??999)-(pageRank.get(b.page_id)??999)||Number(a.order)-Number(b.order);
    }
    const ca=categoryRank.get(a.category_id)||[999,999],cb=categoryRank.get(b.category_id)||[999,999];
    return ca[0]-cb[0]||ca[1]-cb[1]||(Number(a.order)||0)-(Number(b.order)||0)||itemName(a).localeCompare(itemName(b),'zh-Hant');
  });
};
renderRecords=function(){
  const categoryMap=new Map((layoutDraft?.categories||[]).map(c=>[c.id,c])),pageMap=new Map((layoutDraft?.pages||[]).map(p=>[p.id,p]));
  const badge=(kind,label,value)=>`<span class="record-badge record-badge-${kind}"><span>${esc(label)}</span><strong>${esc(value)}</strong></span>`;
  $('#records').innerHTML=sortedRecords().map(item=>{
    const category=categoryMap.get(item.category_id),page=item.type==='page'?pageMap.get(item._layout_id):pageMap.get(item.type==='category'?item.page_id:category?.page_id),badges=[badge('type','項目類型',LABEL[item.type]||item.type)];
    if(item.type==='page')badges.push(badge('language','語言版本',page?.languages?.length===1?(page.languages[0]==='zh'?'僅中文':'僅英文'):'雙語'));
    else badges.push(badge('page','所在頁面',pageName(page?.id||item.page_id)));
    if(!['page','category'].includes(item.type))badges.push(badge('category','所在類別',categoryName(category)));
    const canDelete=item.type!=='page';
    return `<div class="row"><div class="record-badges">${badges.join('')}</div><div class="record-heading"><strong>${esc(itemName(item))}</strong><span class="muted record-meta">${esc(recordMeta(item))}</span></div><div class="id">${esc(item.id)}</div><div class="actions"><button class="button" data-edit="${esc(item.id)}">編輯</button>${canDelete?`<button class="button danger" data-delete="${esc(item.id)}">刪除</button>`:''}</div></div>`;
  }).join('')||'<p class="muted">沒有符合項目。</p>';
};
const baseRenderPreview=renderPreview;
renderPreview=function(refreshDictionary=true){layoutPreviewSuppressed=true;baseRenderPreview(refreshDictionary);layoutPreviewSuppressed=false;if(layoutDirty()){const op=layoutOperation();$('#preview').insertAdjacentHTML('beforeend',layoutPreviewHtml(op));const text=$('#summary').textContent;$('#summary').textContent=text==='尚無變更。'?'頁面、類別或排序有變更。':text.replace(/。$/,'')+'、頁面／類別 1。'}$('#payload').textContent=JSON.stringify(payload(),null,2)};
const baseRenderAll=renderAll;
renderAll=function(){baseRenderAll();if(site){initLayoutState();renderLayoutManager();renderUnifiedOrder()}};
const baseClearSubmittedDraft=clearSubmittedDraft;
clearSubmittedDraft=function(){localStorage.removeItem(LAYOUT_DRAFT_KEY);baseClearSubmittedDraft()};

function installLayoutCss(){const style=document.createElement('style');style.textContent=`
.legacy-category-hidden,.page-language-hidden{display:none!important}.academic-event-choices{display:grid;grid-template-columns:1fr 1fr;gap:10px}.academic-event-choice{display:grid;gap:4px;text-align:left;padding:14px}.academic-event-choice span{color:#6f655e;font-weight:400}.order-homepage-panel{margin-top:16px;border-top:1px solid #ded3ca;padding-top:12px}.order-homepage-panel>summary{cursor:pointer;padding:8px 0}.record-badges{display:flex;gap:6px;flex-wrap:wrap}.record-badge{display:inline-flex;overflow:hidden;border:1px solid #d9cec5;border-radius:999px;font-size:12px}.record-badge span{padding:3px 6px;background:#eee7e1;color:#625950}.record-badge strong{padding:3px 7px;background:#fff}.record-badge-type{border-color:#c9b19f}.record-badge-page{border-color:#aebfd2}.record-badge-page span{background:#e8eff6;color:#405b76}.record-badge-category{border-color:#b5cbbf}.record-badge-category span{background:#e8f2ec;color:#3f6651}.record-badge-language{border-color:#c8b8d2}.record-badge-language span{background:#f0eaf4;color:#665072}.layout-tool,.layout-page-card{border:1px solid #ded3ca;border-radius:12px;margin:10px 0;background:#fcfaf8}.layout-tool>summary,.layout-page-card>summary{display:flex;gap:8px;align-items:center;justify-content:space-between;cursor:pointer;padding:12px}.layout-tool-body{padding:0 12px 12px}.layout-category-editor{border:1px solid #e1d6ce;border-radius:11px;padding:12px;margin:10px 0;background:#fff}.layout-category-editor textarea,.layout-page-editor textarea{min-height:70px}.layout-order-category{border:1px solid #d9cec5;border-radius:12px;padding:11px;margin:10px 0;background:#faf6f2}.layout-order-category-head,.layout-order-item{display:flex;justify-content:space-between;gap:12px;align-items:center}.layout-order-category-head>div:first-child,.layout-order-item>div:first-child{display:grid;gap:3px;min-width:0}.layout-order-item{padding:9px;border-top:1px solid #e7ddd5;background:#fff}.layout-order-item-actions{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.layout-order-item-actions select{max-width:240px;padding:7px;border:1px solid #cfc4bb;border-radius:8px}.layout-category-editor .actions{margin-top:8px}@media(max-width:700px){.academic-event-choices{grid-template-columns:1fr}.layout-order-category-head,.layout-order-item{align-items:flex-start;flex-direction:column}.layout-order-item-actions{width:100%}}
`;document.head.append(style)}
installLayoutCss();
setupUnifiedOrderUI();
if(site)renderAll();
