'use strict';

/* Homepage selections, general-content style editor, and Admin compatibility
   fixes. This file loads after layout-v2.js and intentionally owns the final
   wrappers for shared Admin functions. */
const HOMEPAGE_DRAFT_KEY='hctsui-homepage-draft-v1';
const GENERAL_LAYOUT_LINK_KEY='hctsui-general-layout-links-v1';
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
function homepageComparableSection(config,section='',data=null){
  const result={mode:config.mode,limit:config.limit};
  if(section&&data)result.resolved_ids=homepageResolvedIds(data,section,config);
  else result.selected_ids=[...config.selected_ids];
  return result;
}
function homepageSectionChanged(before,after,section='',data=null){return homepageSignature(homepageComparableSection(before,section,data))!==homepageSignature(homepageComparableSection(after,section,data))}
function homepageComparableBundle(value,data=null){return{publications:homepageComparableSection(value.publications,'publications',data),activities:homepageComparableSection(value.activities,'activities',data)}}
function initHomepageState(){
  if(homepageReady||!site)return;
  homepageBase=homepageBundle(site);homepageDraft=clone(homepageBase);
  try{
    const saved=JSON.parse(localStorage.getItem(HOMEPAGE_DRAFT_KEY)||'null');
    if(saved?.base_signature===homepageSignature(homepageBase)&&saved?.draft){
      homepageDraft=homepageBundle(site,saved.draft);
      if(homepageSignature(homepageComparableBundle(homepageDraft,site))===homepageSignature(homepageComparableBundle(homepageBase,site))){homepageDraft=clone(homepageBase);localStorage.removeItem(HOMEPAGE_DRAFT_KEY)}
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
function homepageDirty(){if(!homepageReady)return false;const data=homepageBaseEffectiveSite();return homepageSignature(homepageComparableBundle(homepageSubmissionBundle(),data))!==homepageSignature(homepageComparableBundle(homepageBase,data))}
function homepageOperation(){return{op:'homepage',before:clone(homepageBase),after:homepageSubmissionBundle()}}
function applyHomepageToData(data,value){data.settings=data.settings||{};data.settings.homepage=clone(value);data.settings.homepage_publication_limit=value.publications.limit;return data}
function removeLegacyHomepagePanel(){document.querySelectorAll('.order-homepage-panel').forEach(panel=>panel.remove())}
function bindIntegratedHomepageOrderControls(){
  const editor=$('#layoutOrderEditor');if(!editor)return;
  editor.onclick=integratedHomepageOrderClick;
  editor.onchange=integratedHomepageOrderChange;
}
function refreshHomepageSurfaces(){
  removeLegacyHomepagePanel();
  if($('#layoutOrderPage')?.value==='home'&&typeof renderUnifiedOrder==='function')renderUnifiedOrder();
  bindIntegratedHomepageOrderControls();
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
function homepageAutomaticIds(data,section,config){
  const items=homepageCandidates(data,section);
  items.sort((a,b)=>{const comparison=homepageDate(a,section).localeCompare(homepageDate(b,section))||String(a.id).localeCompare(String(b.id));return config.mode==='latest'||config.mode==='farthest'?-comparison:comparison});
  return items.slice(0,config.limit).map(item=>String(item.id));
}
function homepageResolvedIds(data,section,config){
  const items=homepageCandidates(data,section),available=new Set(items.map(item=>String(item.id)));
  if(config.mode==='manual')return config.selected_ids.filter(id=>available.has(id));
  const automatic=homepageAutomaticIds(data,section,config),automaticSet=new Set(automatic),preferred=config.selected_ids.filter(id=>automaticSet.has(id));
  return[...preferred,...automatic.filter(id=>!preferred.includes(id))];
}
function homepageNameById(data,id){const item=[...(data?.publications||[]),...(data?.activities||[])].find(entry=>String(entry.id)===String(id));return item?homepageItemTitle(item):id}
function homepageModeLabel(section,mode){return({publications:{latest:'固定最新 N 篇',oldest:'固定最舊 N 篇',manual:'手動選擇與排序'},activities:{soonest:'最近即將開始的 N 筆',farthest:'日期最遠的 N 筆',manual:'手動選擇與排序'}})[section][mode]||mode}
function homepageSelectedRowsHtml(data,section,config){
  const candidates=homepageCandidates(data,section),byId=new Map(candidates.map(item=>[String(item.id),item])),selected=homepageResolvedIds(data,section,config);
  const rows=selected.map((id,index)=>{const item=byId.get(id);if(!item)return'';const remove=config.mode==='manual'?`<button class="button danger" data-home-remove="${esc(section)}:${esc(id)}">移除</button>`:'';return`<div class="homepage-selected-row layout-order-item"><div><strong>${esc(homepageItemTitle(item))}</strong><span class="muted">${esc(homepageDate(item,section))}</span></div><div class="layout-order-item-actions"><button class="button" data-home-up="${esc(section)}:${esc(id)}" ${index===0?'disabled':''}>上移</button><button class="button" data-home-down="${esc(section)}:${esc(id)}" ${index===selected.length-1?'disabled':''}>下移</button>${remove}</div></div>`}).join('');
  return`<div class="homepage-order-list"><h4>目前顯示順序</h4>${rows||'<p class="muted">尚未選擇；首頁這一欄會是空的。</p>'}</div>`;
}
function homepageAvailableHtml(data,section,config){
  if(config.mode!=='manual')return'';
  const candidates=homepageCandidates(data,section),selected=new Set(homepageResolvedIds(data,section,config));
  const available=candidates.filter(item=>!selected.has(String(item.id))).map(item=>`<button class="homepage-choice" data-home-add="${esc(section)}:${esc(item.id)}"><span>加入</span><strong>${esc(homepageItemTitle(item))}</strong><small>${esc(homepageDate(item,section))}</small></button>`).join('');
  return`<div class="homepage-manual"><h4>可加入項目</h4><div class="homepage-choice-list">${available||'<p class="muted">沒有其他可加入項目。</p>'}</div>${section==='activities'?'<p class="field-hint">只列出尚未結束的活動；活動結束後會自動從首頁隱藏。</p>':''}</div>`;
}
function homepageSectionBodyHtml(data,section){
  const config=homepageDraft[section],isPublications=section==='publications';
  const options=isPublications?[['latest','固定最新 N 篇'],['oldest','固定最舊 N 篇'],['manual','手動選擇與排序']]:[['soonest','最近即將開始的 N 筆'],['farthest','日期最遠的 N 筆'],['manual','手動選擇與排序']];
  const resultIds=homepageResolvedIds(data,section,config),countField=config.mode==='manual'?`<div class="field"><label>目前數量</label><div class="preview-value">${resultIds.length} 筆</div></div>`:`<div class="field"><label>N（1–50）</label><input type="number" min="1" max="50" value="${config.limit}" data-home-limit="${section}"></div>`;
  const hint=config.mode==='manual'?'可自行加入、移除與排序；下方順序就是首頁顯示順序。':'系統依日期更新入選項目；下方仍可調整首頁顯示順序。';
  return`<div class="homepage-order-settings"><div class="pair-grid"><div class="field"><label>選取方式</label><select data-home-mode="${section}">${options.map(([value,label])=>`<option value="${value}" ${config.mode===value?'selected':''}>${label}</option>`).join('')}</select></div>${countField}</div><p class="field-hint homepage-order-help">${hint} 變更會自動存成草稿。</p></div>${homepageSelectedRowsHtml(data,section,config)}${homepageAvailableHtml(data,section,config)}`;
}
function homepageOrderCategoryCard(category,index,total,section){
  const data=homepageBaseEffectiveSite(),resultIds=homepageResolvedIds(data,section,homepageDraft[section]),sectionDirty=homepageSectionChanged(homepageBase[section],homepageSubmissionBundle()[section],section,data);
  const status=sectionDirty?'<span class="tag homepage-status-tag homepage-dirty-tag">有未送出變更</span>':'<span class="tag homepage-status-tag">目前無變更</span>';
  const reset=`<button class="button" data-reset-home-section="${esc(section)}" ${sectionDirty?'':'disabled'}>重設</button>`;
  return`<div class="layout-order-category homepage-order-category" data-order-category="${esc(category.id)}" data-homepage-section="${esc(section)}"><div class="layout-order-category-head"><div><span class="tag">${esc(CATEGORY_KIND_LABELS[category.kind]||category.kind)}</span><strong>${index+1}. ${esc(categoryName(category))}</strong><span class="muted">${esc(pageName(category.page_id))} · ${resultIds.length} 個項目</span></div><div class="actions">${status}<button class="button" data-category-up="${esc(category.id)}" ${index===0?'disabled':''}>類別 ↑</button><button class="button" data-category-down="${esc(category.id)}" ${index===total-1?'disabled':''}>類別 ↓</button><button class="button" data-edit-category-jump="${esc(category.id)}">編輯類別</button>${reset}</div></div><div class="homepage-order-body">${homepageSectionBodyHtml(data,section)}</div></div>`;
}
function renderHomepageManager(){initHomepageState();removeLegacyHomepagePanel();bindIntegratedHomepageOrderControls()}
function homepageManagerChange(event){
  const mode=event.target.closest('[data-home-mode]'),limit=event.target.closest('[data-home-limit]');
  if(mode){const section=mode.dataset.homeMode,config=homepageDraft[section],current=homepageResolvedIds(homepageBaseEffectiveSite(),section,config),oldMode=config.mode;config.mode=mode.value;if(mode.value==='manual'&&oldMode!=='manual')config.selected_ids=[...current];saveHomepageDraft('已更新首頁選取方式')}
  else if(limit){homepageDraft[limit.dataset.homeLimit].limit=homepageLimit(limit.value,homepageDraft[limit.dataset.homeLimit].limit);saveHomepageDraft('已更新首頁顯示數量')}
}
function splitHomepageAction(value){const index=value.indexOf(':');return[value.slice(0,index),value.slice(index+1)]}
function homepageManagerClick(event){
  const button=event.target.closest('button');if(!button)return false;
  if(button.dataset.resetHomeSection){resetHomepageSection(button.dataset.resetHomeSection);return true}
  for(const action of ['homeAdd','homeRemove','homeUp','homeDown']){
    if(button.dataset[action]===undefined)continue;
    const[section,id]=splitHomepageAction(button.dataset[action]),config=homepageDraft[section],data=homepageBaseEffectiveSite();
    if(action==='homeAdd'){if(!config.selected_ids.includes(id))config.selected_ids.push(id)}
    else if(action==='homeRemove'){const index=config.selected_ids.indexOf(id);if(index>=0)config.selected_ids.splice(index,1)}
    else{
      const resolved=homepageResolvedIds(data,section,config);config.selected_ids=[...resolved];const index=config.selected_ids.indexOf(id),target=action==='homeUp'?index-1:index+1;
      if(index>=0&&target>=0&&target<config.selected_ids.length)[config.selected_ids[index],config.selected_ids[target]]=[config.selected_ids[target],config.selected_ids[index]];
    }
    saveHomepageDraft(action==='homeAdd'||action==='homeRemove'?'已更新首頁手動清單':'已更新首頁顯示順序');return true;
  }
  return false;
}
function previewValue(value){
  if(value===undefined||value===null||value==='')return'—';
  if(typeof value==='boolean')return value?'是':'否';
  if(Array.isArray(value))return value.length?value.join('、'):'—';
  return String(value);
}
function previewFieldRow(label,before,after){
  const same=homepageSignature(before)===homepageSignature(after);
  if(same)return'';
  return`<div class="unified-preview-field"><strong>${esc(label)}</strong><div><span class="preview-before-value">${esc(previewValue(before))}</span><span class="preview-arrow">→</span><span class="preview-after-value">${esc(previewValue(after))}</span></div></div>`;
}
function previewListHtml(data,section,ids){
  if(!ids.length)return'<p class="muted unified-preview-empty">沒有顯示項目。</p>';
  const all=[...(data?.publications||[]),...(data?.activities||[])],map=new Map(all.map(item=>[String(item.id),item]));
  return`<ol class="unified-preview-list">${ids.map((id,index)=>{const item=map.get(String(id));return`<li><span class="preview-index">${index+1}</span><span><strong>${esc(homepageNameById(data,id))}</strong><small>${esc(homepageDate(item,section))}</small></span></li>`}).join('')}</ol>`;
}
function homepagePreviewHtml(op){
  const data=homepageBaseEffectiveSite();
  const changedSections=['publications','activities'].filter(section=>homepageSectionChanged(op.before[section],op.after[section],section,data));
  if(!changedSections.length)return'';
  const rows=changedSections.map(section=>{
    const before=op.before[section],after=op.after[section],beforeIds=homepageResolvedIds(data,section,before),afterIds=homepageResolvedIds(data,section,after),title=section==='publications'?'精選論文':'近期活動';
    return`<section class="unified-preview-card"><div class="unified-preview-card-head"><div><span class="preview-kicker">首頁</span><h4>${title}</h4></div><span class="tag">${afterIds.length} 筆</span></div><div class="unified-preview-fields">${previewFieldRow('選取方式',homepageModeLabel(section,before.mode),homepageModeLabel(section,after.mode))}${previewFieldRow('數量',before.mode==='manual'?beforeIds.length:`N = ${before.limit}`,after.mode==='manual'?afterIds.length:`N = ${after.limit}`)}</div><div class="unified-preview-columns"><div><h5>修改前</h5>${previewListHtml(data,section,beforeIds)}</div><div><h5>修改後</h5>${previewListHtml(data,section,afterIds)}</div></div></section>`;
  }).join('');
  const label=changedSections.length===1?(changedSections[0]==='publications'?'精選論文':'近期活動'):'首頁精選與近期活動';
  return`<details class="diff unified-preview" open><summary><strong>${label}</strong><span class="tag">${changedSections.length} 個區塊</span></summary>${rows}</details>`;
}
function resetHomepageSection(section,shouldRender=true){
  initHomepageState();if(!['publications','activities'].includes(section))return;
  homepageDraft[section]=clone(homepageBase[section]);
  if(homepageDirty())localStorage.setItem(HOMEPAGE_DRAFT_KEY,JSON.stringify({base_signature:homepageSignature(homepageBase),draft:homepageDraft}));else localStorage.removeItem(HOMEPAGE_DRAFT_KEY);
  if(shouldRender){flash('已重設');refreshHomepageSurfaces()}
}
function clearHomepageDraft(shouldRender=true){initHomepageState();homepageDraft=clone(homepageBase);localStorage.removeItem(HOMEPAGE_DRAFT_KEY);if(shouldRender){flash('已重設首頁設定草稿');refreshHomepageSurfaces()}}

const homepageBaseRenderDrafts=renderDrafts;
renderDrafts=function(){
  homepageBaseRenderDrafts();
  const hasLayout=typeof layoutDirty==='function'&&layoutDirty(),hasHomepage=homepageDirty();if(!hasLayout&&!hasHomepage)return;
  const box=$('#drafts');if(!contentOps().length)box.innerHTML='';
  if(hasLayout){const stats=layoutDiffSummary(layoutOrderBaseline(),layoutDraft),summary=[stats.pageChanged?'頁面設定':'',stats.added||stats.removed||stats.changed||stats.moved?'類別設定／順序':'',stats.itemMoved?'項目排序／搬移':'',stats.cvChanged?'PDF 履歷順序':''].filter(Boolean).join('、')||'排序設定';box.insertAdjacentHTML('beforeend',`<div class="row draft-row layout-draft-row"><span class="tag">頁面／類別／排序</span><strong>網站結構與項目排序</strong><span class="muted">${esc(summary)}</span><div class="actions"><button class="button" data-edit-layout-draft>修改草稿</button><button class="button" data-preview-layout-draft>預覽</button><button class="button danger" data-drop-layout-draft>重設</button></div></div>`)}
  if(hasHomepage)box.insertAdjacentHTML('beforeend','<div class="row draft-row homepage-draft-row"><span class="tag">首頁設定</span><strong>首頁精選與近期活動</strong><span class="muted">包含選取模式、數量與顯示順序</span><div class="actions"><button class="button" data-edit-homepage-draft>修改草稿</button><button class="button" data-preview-homepage-draft>預覽</button><button class="button danger" data-drop-homepage-draft>重設</button></div></div>');
};
$('#drafts').addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.hasAttribute('data-edit-layout-draft')){switchTab('order');renderUnifiedOrder();bindIntegratedHomepageOrderControls();return}
  if(button.hasAttribute('data-preview-layout-draft')){$('#editorPreview').innerHTML=`<div class="preview-context"><span class="tag">草稿預覽</span><strong>頁面、類別與排序</strong></div>${layoutPreviewHtml(layoutOperation())}`;return}
  if(button.hasAttribute('data-drop-layout-draft')){resetLayoutDraft();return}
  if(button.hasAttribute('data-edit-homepage-draft')){switchTab('order');const selector=$('#layoutOrderPage');if(selector){selector.value='home';renderUnifiedOrder();bindIntegratedHomepageOrderControls()}document.querySelector('.homepage-order-category')?.scrollIntoView({behavior:'smooth',block:'start'});return}
  if(button.hasAttribute('data-preview-homepage-draft')){$('#editorPreview').innerHTML=`<div class="preview-context"><span class="tag">草稿預覽</span><strong>首頁設定</strong></div>${homepagePreviewHtml(homepageOperation())}`;return}
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
const homepageBaseClearSubmittedDraft=clearSubmittedDraft;
clearSubmittedDraft=function(){localStorage.removeItem(HOMEPAGE_DRAFT_KEY);localStorage.removeItem(GENERAL_LAYOUT_LINK_KEY);homepageBaseClearSubmittedDraft()};

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
   category with the same accepted format exists. Homepage categories instead
   render their selection and ordering controls directly in the category card. */
function layoutOrderBaseline(){return normalizeLayoutBundle(typeof layoutBaselineForCurrent==='function'?layoutBaselineForCurrent():clone(layoutBase))}
function layoutOrderCategoryDirty(categoryId,cvMode=false){
  const baseline=layoutOrderBaseline(),beforeCategory=baseline.categories.find(c=>c.id===categoryId),afterCategory=layoutDraft.categories.find(c=>c.id===categoryId);
  if(!beforeCategory||!afterCategory)return true;
  if(cvMode){if(baseline.cv_category_order.indexOf(categoryId)!==layoutDraft.cv_category_order.indexOf(categoryId))return true}
  else if(beforeCategory.page_id===afterCategory.page_id&&Number(beforeCategory.order)!==Number(afterCategory.order))return true;
  const ids=new Set([...Object.keys(baseline.assignments||{}),...Object.keys(layoutDraft.assignments||{})]);
  for(const id of ids){const before=baseline.assignments[id],after=layoutDraft.assignments[id];if(before?.category_id!==categoryId&&after?.category_id!==categoryId)continue;if(homepageSignature(before)!==homepageSignature(after))return true}
  return false;
}
function resetLayoutOrderCategory(categoryId,cvMode=false){
  const baseline=layoutOrderBaseline(),beforeCategory=baseline.categories.find(c=>c.id===categoryId),afterCategory=layoutDraft.categories.find(c=>c.id===categoryId);if(!beforeCategory||!afterCategory)return;
  if(cvMode){const current=layoutDraft.cv_category_order.filter(id=>id!==categoryId),target=Math.max(0,baseline.cv_category_order.indexOf(categoryId));current.splice(Math.min(target,current.length),0,categoryId);layoutDraft.cv_category_order=current}
  else{
    const rows=layoutDraft.categories.filter(c=>c.page_id===afterCategory.page_id).sort((a,b)=>a.order-b.order),current=rows.filter(c=>c.id!==categoryId),target=beforeCategory.page_id===afterCategory.page_id?Math.max(0,beforeCategory.order):Math.max(0,afterCategory.order);current.splice(Math.min(target,current.length),0,afterCategory);current.forEach((c,index)=>c.order=index);
  }
  const ids=new Set([...Object.keys(baseline.assignments||{}),...Object.keys(layoutDraft.assignments||{})]);
  for(const id of ids){const before=baseline.assignments[id],after=layoutDraft.assignments[id];if(before?.category_id!==categoryId&&after?.category_id!==categoryId)continue;if(before)layoutDraft.assignments[id]=clone(before);else delete layoutDraft.assignments[id]}
  layoutDraft=normalizeLayoutBundle(layoutDraft);saveLayoutDraft('已重設');
}
function resetLayoutDraft(shouldRender=true){
  initLayoutState();layoutDraft=layoutOrderBaseline();localStorage.removeItem(LAYOUT_DRAFT_KEY);if(shouldRender){flash('已重設頁面、類別與排序草稿');renderAll()}
}
function layoutFieldValue(bundle,kind,path,value){
  if(value===undefined||value===null||value==='')return'—';
  if(path==='page_id')return pageNameFromBundle(bundle,value);
  if(path==='kind')return CATEGORY_KIND_LABELS[value]||value;
  if(path==='languages')return(Array.isArray(value)?value:[]).map(lang=>lang==='zh'?'中文':'英文').join('、');
  if(path==='show_on_web'||path==='show_on_cv')return value?'是':'否';
  if(path==='order')return Number(value)+1;
  return previewValue(value);
}
function deepValue(object,path){return path.split('.').reduce((value,key)=>value?.[key],object)}
function layoutEntityChanges(beforeBundle,afterBundle,before,after,specs,kind){
  return specs.map(([path,label])=>{const oldValue=before?deepValue(before,path):undefined,newValue=after?deepValue(after,path):undefined;if(homepageSignature(oldValue)===homepageSignature(newValue))return'';return previewFieldRow(label,layoutFieldValue(beforeBundle,kind,path,oldValue),layoutFieldValue(afterBundle,kind,path,newValue))}).join('');
}
function layoutPreviewEntityCard(kind,title,status,changes){return`<section class="unified-preview-card"><div class="unified-preview-card-head"><div><span class="preview-kicker">${kind==='page'?'頁面':'類別'}</span><h4>${esc(title)}</h4></div><span class="tag preview-status-${esc(status)}">${status==='added'?'新增':status==='removed'?'刪除':'修改'}</span></div><div class="unified-preview-fields">${changes||'<p class="muted">沒有欄位差異。</p>'}</div></section>`}
function layoutPreviewHtml(op){
  const before=normalizeLayoutBundle(op.before),after=normalizeLayoutBundle(op.after),pageBefore=new Map(before.pages.map(x=>[x.id,x])),pageAfter=new Map(after.pages.map(x=>[x.id,x])),categoryBefore=new Map(before.categories.map(x=>[x.id,x])),categoryAfter=new Map(after.categories.map(x=>[x.id,x])),items=new Map(layoutItems(effectiveSite()).map(x=>[String(x.id),x]));
  const pageSpecs=[['name.en','導覽名稱（英文）'],['name.zh','導覽名稱（中文）'],['languages','語言版本'],['path.en','英文網址'],['path.zh','中文網址'],['header.label.en','左上小字（英文）'],['header.label.zh','左上小字（中文）'],['header.title.en','頁面標題（英文）'],['header.title.zh','頁面標題（中文）'],['header.intro.en','簡介（英文）'],['header.intro.zh','簡介（中文）'],['color','頁面主色'],['order','頁面順序']];
  const categorySpecs=[['label.en','左上小字（英文）'],['label.zh','左上小字（中文）'],['title.en','大標題（英文）'],['title.zh','大標題（中文）'],['intro.en','簡介（英文）'],['intro.zh','簡介（中文）'],['page_id','所在頁面'],['kind','顯示風格'],['show_on_web','顯示於網站'],['show_on_cv','顯示於 PDF 履歷'],['order','類別順序']];
  const pageCards=[];for(const id of new Set([...pageBefore.keys(),...pageAfter.keys()])){const b=pageBefore.get(id),a=pageAfter.get(id);if(homepageSignature(b)===homepageSignature(a))continue;pageCards.push(layoutPreviewEntityCard('page',a?.name?.zh||a?.name?.en||b?.name?.zh||b?.name?.en||id,!b?'added':!a?'removed':'changed',layoutEntityChanges(before,after,b,a,pageSpecs,'page')))}
  const categoryCards=[];for(const id of new Set([...categoryBefore.keys(),...categoryAfter.keys()])){const b=categoryBefore.get(id),a=categoryAfter.get(id);if(homepageSignature(b)===homepageSignature(a))continue;categoryCards.push(layoutPreviewEntityCard('category',categoryName(a||b),!b?'added':!a?'removed':'changed',layoutEntityChanges(before,after,b,a,categorySpecs,'category')))}
  const assignmentRows=[];for(const id of new Set([...Object.keys(before.assignments),...Object.keys(after.assignments)])){const b=before.assignments[id],a=after.assignments[id];if(homepageSignature(b)===homepageSignature(a))continue;assignmentRows.push(`<div class="unified-preview-move"><strong>${esc(itemName(items.get(id))||id)}</strong><div><span>${esc(layoutPosition(before,b))}</span><span class="preview-arrow">→</span><span>${esc(layoutPosition(after,a))}</span></div></div>`)}
  const cvChanged=homepageSignature(before.cv_category_order)!==homepageSignature(after.cv_category_order),cvSection=cvChanged?`<section class="unified-preview-card"><div class="unified-preview-card-head"><div><span class="preview-kicker">PDF 履歷</span><h4>類別順序</h4></div><span class="tag">修改</span></div><div class="unified-preview-columns"><div><h5>修改前</h5>${previewCategoryOrderList(before,before.cv_category_order)}</div><div><h5>修改後</h5>${previewCategoryOrderList(after,after.cv_category_order)}</div></div></section>`:'';
  const cards=[...pageCards,...categoryCards].join(''),moves=assignmentRows.length?`<section class="unified-preview-card"><div class="unified-preview-card-head"><div><span class="preview-kicker">排序與搬移</span><h4>項目位置</h4></div><span class="tag">${assignmentRows.length} 筆</span></div><div class="unified-preview-moves">${assignmentRows.slice(0,100).join('')}${assignmentRows.length>100?`<p class="muted">另有 ${assignmentRows.length-100} 筆未展開。</p>`:''}</div></section>`:'';
  const count=pageCards.length+categoryCards.length+assignmentRows.length+(cvChanged?1:0),body=cards+moves+cvSection;
  return`<details class="diff unified-preview" open><summary><strong>頁面、類別與排序</strong><span class="tag">${count} 項差異</span></summary>${body||'<p class="muted unified-preview-empty">沒有差異。</p>'}</details>`;
}
function previewCategoryOrderList(bundle,ids){return`<ol class="unified-preview-list">${ids.map((id,index)=>{const c=bundle.categories.find(item=>item.id===id);return`<li><span class="preview-index">${index+1}</span><span><strong>${esc(categoryName(c)||id)}</strong><small>${esc(c?pageNameFromBundle(bundle,c.page_id):'')}</small></span></li>`}).join('')}</ol>`}

const homepageBaseOrderCategoryCard=orderCategoryCard;
orderCategoryCard=function(category,index,total,map,cvMode=false){
  if(!cvMode&&category.kind==='featured_publications')return homepageOrderCategoryCard(category,index,total,'publications');
  if(!cvMode&&category.kind==='upcoming')return homepageOrderCategoryCard(category,index,total,'activities');
  const ids=categoryItemIds(category.id),compatible=layoutDraft.categories.filter(c=>c.kind===category.kind&&c.id!==category.id).sort(categorySort),orderDirty=layoutOrderCategoryDirty(category.id,cvMode),reset=`<button class="button" data-reset-order-category="${esc(category.id)}" data-reset-order-cv="${cvMode?'1':'0'}" ${orderDirty?'':'disabled'}>重設</button>`;
  return `<div class="layout-order-category" data-order-category="${esc(category.id)}"><div class="layout-order-category-head"><div><span class="tag">${esc(CATEGORY_KIND_LABELS[category.kind]||category.kind)}</span><strong>${index+1}. ${esc(categoryName(category))}</strong><span class="muted">${esc(pageName(category.page_id))} · ${ids.length} 個項目</span></div><div class="actions"><button class="button" data-category-up="${esc(category.id)}" ${index===0?'disabled':''}>類別 ↑</button><button class="button" data-category-down="${esc(category.id)}" ${index===total-1?'disabled':''}>類別 ↓</button><button class="button" data-edit-category-jump="${esc(category.id)}">編輯類別</button>${reset}</div></div>${!cvMode?`<div class="order-sort-tools"><span class="muted">此類別快速排序：</span><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="newest">日期新到舊</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="oldest">日期舊到新</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="title">名稱</button></div>`:''}<div>${ids.map((id,i)=>{const item=map.get(id);if(!item)return'';let moveControl;if(cvMode)moveControl='<select class="move-category-select" disabled><option>搬移（PDF 檢視不可用）</option></select>';else if(compatible.length)moveControl=`<select class="move-category-select" data-move-item="${esc(id)}"><option value="">搬移…</option>${compatible.map(c=>`<option value="${esc(c.id)}">${esc(pageName(c.page_id))} → ${esc(categoryName(c))}</option>`).join('')}</select>`;else moveControl='<select class="move-category-select" disabled><option>搬移（無相容類別）</option></select>';return `<div class="layout-order-item"><div><strong>${i+1}. ${esc(itemName(item))}</strong><span class="muted">${esc(itemMetaChinese(item))}</span></div><div class="layout-order-item-actions"><button class="button" data-item-up="${esc(id)}" ${i===0?'disabled':''}>↑</button><button class="button" data-item-down="${esc(id)}" ${i===ids.length-1?'disabled':''}>↓</button>${moveControl}</div></div>`}).join('')||'<p class="muted">此類別目前沒有項目。</p>'}</div></div>`;
};
const homepageBaseUnifiedOrderClick=unifiedOrderClick;
const homepageBaseUnifiedOrderChange=unifiedOrderChange;
function integratedHomepageOrderClick(event){if(homepageManagerClick(event))return;const reset=event.target.closest('[data-reset-order-category]');if(reset){resetLayoutOrderCategory(reset.dataset.resetOrderCategory,reset.dataset.resetOrderCv==='1');return}homepageBaseUnifiedOrderClick(event)}
function integratedHomepageOrderChange(event){if(event.target.closest('[data-home-mode],[data-home-limit]')){homepageManagerChange(event);return}homepageBaseUnifiedOrderChange(event)}
unifiedOrderClick=integratedHomepageOrderClick;
unifiedOrderChange=integratedHomepageOrderChange;

const homepageBaseRenderAll=renderAll;
renderAll=function(){homepageBaseRenderAll();configureAddTypeMenu();renderHomepageManager();bindIntegratedHomepageOrderControls()};

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
function categoryDisplayNameFromId(id,bundle=layoutDraft){const category=bundle?.categories?.find(c=>c.id===id);return category?`${pageNameFromBundle(bundle,category.page_id)} → ${categoryName(category)}`:(id||'—')}
function generalStyleName(type){return GENERAL_STYLE_INFO[type]?.name||GENERAL_FORMAT_LABELS[type]||type||'—'}
function generalStyleChangePreview(beforeType,afterType,beforeCategoryId,afterCategoryId){
  const rows=[previewFieldRow('顯示風格',generalStyleName(beforeType),generalStyleName(afterType)),previewFieldRow('所屬類別',categoryDisplayNameFromId(beforeCategoryId,layoutOrderBaseline()),categoryDisplayNameFromId(afterCategoryId,layoutDraft))].filter(Boolean).join('');
  return rows?`<section class="unified-preview-card general-style-change-preview"><div class="unified-preview-card-head"><div><span class="preview-kicker">一般內容</span><h4>版面與類別</h4></div><span class="tag preview-status-changed">修改</span></div><div class="unified-preview-fields">${rows}</div></section>`:'';
}
function previewGeneralCurrent(){
  const value=generalEditorValue(),errors=generalValidation(value);if(errors.length){$('#editorPreview').innerHTML=`<div class="notice error"><strong>請先修正</strong><ul>${errors.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;return}
  const before=currentEditor.originalBefore||currentEditor.record||null,beforeType=before?.type||'',beforeCategory=layoutOrderBaseline().assignments?.[value.o.id]?.category_id||before?.category_id||'';
  $('#editorPreview').innerHTML=`<div class="preview-context"><span class="tag">項目預覽</span><strong>${esc(homepageItemTitle(value.o))}</strong></div>${generalStyleChangePreview(beforeType,value.targetType,beforeCategory,value.targetCategory)}${objectPreviewHtml(value.targetType,value.o)}`;
}
const homepageBaseChangePreviewHtml=changePreviewHtml;
changePreviewHtml=function(type,before,after){
  const body=homepageBaseChangePreviewHtml(type,before,after),beforeType=before?.type||'',afterType=after?.type||type||'',relevant=GENERAL_STYLE_KINDS.has(beforeType)||GENERAL_STYLE_KINDS.has(afterType);
  if(!relevant)return body;
  const id=after?.id||before?.id||'',baseline=layoutOrderBaseline().assignments?.[id],current=layoutDraft.assignments?.[id],beforeCategory=baseline?.category_id||before?.category_id||'',afterCategory=current?.category_id||after?.category_id||'';
  const meta=generalStyleChangePreview(beforeType,afterType,beforeCategory,afterCategory);
  return meta+body;
};
function replaceDraftsForId(id,operations){for(let i=draft.length-1;i>=0;i--){const op=draft[i];if(['add','update','delete'].includes(op.op)&&(op.id||op.after?.id)===id)draft.splice(i,1)}draft.push(...operations)}
function loadGeneralLayoutLinks(){try{const raw=JSON.parse(localStorage.getItem(GENERAL_LAYOUT_LINK_KEY)||'{}');return raw&&typeof raw==='object'?raw:{}}catch{return{}}}
function saveGeneralLayoutLinks(links){if(Object.keys(links).length)localStorage.setItem(GENERAL_LAYOUT_LINK_KEY,JSON.stringify(links));else localStorage.removeItem(GENERAL_LAYOUT_LINK_KEY)}
function rememberGeneralLayoutLink(id,before,after){if(!id||!before)return;const links=loadGeneralLayoutLinks();links[id]={before:clone(before),after:clone(after)};saveGeneralLayoutLinks(links)}
function forgetGeneralLayoutLink(id){const links=loadGeneralLayoutLinks();if(!links[id])return;delete links[id];saveGeneralLayoutLinks(links)}
function persistLayoutDraftWithoutMessage(){layoutDraft=normalizeLayoutBundle(layoutDraft);if(layoutDirty())localStorage.setItem(LAYOUT_DRAFT_KEY,JSON.stringify({base_signature:layoutSignature(layoutBase),draft:layoutDraft}));else localStorage.removeItem(LAYOUT_DRAFT_KEY)}
function reconcileGeneralLayoutLinks(){
  if(!site||typeof contentOps!=='function')return false;initLayoutState();const links=loadGeneralLayoutLinks();let changed=false;
  for(const[id,link]of Object.entries(links)){
    const related=contentOps().filter(op=>(op.id||op.after?.id)===id),hasAfter=related.some(op=>['add','update'].includes(op.op)&&op.after);
    if(hasAfter)continue;
    if(link.before)layoutDraft.assignments[id]=clone(link.before);else delete layoutDraft.assignments[id];delete links[id];changed=true;
  }
  if(changed){saveGeneralLayoutLinks(links);persistLayoutDraftWithoutMessage()}
  return changed;
}
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
    const baseline=layoutOrderBaseline().assignments?.[id],oldState=layoutDraft.assignments[id]||baseline||{},originalType=String(originalBefore?.type||record?.type||value.originalType),returningToOriginal=!!baseline&&value.targetType===originalType&&value.targetCategory===baseline.category_id;
    if(returningToOriginal){layoutDraft.assignments[id]=clone(baseline);forgetGeneralLayoutLink(id)}
    else{
      const sameCategory=oldState.category_id===value.targetCategory,order=sameCategory?Number(oldState.order??0):categoryItemIds(value.targetCategory).filter(itemId=>itemId!==id).length,target={category_id:value.targetCategory,order};
      layoutDraft.assignments[id]=target;if(baseline)rememberGeneralLayoutLink(id,baseline,target);
    }
    saveLayoutDraft('');
  }
  switchTab('draft');flash(isDraft?'草稿變更已儲存':'已加入批次草稿');
}
const homepageGeneralBaseSaveLocal=saveLocal;
saveLocal=function(){homepageGeneralBaseSaveLocal();if(reconcileGeneralLayoutLinks())renderAll()};

const GENERAL_CONTENT_FILTER_TYPES=new Set(['interest','education','generic','contact','personal']);
function configureActivityLabels(){
  LABEL.academic_event='活動';LABEL.organization='學術籌辦';LABEL.general_content='一般內容';
  if(typeof CATEGORY_KIND_LABELS==='object')CATEGORY_KIND_LABELS.organization='學術籌辦';
}
const homepageBaseAdminFilterMatches=adminFilterMatches;
adminFilterMatches=function(item,filter){
  if(filter==='general_content')return GENERAL_CONTENT_FILTER_TYPES.has(item?.type);
  return homepageBaseAdminFilterMatches(item,filter);
};
function configureAddTypeMenu(){
  configureActivityLabels();
  const add=$('#addType');if(add){
    const selected=add.value;
    const types=['page','category','publication','academic_event','teaching','generic'];
    add.innerHTML=types.map(type=>`<option value="${type}" ${type===selected?'selected':''}>${esc(LABEL[type]||type)}</option>`).join('');
    if(!types.includes(add.value))add.value='academic_event';
  }
  const filter=$('#filter');if(filter){
    const previous=GENERAL_CONTENT_FILTER_TYPES.has(filter.value)?'general_content':filter.value;
    const types=['page','category','publication','conference','talk','visit','organization','honor','teaching','general_content'];
    filter.innerHTML='<option value="">全部</option>'+types.map(type=>`<option value="${type}" ${type===previous?'selected':''}>${esc(LABEL[type]||type)}</option>`).join('');
    filter.value=types.includes(previous)?previous:'';
  }
  const order=$('#orderType');if(order)for(const option of order.options)option.textContent=LABEL[option.value]||option.textContent;
}
function openAcademicEventChooser(){
  initLayoutState();configureActivityLabels();
  const box=document.createElement('div');
  const choices=[
    ['conference','學術會議','會議、工作坊與參與身分'],
    ['talk','學術報告','報告題目、場合與投影片連結'],
    ['visit','學術訪問','訪問機構、地點與資助資訊'],
    ['organization','學術籌辦','主辦、協辦、召集或籌辦的活動']
  ];
  box.innerHTML=`<div class="activity-chooser-head"><div><span class="eyebrow">新增項目</span><h3>新增活動</h3></div></div><p class="field-hint">請選擇活動種類，接著會開啟對應表單。選錯時可從表單上方返回這一頁。</p><div class="academic-event-choices activity-four-choices">${choices.map(([type,label,description])=>`<button class="button academic-event-choice" data-academic-event-type="${type}"><strong>${label}</strong><span>${description}</span></button>`).join('')}</div>`;
  $('#addEditor').replaceChildren(box);currentEditor={type:'academic_event',record:null,root:box};
  box.onclick=event=>{const button=event.target.closest('[data-academic-event-type]');if(button)openEditor(button.dataset.academicEventType,null,{fromActivityChooser:true})};
}
function installActivityBackButton(root){
  if(!root||root.querySelector('[data-back-to-activity-chooser]'))return;
  const bar=document.createElement('div');bar.className='activity-form-nav';
  bar.innerHTML='<button type="button" class="button" data-back-to-activity-chooser>← 返回活動類型</button>';
  bar.onclick=event=>{if(event.target.closest('[data-back-to-activity-chooser]'))openAcademicEventChooser()};
  root.prepend(bar);
}
const homepageBaseOpenEditor=openEditor;
openEditor=function(type,record,options={}){
  homepageBaseOpenEditor(type,record,options);
  decorateGeneralEditor(type,record);
  if(options.fromActivityChooser&&!record)installActivityBackButton(currentEditor?.root);
};

const homepageBaseCategoryFormHtml=categoryFormHtml;
categoryFormHtml=function(category){
  return homepageBaseCategoryFormHtml(category).replace('<div class="notice">類別是頁面中的一個大區塊。左上小字、大標題與簡介都可分別填寫中英文。</div>','<p class="field-hint compact-layout-hint">類別是頁面中的一個大區塊；左上小字、大標題與簡介可分別填寫中英文。</p>');
};

function installClearAllDraftHandler(){
  const button=$('#clearDraft');if(!button)return;
  button.onclick=()=>{if(!confirm('清空所有內容、排序、首頁精選與還原草稿？'))return;draft=[];clearHomepageDraft(false);initLayoutState();layoutDraft=clone(layoutBase);localStorage.removeItem(LAYOUT_DRAFT_KEY);localStorage.removeItem(GENERAL_LAYOUT_LINK_KEY);saveLocal()};
}

function previewPlaceholderHtml(){return'<p class="muted preview-placeholder">在左側填寫後，按「在右側預覽」查看修改內容。</p>'}
function closeEditorPreview(){const box=$('#editorPreview');if(box)box.innerHTML=previewPlaceholderHtml()}
function ensurePreviewCloseButton(){
  const box=$('#editorPreview');if(!box||box.querySelector('.preview-close-button')||box.querySelector('.preview-placeholder'))return;
  const text=box.textContent.trim();if(!text||text.startsWith('在左側填寫後'))return;
  const button=document.createElement('button');button.type='button';button.className='button preview-close-button';button.setAttribute('aria-label','關閉預覽');button.textContent='關閉';button.onclick=closeEditorPreview;box.prepend(button);
}
function installPreviewCloseButton(){const box=$('#editorPreview');if(!box)return;new MutationObserver(()=>ensurePreviewCloseButton()).observe(box,{childList:true,subtree:false});ensurePreviewCloseButton()}

function installHomepageAndStyleCss(){const style=document.createElement('style');style.textContent=`
.homepage-order-category{background:#fff}.homepage-order-body{margin-top:10px}.homepage-order-settings{padding:10px 11px;border:1px solid #e3d8cf;border-radius:10px;background:#fcfaf8}.homepage-order-settings .field{margin:0}.homepage-order-help{margin:6px 0 0;font-size:.74rem;line-height:1.45}.homepage-order-list h4,.homepage-manual h4{margin:12px 0 6px;font-size:.88rem}.homepage-selected-row{padding:9px 7px;border-top:1px solid #e7ddd5;background:#fff}.homepage-selected-row>div:first-child{display:grid;gap:2px;min-width:0}.homepage-choice-list{display:grid;gap:7px}.homepage-choice{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;text-align:left;padding:9px 11px;border:1px solid #d9cec5;border-radius:9px;background:#fff;color:inherit;cursor:pointer}.homepage-choice:hover{border-color:#8f6f59}.homepage-choice span{font-weight:700;color:#79543d}.homepage-choice small{color:#70665e}.homepage-status-tag{font-size:.7rem;line-height:1.35}.homepage-dirty-tag{background:#f2dfb8;color:#68420b}.layout-order-item{display:grid;grid-template-columns:minmax(0,1fr) max-content;gap:10px;align-items:center}.layout-order-item>div:first-child{min-width:0}.layout-order-item>div:first-child strong{display:block;overflow-wrap:anywhere}.layout-order-item-actions{display:flex;flex-wrap:nowrap;gap:6px;align-items:center;white-space:nowrap}.move-category-select{min-width:180px;max-width:260px}.move-category-select:disabled{opacity:.5;cursor:not-allowed;background:#eee9e5}.activity-form-nav{display:flex;margin:0 0 12px}.activity-four-choices{grid-template-columns:repeat(2,minmax(0,1fr))!important}.activity-chooser-head h3{margin:.2rem 0 0}.general-style-guide{margin:12px 0;border:1px solid #ded3ca;border-radius:12px;background:#fcfaf8}.general-style-guide>summary{cursor:pointer;padding:12px}.general-style-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:0 12px 12px}.general-style-card{border:1px solid #ddd2c9;border-radius:11px;padding:10px;background:#fff;transition:.15s}.general-style-card.selected{border-color:#8d493d;box-shadow:inset 4px 0 #8d493d;background:#fff8f4}.general-style-card-head{display:flex;justify-content:space-between;gap:8px}.general-style-card-head span{font:11px ui-monospace,monospace;color:#81766e}.general-style-card p{font-size:.78rem;color:#6f655e;margin:.55rem 0 0}.general-style-sample{min-height:58px;margin-top:9px;padding:9px;border-radius:8px;background:#f5f0ec;display:flex;gap:9px;align-items:flex-start}.general-style-sample>span{display:grid;gap:3px}.general-style-sample small{display:block;color:#776c64}.general-style-sample.interest{display:block}.general-style-sample.contact{display:block}.general-style-sample.personal{align-items:center}.style-date{min-width:58px;font-weight:800;color:#8d493d}.style-card{padding:7px 9px;border:1px solid #d8cdc5;border-radius:8px;background:#fff}.style-pill{display:inline-flex!important;padding:3px 8px;border-radius:999px;background:#e8dfd8;font-weight:800}
.compact-layout-hint{margin:0 0 10px;font-size:.76rem;line-height:1.5;color:#756a63}#editorPreview{position:relative}.preview-close-button{float:right;margin:0 0 8px 8px;padding:4px 8px;font-size:.72rem;border-radius:999px}.preview-close-button+*{clear:both}.general-style-change-preview{border-color:#d8c7bb}.preview-context{display:flex;gap:8px;align-items:center;margin:0 0 10px;padding:8px 10px;border:1px solid #ded3ca;border-radius:10px;background:#faf7f4}.unified-preview{border:1px solid #d8cdc5;border-radius:13px;background:#fff;overflow:hidden;margin:10px 0}.unified-preview>summary{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 13px;cursor:pointer;background:#f7f2ee;border-bottom:1px solid #e6ddd6}.unified-preview-card{margin:11px;border:1px solid #ded4cc;border-radius:12px;background:#fff;overflow:hidden}.unified-preview-card-head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:11px 12px;background:#fcfaf8;border-bottom:1px solid #ece4de}.unified-preview-card-head h4{margin:1px 0 0;font-size:.98rem}.preview-kicker{display:block;font-size:.67rem;font-weight:850;letter-spacing:.08em;color:#8a6853;text-transform:uppercase}.unified-preview-fields{display:grid;gap:0;padding:0 12px}.unified-preview-field{display:grid;grid-template-columns:minmax(120px,.45fr) minmax(0,1fr);gap:12px;padding:9px 0;border-bottom:1px solid #eee7e1}.unified-preview-field:last-child{border-bottom:0}.unified-preview-field>div{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:start}.preview-before-value{color:#766b63;text-decoration:line-through;text-decoration-color:#c9b7aa}.preview-after-value{font-weight:750;color:#342d29}.preview-arrow{color:#aa8b77;font-weight:850}.unified-preview-columns{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px}.unified-preview-columns>div{min-width:0;border:1px solid #e6ddd6;border-radius:10px;background:#fcfaf8;padding:10px}.unified-preview-columns h5{margin:0 0 7px;font-size:.76rem;color:#6f625a;text-transform:uppercase;letter-spacing:.05em}.unified-preview-list{display:grid;gap:6px;list-style:none;padding:0;margin:0}.unified-preview-list li{display:grid;grid-template-columns:24px minmax(0,1fr);gap:8px;align-items:start;padding:7px 8px;border-radius:8px;background:#fff;border:1px solid #ece4de}.unified-preview-list li>span:last-child{display:grid;gap:2px}.unified-preview-list small{color:#756a63}.preview-index{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:999px;background:#eee5de;color:#70523f;font-size:.7rem;font-weight:850}.unified-preview-moves{display:grid}.unified-preview-move{display:grid;grid-template-columns:minmax(160px,.55fr) minmax(0,1fr);gap:12px;padding:10px 12px;border-bottom:1px solid #eee7e1}.unified-preview-move:last-child{border-bottom:0}.unified-preview-move>div{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px}.unified-preview-empty{padding:12px}.preview-status-added{background:#e6f2e9;color:#315c3d}.preview-status-removed{background:#f6e5e2;color:#7a3d34}.preview-status-changed{background:#efe6d7;color:#674d28}.preview-columns>div{border:1px solid #e2d8d0;border-radius:12px;padding:10px;background:#fcfaf8}.preview-card{border:1px solid #e2d8d0;border-radius:11px;background:#fff;box-shadow:none}.order-diff-row{border-bottom:1px solid #eee7e1;padding:8px 0}
@media(max-width:700px){.layout-order-item{grid-template-columns:1fr}.layout-order-item-actions{justify-content:flex-end;overflow-x:auto;padding-bottom:2px}.move-category-select{min-width:170px}.activity-four-choices{grid-template-columns:1fr!important}.homepage-selected-row{align-items:flex-start;flex-direction:column}.homepage-selected-row .actions{width:100%}.homepage-choice{grid-template-columns:auto 1fr}.homepage-choice small{grid-column:2}.general-style-grid{grid-template-columns:1fr}.unified-preview-columns{grid-template-columns:1fr}.unified-preview-field,.unified-preview-move{grid-template-columns:1fr}.unified-preview-field>div,.unified-preview-move>div{grid-template-columns:1fr}.preview-arrow{transform:rotate(90deg);justify-self:start}}
`;document.head.append(style)}
installHomepageAndStyleCss();
configureAddTypeMenu();
bindModernRecordControls();
installClearAllDraftHandler();
installPreviewCloseButton();
if(site)renderAll();
