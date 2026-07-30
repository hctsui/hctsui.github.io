'use strict';

/* Schema 3 page/category manager. This script intentionally sits outside the
   large legacy Admin script so the old content editor remains stable. */
const LAYOUT_DRAFT_KEY='hctsui-layout-draft-v3';
const CATEGORY_KIND_LABELS={
  featured_publications:'首頁精選論文',upcoming:'首頁近期活動',contact:'聯絡資訊',
  interest:'研究興趣',education:'學歷',honor:'獎項／榮譽',publication:'論文／作品',
  visit:'學術訪問',talk:'學術報告',organization:'學術活動籌辦',conference:'會議／工作坊',
  teaching:'教學',personal:'個人資訊',generic:'一般項目'
};
const DIRECT_CATEGORY_KINDS=new Set(['contact','interest','education','honor','publication','visit','talk','organization','conference','teaching','personal','generic']);
const ITEM_KIND={conference:'conference',talk:'talk',visit:'visit',organization:'organization',honor:'honor',publication:'publication',teaching:'teaching',interest:'interest',education:'education',generic:'generic',contact:'contact',personal:'personal'};
let layoutBase=null,layoutDraft=null,layoutNotice='',layoutReady=false,layoutPreviewSuppressed=false;

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
  result.pages.sort((a,b)=>(Number(a.order)||0)-(Number(b.order)||0)||String(a.id).localeCompare(String(b.id)));
  result.pages.forEach((p,i)=>{p.order=i;p.name=layoutPair(p.name);if(p.header){p.header={label:layoutPair(p.header.label),title:layoutPair(p.header.title),intro:layoutPair(p.header.intro)}}});
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
    if(saved?.base_signature===layoutSignature(layoutBase)&&saved?.draft){layoutDraft=normalizeLayoutBundle(saved.draft);layoutNotice='已恢復尚未送出的頁面、類別與排序草稿。'}
    else if(saved){localStorage.removeItem(LAYOUT_DRAFT_KEY);layoutNotice='網站結構已更新，舊的頁面與類別草稿已安全丟棄。'}
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
  baseOpenEditor(type,record,options);initLayoutState();
  const root=currentEditor?.root;if(!root)return;
  const cats=categoriesForType(type);
  const selected=record?.category_id||options?.draftOp?.after?.category_id||cats[0]?.id||'';
  const block=document.createElement('div');block.className='field category-selector-field';
  block.innerHTML=`<label>所屬類別</label><select data-path="category_id" id="itemCategorySelector">${cats.map(c=>`<option value="${esc(c.id)}" ${c.id===selected?'selected':''}>${esc(pageName(c.page_id))} → ${esc(categoryName(c))}</option>`).join('')}</select><p class="field-hint">項目會跟隨這個類別出現在對應頁面；移動類別時，所有項目會一起移動。</p>`;
  const optionsBox=root.querySelector('.form-options');(optionsBox||root.firstChild)?.after(block);
  for(const id of ['publicationGroup','publicationCustom','teachingGroup','teachingCustom'])root.querySelector('#'+id)?.closest('.field,div')?.classList.add('legacy-category-hidden');
  if(!cats.length){block.innerHTML='<div class="notice error">目前沒有可容納這種項目的類別。請先到「頁面與類別」新增類別。</div>';root.querySelector('#saveEditor').disabled=true}
};

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
    <button class="button primary" data-save-page="${esc(page.id)}">儲存頁首設定</button>
  </div>`;
}
function renderLayoutManager(){
  initLayoutState();const box=$('#layoutManager');if(!box)return;
  const pageOptions=layoutDraft.pages.map(p=>`<option value="${esc(p.id)}">${esc(pageName(p.id))}</option>`).join('');
  const kindOptions=Object.entries(CATEGORY_KIND_LABELS).map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join('');
  box.innerHTML=`<div class="notice"><strong>類別就是網站的大標題。</strong><p>所有項目都必須放在某個類別中。類別移到另一頁時，裡面的項目會一起移動；網站與 PDF 履歷共用同一套類別名稱。</p>${layoutNotice?`<p>${esc(layoutNotice)}</p>`:''}</div>
  <details class="layout-tool" open><summary><strong>新增類別</strong></summary><div class="layout-tool-body"><div class="pair-grid"><div class="field"><label>中文大標題</label><input id="newCategoryZh"></div><div class="field"><label>英文大標題</label><input id="newCategoryEn"></div></div><div class="pair-grid"><div class="field"><label>所在頁面</label><select id="newCategoryPage">${pageOptions}</select></div><div class="field"><label>項目類型</label><select id="newCategoryKind">${kindOptions}</select></div></div><button class="button primary" id="addCategoryButton">新增類別</button></div></details>
  ${layoutDraft.pages.map(page=>`<details class="layout-page-card" open><summary><strong>${esc(pageName(page.id))}</strong><span class="tag">${layoutDraft.categories.filter(c=>c.page_id===page.id).length} 個類別</span></summary><div class="layout-tool-body"><h3>頁首設定</h3>${pageEditorHtml(page)}<h3>此頁類別</h3>${layoutDraft.categories.filter(c=>c.page_id===page.id).sort((a,b)=>a.order-b.order).map(categoryEditorHtml).join('')||'<p class="muted">此頁尚無類別。</p>'}</div></details>`).join('')}`;
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
  saveLayoutDraft('已新增類別草稿')
}
function setCategoryFromEditor(id,root){const category=layoutDraft.categories.find(c=>c.id===id);if(!category)return;const values=readNestedFields(root,'data-category-field');if(!values.label?.en?.trim()||!values.label?.zh?.trim()||!values.title?.en?.trim()||!values.title?.zh?.trim())return flash('類別的小字與大標題，中英文都不能留白');const oldPage=category.page_id;Object.assign(category,values);category.label=layoutPair(values.label);category.title=layoutPair(values.title);category.intro=layoutPair(values.intro);category.show_on_web=!!values.show_on_web;category.show_on_cv=!!values.show_on_cv;if(oldPage!==category.page_id)category.order=layoutDraft.categories.filter(c=>c.page_id===category.page_id&&c.id!==id).length;layoutDraft=normalizeLayoutBundle(layoutDraft);saveLayoutDraft('已儲存類別設定')}
function setPageFromEditor(id,root){const page=layoutDraft.pages.find(p=>p.id===id);if(!page?.header)return;const values=readNestedFields(root,'data-page-field');if(!values.header?.label?.en?.trim()||!values.header?.label?.zh?.trim()||!values.header?.title?.en?.trim()||!values.header?.title?.zh?.trim())return flash('頁首小字與頁面標題，中英文都不能留白');page.header={label:layoutPair(values.header.label),title:layoutPair(values.header.title),intro:layoutPair(values.header.intro)};saveLayoutDraft('已儲存頁首設定')}
function chooseMoveTarget(category,items){const targets=layoutDraft.categories.filter(c=>c.id!==category.id&&c.kind===category.kind);if(!targets.length)return null;const answer=prompt(`這個類別有 ${items.length} 個項目。請輸入要移入的類別編號：\n`+targets.map((c,i)=>`${i+1}. ${pageName(c.page_id)} → ${categoryName(c)}`).join('\n'));if(answer===null)return undefined;const index=Number(answer)-1;return targets[index]||null}
function deleteCategory(id){const category=layoutDraft.categories.find(c=>c.id===id);if(!category)return;const items=layoutItems(effectiveSite()).filter(x=>layoutDraft.assignments[x.id]?.category_id===id);if(!confirm(`確定刪除類別「${categoryName(category)}」？${items.length?`\n其中 ${items.length} 個項目必須先移到同類型的其他類別。`:''}`))return;if(items.length){const target=chooseMoveTarget(category,items);if(target===undefined)return;if(!target)return flash('沒有可接收這些項目的同類型類別，請先新增類別');const start=Object.values(layoutDraft.assignments).filter(x=>x.category_id===target.id).length;items.forEach((item,i)=>layoutDraft.assignments[item.id]={category_id:target.id,order:start+i})}layoutDraft.categories=layoutDraft.categories.filter(c=>c.id!==id);layoutDraft.cv_category_order=layoutDraft.cv_category_order.filter(x=>x!==id);saveLayoutDraft('已刪除類別草稿')}
function layoutManagerClick(event){const button=event.target.closest('button');if(!button)return;if(button.dataset.saveCategory){const root=button.closest('[data-category-editor]');setCategoryFromEditor(button.dataset.saveCategory,root)}else if(button.dataset.deleteCategory)deleteCategory(button.dataset.deleteCategory);else if(button.dataset.savePage){const root=button.closest('[data-page-editor]');setPageFromEditor(button.dataset.savePage,root)}}

function setupUnifiedOrderUI(){
  const tab=$('#orderTab');if(!tab)return;
  tab.innerHTML=`<div class="toolbar"><div class="field"><label>選擇頁面</label><select id="layoutOrderPage"></select></div><button class="button" id="reloadLayoutOrder">依目前草稿重載</button></div><p class="field-hint">同一頁面的類別與項目會一起顯示。移動類別時，其下所有項目會跟著移動；項目也能改放到同類型的其他類別。</p><div id="layoutOrderEditor" class="scroll"></div>`;
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
function unifiedOrderClick(event){const button=event.target.closest('button');if(!button)return;if(button.dataset.categoryUp)moveCategory(button.dataset.categoryUp,-1);else if(button.dataset.categoryDown)moveCategory(button.dataset.categoryDown,1);else if(button.dataset.itemUp)moveItem(button.dataset.itemUp,-1);else if(button.dataset.itemDown)moveItem(button.dataset.itemDown,1);else if(button.dataset.sortCategory)sortCategory(button.dataset.sortCategory,button.dataset.sortMode);else if(button.dataset.editCategoryJump){switchTab('headings');setTimeout(()=>document.querySelector(`[data-category-editor="${CSS.escape(button.dataset.editCategoryJump)}"]`)?.scrollIntoView({behavior:'smooth',block:'center'}),50)}}
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
sortedRecords=function(){
  if(!site||$('#viewSort').value!=='manual')return baseSortedRecords();
  const data=effectiveSite(),query=norm($('#search').value),filter=$('#filter').value;
  const pageRank=new Map(layoutDraft.pages.map((p,i)=>[p.id,i]));
  const categoryRank=new Map(layoutDraft.categories.map(c=>[c.id,[pageRank.get(c.page_id)??999,Number(c.order)||0]]));
  return allRecords(data).filter(item=>(!filter||item.type===filter)&&(!query||norm(JSON.stringify(item)).includes(query))).sort((a,b)=>{
    const ca=categoryRank.get(a.category_id)||[999,999],cb=categoryRank.get(b.category_id)||[999,999];
    return ca[0]-cb[0]||ca[1]-cb[1]||(Number(a.order)||0)-(Number(b.order)||0)||itemName(a).localeCompare(itemName(b),'zh-Hant');
  });
};
renderRecords=function(){
  const categoryMap=new Map((layoutDraft?.categories||[]).map(c=>[c.id,c]));
  $('#records').innerHTML=sortedRecords().map(item=>{const category=categoryMap.get(item.category_id);return `<div class="row"><span class="tag">${esc(LABEL[item.type]||item.type)}</span><span class="tag">${esc(categoryName(category))}</span><div class="record-heading"><strong>${esc(itemName(item))}</strong><span class="muted record-meta">${esc(recordMeta(item))}</span></div><div class="id">${esc(item.id)}</div><div class="actions"><button class="button" data-edit="${esc(item.id)}">編輯</button><button class="button danger" data-delete="${esc(item.id)}">刪除</button></div></div>`}).join('')||'<p class="muted">沒有符合項目。</p>';
};
const baseRenderPreview=renderPreview;
renderPreview=function(refreshDictionary=true){layoutPreviewSuppressed=true;baseRenderPreview(refreshDictionary);layoutPreviewSuppressed=false;if(layoutDirty()){const op=layoutOperation();$('#preview').insertAdjacentHTML('beforeend',layoutPreviewHtml(op));const text=$('#summary').textContent;$('#summary').textContent=text==='尚無變更。'?'頁面、類別或排序有變更。':text.replace(/。$/,'')+'、頁面／類別 1。'}$('#payload').textContent=JSON.stringify(payload(),null,2)};
const baseRenderAll=renderAll;
renderAll=function(){baseRenderAll();if(site){initLayoutState();renderLayoutManager();renderUnifiedOrder()}};
const baseClearSubmittedDraft=clearSubmittedDraft;
clearSubmittedDraft=function(){localStorage.removeItem(LAYOUT_DRAFT_KEY);baseClearSubmittedDraft()};

function installLayoutCss(){const style=document.createElement('style');style.textContent=`
.legacy-category-hidden{display:none!important}.layout-tool,.layout-page-card{border:1px solid #ded3ca;border-radius:12px;margin:10px 0;background:#fcfaf8}.layout-tool>summary,.layout-page-card>summary{display:flex;gap:8px;align-items:center;justify-content:space-between;cursor:pointer;padding:12px}.layout-tool-body{padding:0 12px 12px}.layout-category-editor{border:1px solid #e1d6ce;border-radius:11px;padding:12px;margin:10px 0;background:#fff}.layout-category-editor textarea,.layout-page-editor textarea{min-height:70px}.layout-order-category{border:1px solid #d9cec5;border-radius:12px;padding:11px;margin:10px 0;background:#faf6f2}.layout-order-category-head,.layout-order-item{display:flex;justify-content:space-between;gap:12px;align-items:center}.layout-order-category-head>div:first-child,.layout-order-item>div:first-child{display:grid;gap:3px;min-width:0}.layout-order-item{padding:9px;border-top:1px solid #e7ddd5;background:#fff}.layout-order-item-actions{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.layout-order-item-actions select{max-width:240px;padding:7px;border:1px solid #cfc4bb;border-radius:8px}.layout-category-editor .actions{margin-top:8px}@media(max-width:700px){.layout-order-category-head,.layout-order-item{align-items:flex-start;flex-direction:column}.layout-order-item-actions{width:100%}}
`;document.head.append(style)}
installLayoutCss();
setupUnifiedOrderUI();
if(site)renderAll();
