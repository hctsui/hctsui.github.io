'use strict';

/* Homepage selections, general-content style editor, and Admin compatibility
   fixes. This file loads after layout-v2.js and intentionally owns the final
   wrappers for shared Admin functions. */
const HOMEPAGE_DRAFT_KEY='hctsui-homepage-draft-v1';
let homepageBase=null,homepageDraft=null,homepageReady=false,homepagePreviewSuppressed=false;

function homepageUniqueIds(value){const result=[];for(const raw of Array.isArray(value)?value:[]){const id=String(raw||'').trim();if(id&&!result.includes(id))result.push(id)}return result}
function homepageLimit(value,fallback=2){const number=Number.parseInt(value,10);return Math.min(50,Math.max(1,Number.isFinite(number)?number:fallback))}
function homepageLegacyActivityIds(data){return(data?.activities||[]).filter(item=>item.show_upcoming).sort((a,b)=>String(a.start_date||'').localeCompare(String(b.start_date||''))||String(a.id).localeCompare(String(b.id))).map(item=>String(item.id))}
function homepageBundle(data,value){
  const settings=data?.settings||{},legacyActivities=homepageLegacyActivityIds(data);
  const defaults={publications:{mode:'latest',limit:homepageLimit(settings.homepage_publication_limit,2),selected_ids:[]},activities:{mode:'manual',limit:Math.max(1,legacyActivities.length),selected_ids:legacyActivities}};
  const raw=value===undefined?settings.homepage:value;
  if(!raw||typeof raw!=='object')return defaults;
  const publications=raw.publications&&typeof raw.publications==='object'?raw.publications:{},activities=raw.activities&&typeof raw.activities==='object'?raw.activities:{};
  return{
    publications:{mode:['latest','oldest','manual'].includes(publications.mode)?publications.mode:defaults.publications.mode,limit:homepageLimit(publications.limit,defaults.publications.limit),selected_ids:homepageUniqueIds(publications.selected_ids)},
    activities:{mode:['soonest','farthest','manual'].includes(activities.mode)?activities.mode:defaults.activities.mode,limit:homepageLimit(activities.limit,defaults.activities.limit),selected_ids:homepageUniqueIds(activities.selected_ids)}
  };
}
function homepageSignature(value){return JSON.stringify(value)}
function homepageComparableSection(config){return config.mode==='manual'?{mode:'manual',selected_ids:[...config.selected_ids]}:{mode:config.mode,limit:config.limit}}
function homepageSectionChanged(before,after){return homepageSignature(homepageComparableSection(before))!==homepageSignature(homepageComparableSection(after))}
function homepageComparableBundle(value){return{publications:homepageComparableSection(value.publications),activities:homepageComparableSection(value.activities)}}
function initHomepageState(){
  if(homepageReady||!site)return;
  homepageBase=homepageBundle(site);homepageDraft=clone(homepageBase);
  try{
    const saved=JSON.parse(localStorage.getItem(HOMEPAGE_DRAFT_KEY)||'null');
    if(saved?.base_signature===homepageSignature(homepageBase)&&saved?.draft){
      homepageDraft=homepageBundle(site,saved.draft);
      if(homepageSignature(homepageComparableBundle(homepageDraft))===homepageSignature(homepageComparableBundle(homepageBase))){homepageDraft=clone(homepageBase);localStorage.removeItem(HOMEPAGE_DRAFT_KEY)}
    }else if(saved)localStorage.removeItem(HOMEPAGE_DRAFT_KEY);
  }catch{localStorage.removeItem(HOMEPAGE_DRAFT_KEY)}
  homepageReady=true;
}
function homepageSubmissionBundle(){
  const result=clone(homepageDraft),data=homepageBaseEffectiveSite();
  const publicationIds=new Set((data?.publications||[]).map(item=>String(item.id))),activityIds=new Set((data?.activities||[]).map(item=>String(item.id)));
  result.publications.selected_ids=result.publications.selected_ids.filter(id=>publicationIds.has(id));
  result.activities.selected_ids=result.activities.selected_ids.filter(id=>activityIds.has(id));
  return result;
}
function homepageDirty(){return homepageReady&&homepageSignature(homepageComparableBundle(homepageSubmissionBundle()))!==homepageSignature(homepageComparableBundle(homepageBase))}
function homepageOperation(){return{op:'homepage',before:clone(homepageBase),after:homepageSubmissionBundle()}}
function applyHomepageToData(data,value){data.settings=data.settings||{};data.settings.homepage=clone(value);data.settings.homepage_publication_limit=value.publications.limit;return data}
function refreshHomepageSurfaces(){
  renderHomepageManager();
  renderDrafts();
  renderPreview();
  if(typeof renderRecords==='function')renderRecords();
}
function saveHomepageDraft(message=''){
  initHomepageState();
  if(homepageDirty())localStorage.setItem(HOMEPAGE_DRAFT_KEY,JSON.stringify({base_signature:homepageSignature(homepageBase),draft:homepageDraft}));
  else localStorage.removeItem(HOMEPAGE_DRAFT_KEY);
  if(message)flash(message);
  refreshHomepageSurfaces();
}
function homepageToday(){try{return new Date().toLocaleDateString('sv-SE',{timeZone:site?.settings?.timezone||'Asia/Tokyo'})}catch{return new Date().toISOString().slice(0,10)}}
function homepageItemTitle(item){return title(item)||item?.id||'未命名項目'}
function homepageDate(item,section){return section==='activities'?String(item?.start_date||''):String(item?.date||item?.year||'')}
function homepageCandidates(data,section){
  const items=section==='publications'?[...(data?.publications||[])]:[...(data?.activities||[])].filter(item=>String(item.end_date||item.start_date||'')>=homepageToday());
  return items.sort((a,b)=>homepageDate(b,section).localeCompare(homepageDate(a,section))||String(a.id).localeCompare(String(b.id)));
}
function homepageResolvedIds(data,section,config){
  const items=homepageCandidates(data,section),byId=new Map(items.map(item=>[String(item.id),item]));
  if(config.mode==='manual')return config.selected_ids.filter(id=>byId.has(id));
  const sorted=[...items].sort((a,b)=>{const comparison=homepageDate(a,section).localeCompare(homepageDate(b,section))||String(a.id).localeCompare(String(b.id));return config.mode==='latest'||config.mode==='farthest'?-comparison:comparison});
  return sorted.slice(0,config.limit).map(item=>String(item.id));
}
function homepageNameById(data,id){const item=[...(data?.publications||[]),...(data?.activities||[])].find(entry=>String(entry.id)===String(id));return item?homepageItemTitle(item):id}
function homepageModeLabel(section,mode){return({publications:{latest:'固定最新 N 篇',oldest:'固定最舊 N 篇',manual:'手動選擇與排序'},activities:{soonest:'最近即將開始的 N 筆',farthest:'日期最遠的 N 筆',manual:'手動選擇與排序'}})[section][mode]||mode}
function homepageManualHtml(data,section,config){
  const candidates=homepageCandidates(data,section),byId=new Map(candidates.map(item=>[String(item.id),item])),selected=config.selected_ids.filter(id=>byId.has(id));
  const selectedRows=selected.map((id,index)=>{const item=byId.get(id);return`<div class="homepage-selected-row"><div><strong>${esc(homepageItemTitle(item))}</strong><span class="muted">${esc(homepageDate(item,section))}</span></div><div class="actions"><button class="button" data-home-up="${esc(section)}:${esc(id)}" ${index===0?'disabled':''}>上移</button><button class="button" data-home-down="${esc(section)}:${esc(id)}" ${index===selected.length-1?'disabled':''}>下移</button><button class="button danger" data-home-remove="${esc(section)}:${esc(id)}">移除</button></div></div>`}).join('');
  const available=candidates.filter(item=>!selected.includes(String(item.id))).map(item=>`<button class="homepage-choice" data-home-add="${esc(section)}:${esc(item.id)}"><span>加入</span><strong>${esc(homepageItemTitle(item))}</strong><small>${esc(homepageDate(item,section))}</small></button>`).join('');
  return`<div class="homepage-manual"><h4>目前顯示順序</h4>${selectedRows||'<p class="muted">尚未選擇；首頁這一欄會是空的。</p>'}<h4>可加入項目</h4><div class="homepage-choice-list">${available||'<p class="muted">沒有其他可加入項目。</p>'}</div>${section==='activities'?'<p class="field-hint">只列出尚未結束的活動；活動結束後會自動從首頁隱藏。</p>':''}</div>`;
}
function homepageSectionHtml(data,section){
  const config=homepageDraft[section],isPublications=section==='publications';
  const options=isPublications?[['latest','固定最新 N 篇'],['oldest','固定最舊 N 篇'],['manual','手動選擇與排序']]:[['soonest','最近即將開始的 N 筆'],['farthest','日期最遠的 N 筆'],['manual','手動選擇與排序']];
  const resultIds=homepageResolvedIds(data,section,config);
  return`<section class="homepage-card"><h3>${isPublications?'精選論文':'近期活動'}</h3><div class="pair-grid"><div class="field"><label>選取方式</label><select data-home-mode="${section}">${options.map(([value,label])=>`<option value="${value}" ${config.mode===value?'selected':''}>${label}</option>`).join('')}</select></div>${config.mode==='manual'?'<div class="field"><label>目前數量</label><div class="preview-value">'+resultIds.length+' 筆</div></div>':`<div class="field"><label>N（1–50）</label><input type="number" min="1" max="50" value="${config.limit}" data-home-limit="${section}"></div>`}</div>${config.mode==='manual'?homepageManualHtml(data,section,config):`<div class="notice"><strong>首頁目前會顯示 ${resultIds.length} 筆：</strong><ol>${resultIds.map(id=>`<li>${esc(homepageNameById(data,id))}</li>`).join('')}</ol></div>`}</section>`;
}
function ensureHomepagePanel(){
  const tab=$('#orderTab');if(!tab)return null;
  let box=$('#homepageManager');
  if(!box){tab.insertAdjacentHTML('beforeend','<details class="order-homepage-panel"><summary><strong>首頁精選與近期活動</strong></summary><div id="homepageManager"></div></details>');box=$('#homepageManager')}
  return box;
}
function renderHomepageManager(){
  initHomepageState();const box=ensureHomepagePanel();if(!box||!homepageReady)return;
  const data=homepageBaseEffectiveSite(),status=homepageDirty()?'<span class="tag homepage-dirty-tag">有未送出變更</span>':'<span class="tag">目前無變更</span>';
  box.innerHTML=`<div class="notice"><strong>只控制首頁雙欄，不會刪除原始資料。</strong><p>自動模式會隨內容更新；手動模式可指定項目與順序。每次選擇都會立即保存為本機草稿。</p>${status}</div>${homepageSectionHtml(data,'publications')}${homepageSectionHtml(data,'activities')}<div class="actions"><button class="button" id="resetHomepageDraft" ${homepageDirty()?'':'disabled'}>移除首頁精選草稿</button></div>`;
  box.onchange=homepageManagerChange;box.onclick=homepageManagerClick;
}
function homepageManagerChange(event){
  const mode=event.target.closest('[data-home-mode]'),limit=event.target.closest('[data-home-limit]');
  if(mode){homepageDraft[mode.dataset.homeMode].mode=mode.value;saveHomepageDraft('已更新首頁選取方式')}
  else if(limit){homepageDraft[limit.dataset.homeLimit].limit=homepageLimit(limit.value,homepageDraft[limit.dataset.homeLimit].limit);saveHomepageDraft('已更新首頁顯示數量')}
}
function splitHomepageAction(value){const index=value.indexOf(':');return[value.slice(0,index),value.slice(index+1)]}
function homepageManagerClick(event){
  const button=event.target.closest('button');if(!button)return;
  if(button.id==='resetHomepageDraft'){clearHomepageDraft();return}
  for(const action of ['homeAdd','homeRemove','homeUp','homeDown']){
    if(button.dataset[action]===undefined)continue;
    const[section,id]=splitHomepageAction(button.dataset[action]),ids=homepageDraft[section].selected_ids,index=ids.indexOf(id);
    if(action==='homeAdd'&&index<0)ids.push(id);
    if(action==='homeRemove'&&index>=0)ids.splice(index,1);
    if(action==='homeUp'&&index>0)[ids[index-1],ids[index]]=[ids[index],ids[index-1]];
    if(action==='homeDown'&&index>=0&&index<ids.length-1)[ids[index],ids[index+1]]=[ids[index+1],ids[index]];
    saveHomepageDraft('已更新首頁手動清單');return;
  }
}
function homepagePreviewHtml(op){
  const data=homepageBaseEffectiveSite();
  const changedSections=['publications','activities'].filter(section=>homepageSectionChanged(op.before[section],op.after[section]));
  const rows=changedSections.map(section=>{const before=op.before[section],after=op.after[section],beforeIds=homepageResolvedIds(data,section,before),afterIds=homepageResolvedIds(data,section,after);return`<div class="preview-card"><h4>${section==='publications'?'精選論文':'近期活動'}</h4><div class="preview-columns"><div><strong>修改前</strong><p>${esc(homepageModeLabel(section,before.mode))}${before.mode==='manual'?'':` · N=${before.limit}`}</p><ol>${beforeIds.map(id=>`<li>${esc(homepageNameById(data,id))}</li>`).join('')}</ol></div><div><strong>修改後</strong><p>${esc(homepageModeLabel(section,after.mode))}${after.mode==='manual'?'':` · N=${after.limit}`}</p><ol>${afterIds.map(id=>`<li>${esc(homepageNameById(data,id))}</li>`).join('')}</ol></div></div></div>`}).join('');
  const label=changedSections.length===1?(changedSections[0]==='publications'?'精選論文':'近期活動'):'首頁精選與近期活動';
  return`<details class="diff"><summary><strong>${label}</strong></summary>${rows}</details>`;
}
function clearHomepageDraft(shouldRender=true){initHomepageState();homepageDraft=clone(homepageBase);localStorage.removeItem(HOMEPAGE_DRAFT_KEY);if(shouldRender){flash('已移除首頁精選草稿');refreshHomepageSurfaces()}}

const homepageBaseRenderDrafts=renderDrafts;
renderDrafts=function(){
  homepageBaseRenderDrafts();if(!homepageDirty())return;
  const box=$('#drafts');if(!contentOps().length)box.innerHTML='';
  box.insertAdjacentHTML('beforeend','<div class="row draft-row homepage-draft-row"><span class="tag">首頁設定</span><strong>首頁精選與近期活動</strong><span class="muted">只包含實際變更的區塊</span><div class="actions"><button class="button" data-edit-homepage-draft>修改草稿</button><button class="button" data-preview-homepage-draft>預覽</button><button class="button danger" data-drop-homepage-draft>移除</button></div></div>');
};
$('#drafts').addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.hasAttribute('data-edit-homepage-draft')){switchTab('order');document.querySelector('.order-homepage-panel')?.setAttribute('open','');document.querySelector('.order-homepage-panel')?.scrollIntoView({behavior:'smooth',block:'start'});return}
  if(button.hasAttribute('data-preview-homepage-draft')){$('#editorPreview').innerHTML=`<div class="notice"><strong>草稿預覽 · 首頁設定</strong></div>${homepagePreviewHtml(homepageOperation())}`;return}
  if(button.hasAttribute('data-drop-homepage-draft'))clearHomepageDraft();
});

const homepageBaseEffectiveSite=effectiveSite;
effectiveSite=function(){const data=homepageBaseEffectiveSite();initHomepageState();return applyHomepageToData(data,homepageSubmissionBundle())};
const homepageBasePayload=payload;
payload=function(){const result=homepageBasePayload();if(!homepagePreviewSuppressed&&homepageDirty())result.operations.push(homepageOperation());return result};
const homepageBaseRenderPreview=renderPreview;
renderPreview=function(refreshDictionary=true){
  homepagePreviewSuppressed=true;homepageBaseRenderPreview(refreshDictionary);homepagePreviewSuppressed=false;
  if(homepageDirty()){const op=homepageOperation();$('#preview').insertAdjacentHTML('beforeend',homepagePreviewHtml(op));const text=$('#summary').textContent;$('#summary').textContent=text==='尚無變更。'?'首頁精選有變更。':text.replace(/。$/,'')+'、首頁精選 1。'}
  $('#payload').textContent=JSON.stringify(payload(),null,2);
};
const homepageBaseHistoryPreview=historyOperationPreviewHtml;
historyOperationPreviewHtml=function(h){if(h?.action==='homepage')return`<div class="notice"><strong>還原預覽 · 首頁精選</strong><div>${esc(historyTitle(h))}</div></div>${homepagePreviewHtml({before:h.before,after:h.after})}`;return homepageBaseHistoryPreview(h)};
const homepageBaseUndoPreview=undoPreviewHtml;
undoPreviewHtml=function(h){if(h?.action==='homepage')return homepagePreviewHtml({before:h.after,after:h.before});return homepageBaseUndoPreview(h)};
const homepageBaseRenderAll=renderAll;
renderAll=function(){homepageBaseRenderAll();if(site)renderHomepageManager()};
const homepageBaseClearSubmittedDraft=clearSubmittedDraft;
clearSubmittedDraft=function(){localStorage.removeItem(HOMEPAGE_DRAFT_KEY);homepageBaseClearSubmittedDraft()};

/* Keep the modern record badges after search, filtering, or view sorting.
   The legacy page stored the old renderRecords function itself in handlers;
   wrappers below resolve the newest renderer at event time. */
function bindModernRecordControls(){
  const search=$('#search'),filter=$('#filter'),viewSort=$('#viewSort');
  if(search)search.oninput=()=>renderRecords();
  if(filter)filter.onchange=()=>renderRecords();
  if(viewSort)viewSort.onchange=()=>renderRecords();
}

/* Every item gets a 搬移 selector. It stays visible but disabled when no
   category with the same accepted format exists. */
orderCategoryCard=function(category,index,total,map,cvMode=false){
  const ids=categoryItemIds(category.id),compatible=layoutDraft.categories.filter(c=>c.kind===category.kind&&c.id!==category.id).sort(categorySort);
  return `<div class="layout-order-category" data-order-category="${esc(category.id)}"><div class="layout-order-category-head"><div><span class="tag">${esc(CATEGORY_KIND_LABELS[category.kind]||category.kind)}</span><strong>${index+1}. ${esc(categoryName(category))}</strong><span class="muted">${esc(pageName(category.page_id))} · ${ids.length} 個項目</span></div><div class="actions"><button class="button" data-category-up="${esc(category.id)}" ${index===0?'disabled':''}>類別 ↑</button><button class="button" data-category-down="${esc(category.id)}" ${index===total-1?'disabled':''}>類別 ↓</button><button class="button" data-edit-category-jump="${esc(category.id)}">編輯類別</button></div></div>${!cvMode?`<div class="order-sort-tools"><span class="muted">此類別快速排序：</span><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="newest">日期新到舊</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="oldest">日期舊到新</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="title">名稱</button></div>`:''}<div>${ids.map((id,i)=>{const item=map.get(id);if(!item)return'';let moveControl;if(cvMode)moveControl='<select class="move-category-select" disabled><option>搬移（PDF 檢視不可用）</option></select>';else if(compatible.length)moveControl=`<select class="move-category-select" data-move-item="${esc(id)}"><option value="">搬移…</option>${compatible.map(c=>`<option value="${esc(c.id)}">${esc(pageName(c.page_id))} → ${esc(categoryName(c))}</option>`).join('')}</select>`;else moveControl='<select class="move-category-select" disabled><option>搬移（無相容類別）</option></select>';return `<div class="layout-order-item"><div><strong>${i+1}. ${esc(itemName(item))}</strong><span class="muted">${esc(itemMetaChinese(item))}</span></div><div class="layout-order-item-actions"><button class="button" data-item-up="${esc(id)}" ${i===0?'disabled':''}>↑</button><button class="button" data-item-down="${esc(id)}" ${i===ids.length-1?'disabled':''}>↓</button>${moveControl}</div></div>`}).join('')||'<p class="muted">此類別目前沒有項目。</p>'}</div></div>`;
};
const homepageBaseUnifiedOrderChange=unifiedOrderChange;
unifiedOrderChange=function(event){const select=event.target.closest('[data-move-item]');if(select&&select.value){homepageBaseUnifiedOrderChange(event);flash('已搬移項目');return}homepageBaseUnifiedOrderChange(event)};

/* General-content display styles. These six names describe rendering only;
   editing may change style and therefore move the record to a compatible
   category. */
const GENERAL_STYLE_KINDS=new Set(['generic','education','interest','contact','personal','honor']);
const GENERAL_STYLE_INFO={
  generic:{name:'標準時間軸',summary:'日期在左，主標題、機構與說明在右；適合一般經歷。',sample:'<span class="style-date">2026</span><span><b>項目標題</b><small>機構 · 說明文字</small></span>'},
  education:{name:'雙欄紀錄',summary:'左欄固定日期，右欄分層顯示學位／項目與機構。',sample:'<span class="style-date">2024–26</span><span><b>學位或項目</b><small>學校／機構</small></span>'},
  interest:{name:'標題清單',summary:'以標題為主的簡潔清單，補充文字置於下一行。',sample:'<span><b>研究方向</b><small>補充說明與連結</small></span>'},
  contact:{name:'資訊卡片',summary:'每筆內容成為獨立卡片，適合聯絡方式或重點資訊。',sample:'<span class="style-card"><b>電子郵件</b><small>name@example.com</small></span>'},
  personal:{name:'標籤列表',summary:'短標籤與內容並列，適合語言、技能或個人資料。',sample:'<span class="style-pill">語言</span><span><b>中文、英文、日文</b></span>'},
  honor:{name:'精簡時間軸',summary:'年份與獎項壓縮在一行，適合榮譽與簡短里程碑。',sample:'<span class="style-date">2026</span><span><b>獎項名稱</b><small>頒發機構</small></span>'}
};
function generalStyleCards(selected){return`<details class="general-style-guide" open><summary><strong>六種顯示風格預覽</strong></summary><div class="general-style-grid">${GENERAL_FORMAT_ORDER.map(kind=>{const info=GENERAL_STYLE_INFO[kind];return`<article class="general-style-card ${selected===kind?'selected':''}" data-style-preview-kind="${kind}"><div class="general-style-card-head"><strong>${esc(info.name)}</strong><span>${esc(kind)}</span></div><div class="general-style-sample ${kind}">${info.sample}</div><p>${esc(info.summary)}</p></article>`}).join('')}</div></details>`}
function updateGeneralStyleCards(root,kind){root.querySelectorAll('[data-style-preview-kind]').forEach(card=>card.classList.toggle('selected',card.dataset.stylePreviewKind===kind))}
function generalCategories(kind){return layoutDraft.categories.filter(c=>GENERAL_STYLE_KINDS.has(c.kind)&&(!kind||c.kind===kind)).sort(categorySort)}
function decorateGeneralEditor(type,record){
  if(!GENERAL_STYLE_KINDS.has(type))return;
  const root=currentEditor?.root,categoryBlock=root?.querySelector('.category-selector-field');if(!root||!categoryBlock)return;
  root.querySelector('.general-format-field')?.remove();root.querySelector('.general-style-guide')?.remove();
  const styleBlock=document.createElement('div');styleBlock.className='field general-format-field';
  const editing=!!record,initial=editing?String(record.type||type):(type==='generic'?'':type);
  styleBlock.innerHTML=`<label>顯示風格</label><select id="generalContentFormat"><option value="">請選擇顯示風格…</option>${GENERAL_FORMAT_ORDER.map(kind=>`<option value="${esc(kind)}" ${initial===kind?'selected':''}>${esc(GENERAL_FORMAT_LABELS[kind])}</option>`).join('')}</select><p class="field-hint">${editing?'可改成其他顯示風格；儲存後會搬移到能接受該風格的類別。':'風格只描述版面，不限制內容用途。'}</p>`;
  categoryBlock.before(styleBlock);categoryBlock.insertAdjacentHTML('afterend',generalStyleCards(initial));
  const styleSelect=styleBlock.querySelector('#generalContentFormat'),categorySelect=categoryBlock.querySelector('#itemCategorySelector'),hint=categoryBlock.querySelector('.field-hint'),saveButton=root.querySelector('#saveEditor');
  const refresh=()=>{
    const kind=styleSelect.value,choices=generalCategories(kind),old=categorySelect.value,preferred=choices.some(c=>c.id===old)?old:(choices.some(c=>c.id===record?.category_id)?record.category_id:choices[0]?.id||'');
    categorySelect.innerHTML=choices.map(c=>`<option value="${esc(c.id)}" ${c.id===preferred?'selected':''}>${esc(pageName(c.page_id))} → ${esc(categoryName(c))}</option>`).join('');
    categorySelect.disabled=!kind||!choices.length;if(saveButton)saveButton.disabled=!kind||!choices.length;
    hint.textContent=!kind?'請先選擇顯示風格。':choices.length?'可在這裡選擇所屬類別；排序頁也能用「搬移」調整。':'目前沒有使用這種風格的類別，請先新增相同風格的類別。';
    updateGeneralStyleCards(root,kind);
  };
  styleSelect.onchange=refresh;refresh();
  root.querySelector('#previewEditor').onclick=previewGeneralCurrent;
  root.querySelector('#saveEditor').onclick=saveGeneralCurrent;
}
function generalEditorValue(){
  const originalType=String(currentEditor.record?.type||currentEditor.type),targetType=String(currentEditor.root.querySelector('#generalContentFormat')?.value||originalType),targetCategory=String(currentEditor.root.querySelector('#itemCategorySelector')?.value||''),collected=collectEditor(currentEditor.type,currentEditor.record),o=collected.o;
  o.type=targetType;o.category_id=targetCategory;
  if(targetType==='honor'){
    const visible=String(o.date_label?.en||o.date_label?.zh||o.start_date||o.year||'').match(/\d{4}/)?.[0];o.year=Number(visible)||Number(o.year)||new Date().getFullYear();
  }else if(originalType==='honor'){
    const year=Number(o.year)||new Date().getFullYear();o.start_date=o.start_date||`${year}-01-01`;o.end_date=o.end_date||o.start_date;o.date_label=o.date_label||{en:String(year),zh:String(year)};o.description=o.description||{en:'',zh:''};
  }
  return{o,notes:collected.notes,originalType,targetType,targetCategory};
}
function generalValidation(value){
  if(!value.targetType||!GENERAL_STYLE_KINDS.has(value.targetType))return['請選擇顯示風格'];
  if(!value.targetCategory)return['請選擇所屬類別'];
  const category=layoutDraft.categories.find(c=>c.id===value.targetCategory);if(!category||category.kind!==value.targetType)return['所屬類別不能接受所選顯示風格'];
  return validateEditorObject(value.targetType,value.o);
}
function previewGeneralCurrent(){
  const value=generalEditorValue(),errors=generalValidation(value);if(errors.length){$('#editorPreview').innerHTML=`<div class="notice error"><strong>請先修正</strong><ul>${errors.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;return}
  $('#editorPreview').innerHTML=`<div class="notice success"><strong>這一筆的預覽</strong><p>顯示風格：${esc(GENERAL_STYLE_INFO[value.targetType].name)}；所屬類別：${esc(categoryName(layoutDraft.categories.find(c=>c.id===value.targetCategory)))}</p></div>${objectPreviewHtml(value.targetType,value.o)}`;
}
function replaceDraftsForId(id,operations){for(let i=draft.length-1;i>=0;i--){const op=draft[i];if(['add','update','delete'].includes(op.op)&&(op.id||op.after?.id)===id)draft.splice(i,1)}draft.push(...operations)}
function saveGeneralCurrent(){
  const value=generalEditorValue(),errors=generalValidation(value);if(errors.length)return flash(errors.join('；'));
  const id=value.o.id,record=currentEditor.record,isDraft=Number.isInteger(currentEditor.draftIndex),originalBefore=currentEditor.originalBefore||record,crossSection=(value.originalType==='honor')!==(value.targetType==='honor');
  if(isDraft){
    const old=draft[currentEditor.draftIndex];if(!old)return flash('找不到這筆草稿，請重新整理');
    if(old.op==='add'){draft[currentEditor.draftIndex]={...old,type:value.targetType,after:value.o,notes:value.notes}}
    else if(old.op==='update'){
      const before=currentEditor.originalBefore||old.before,after={...value.o,category_id:before.category_id};
      if(crossSection){draft.splice(currentEditor.draftIndex,1,{op:'delete',type:before.type,id,before},{op:'add',type:value.targetType,after,notes:value.notes})}
      else draft[currentEditor.draftIndex]={...old,type:value.targetType,before,after,notes:value.notes};
    }else return flash('這種草稿不能用表格修改');
    saveLocal();
  }else if(record){
    const after={...value.o,category_id:record.category_id};
    if(crossSection)replaceDraftsForId(id,[{op:'delete',type:record.type,id,before:record},{op:'add',type:value.targetType,after,notes:value.notes}]);
    else replaceDraftsForId(id,[{op:'update',type:value.targetType,id,before:record,after,notes:value.notes}]);
    saveLocal();
  }else{queueOperation({op:'add',type:value.targetType,after:value.o,notes:value.notes})}
  if(record||isDraft){
    const oldState=layoutDraft.assignments[id]||{},sameCategory=oldState.category_id===value.targetCategory,order=sameCategory?Number(oldState.order??0):categoryItemIds(value.targetCategory).filter(itemId=>itemId!==id).length;
    layoutDraft.assignments[id]={category_id:value.targetCategory,order};saveLayoutDraft('');
  }
  switchTab('draft');flash(isDraft?'草稿變更已儲存':'已加入批次草稿');
}
const homepageBaseOpenEditor=openEditor;
openEditor=function(type,record,options={}){homepageBaseOpenEditor(type,record,options);decorateGeneralEditor(type,record)};

function installHomepageAndStyleCss(){const style=document.createElement('style');style.textContent=`
.homepage-card{border:1px solid #ded3ca;border-radius:12px;padding:14px;margin:12px 0;background:#fcfaf8}.homepage-card h3{margin-top:0}.homepage-card h4{margin:14px 0 8px}.homepage-selected-row{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px;border-top:1px solid #e7ddd5;background:#fff}.homepage-selected-row>div:first-child{display:grid;gap:3px;min-width:0}.homepage-choice-list{display:grid;gap:7px}.homepage-choice{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;text-align:left;padding:9px 11px;border:1px solid #d9cec5;border-radius:9px;background:#fff;color:inherit;cursor:pointer}.homepage-choice:hover{border-color:#8f6f59}.homepage-choice span{font-weight:700;color:#79543d}.homepage-choice small{color:#70665e}.homepage-card ol{margin-bottom:0}.homepage-dirty-tag{background:#f2dfb8;color:#68420b}.move-category-select:disabled{opacity:.5;cursor:not-allowed;background:#eee9e5}.general-style-guide{margin:12px 0;border:1px solid #ded3ca;border-radius:12px;background:#fcfaf8}.general-style-guide>summary{cursor:pointer;padding:12px}.general-style-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:0 12px 12px}.general-style-card{border:1px solid #ddd2c9;border-radius:11px;padding:10px;background:#fff;transition:.15s}.general-style-card.selected{border-color:#8d493d;box-shadow:inset 4px 0 #8d493d;background:#fff8f4}.general-style-card-head{display:flex;justify-content:space-between;gap:8px}.general-style-card-head span{font:11px ui-monospace,monospace;color:#81766e}.general-style-card p{font-size:.78rem;color:#6f655e;margin:.55rem 0 0}.general-style-sample{min-height:58px;margin-top:9px;padding:9px;border-radius:8px;background:#f5f0ec;display:flex;gap:9px;align-items:flex-start}.general-style-sample>span{display:grid;gap:3px}.general-style-sample small{display:block;color:#776c64}.general-style-sample.interest{display:block}.general-style-sample.contact{display:block}.general-style-sample.personal{align-items:center}.style-date{min-width:58px;font-weight:800;color:#8d493d}.style-card{padding:7px 9px;border:1px solid #d8cdc5;border-radius:8px;background:#fff}.style-pill{display:inline-flex!important;padding:3px 8px;border-radius:999px;background:#e8dfd8;font-weight:800}@media(max-width:700px){.homepage-selected-row{align-items:flex-start;flex-direction:column}.homepage-selected-row .actions{width:100%}.homepage-choice{grid-template-columns:auto 1fr}.homepage-choice small{grid-column:2}.general-style-grid{grid-template-columns:1fr}}
`;document.head.append(style)}
installHomepageAndStyleCss();
bindModernRecordControls();
if(site)renderAll();
