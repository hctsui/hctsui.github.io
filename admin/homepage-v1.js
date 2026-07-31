'use strict';

/* Homepage Selected Publications / Upcoming manager. It extends the legacy
   editor without changing the content-form workflow. */
const HOMEPAGE_DRAFT_KEY='hctsui-homepage-draft-v1';
let homepageBase=null,homepageDraft=null,homepageReady=false,homepageNotice='',homepagePreviewSuppressed=false;

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
function initHomepageState(){
  if(homepageReady||!site)return;
  homepageBase=homepageBundle(site);homepageDraft=clone(homepageBase);
  try{
    const saved=JSON.parse(localStorage.getItem(HOMEPAGE_DRAFT_KEY)||'null');
    if(saved?.base_signature===homepageSignature(homepageBase)&&saved?.draft){homepageDraft=homepageBundle(site,saved.draft);homepageNotice='已恢復尚未送出的首頁精選草稿。'}
    else if(saved){localStorage.removeItem(HOMEPAGE_DRAFT_KEY);homepageNotice='首頁資料已更新，舊的首頁精選草稿已安全丟棄。'}
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
function homepageDirty(){return homepageReady&&homepageSignature(homepageSubmissionBundle())!==homepageSignature(homepageBase)}
function homepageOperation(){return{op:'homepage',before:clone(homepageBase),after:homepageSubmissionBundle()}}
function applyHomepageToData(data,value){data.settings=data.settings||{};data.settings.homepage=clone(value);data.settings.homepage_publication_limit=value.publications.limit;return data}
function saveHomepageDraft(message=''){
  initHomepageState();
  if(homepageDirty())localStorage.setItem(HOMEPAGE_DRAFT_KEY,JSON.stringify({base_signature:homepageSignature(homepageBase),draft:homepageDraft}));
  else localStorage.removeItem(HOMEPAGE_DRAFT_KEY);
  if(message)flash(message);
  renderAll();
}
function homepageToday(){
  try{return new Date().toLocaleDateString('sv-SE',{timeZone:site?.settings?.timezone||'Asia/Tokyo'})}
  catch{return new Date().toISOString().slice(0,10)}
}
function homepageItemTitle(item){return title(item)||item?.id||'未命名項目'}
function homepageDate(item,section){return section==='activities'?String(item?.start_date||''):String(item?.date||item?.year||'')}
function homepageCandidates(data,section){
  const items=section==='publications'?[...(data?.publications||[])]:[...(data?.activities||[])].filter(item=>String(item.end_date||item.start_date||'')>=homepageToday());
  return items.sort((a,b)=>homepageDate(b,section).localeCompare(homepageDate(a,section))||String(a.id).localeCompare(String(b.id)));
}
function homepageResolvedIds(data,section,config){
  const items=homepageCandidates(data,section),byId=new Map(items.map(item=>[String(item.id),item]));
  if(config.mode==='manual')return config.selected_ids.filter(id=>byId.has(id));
  const sorted=[...items].sort((a,b)=>{
    const comparison=homepageDate(a,section).localeCompare(homepageDate(b,section))||String(a.id).localeCompare(String(b.id));
    return config.mode==='latest'||config.mode==='farthest'?-comparison:comparison;
  });
  return sorted.slice(0,config.limit).map(item=>String(item.id));
}
function homepageNameById(data,id){const item=[...(data?.publications||[]),...(data?.activities||[])].find(entry=>String(entry.id)===String(id));return item?homepageItemTitle(item):id}
function homepageModeLabel(section,mode){
  return({publications:{latest:'固定最新 N 篇',oldest:'固定最舊 N 篇',manual:'手動選擇與排序'},activities:{soonest:'最近即將開始的 N 筆',farthest:'日期最遠的 N 筆',manual:'手動選擇與排序'}})[section][mode]||mode;
}
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
function renderHomepageManager(){
  initHomepageState();const box=$('#homepageManager');if(!box)return;
  const data=homepageBaseEffectiveSite();
  box.innerHTML=`<div class="notice"><strong>只控制首頁雙欄，不會刪除原始資料。</strong><p>自動模式會隨內容更新；手動模式可指定項目與順序。右側預覽確認後，再按「前往 GitHub 送出批次」。</p>${homepageNotice?`<p>${esc(homepageNotice)}</p>`:''}</div>${homepageSectionHtml(data,'publications')}${homepageSectionHtml(data,'activities')}<div class="actions"><button class="button" id="resetHomepageDraft" ${homepageDirty()?'':'disabled'}>放棄首頁精選草稿</button></div>`;
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
  if(button.id==='resetHomepageDraft'){homepageDraft=clone(homepageBase);saveHomepageDraft('已放棄首頁精選草稿');return}
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
  const changedSections=['publications','activities'].filter(section=>homepageSignature(op.before[section])!==homepageSignature(op.after[section]));
  const rows=changedSections.map(section=>{
    const before=op.before[section],after=op.after[section],beforeIds=homepageResolvedIds(data,section,before),afterIds=homepageResolvedIds(data,section,after);
    return`<div class="preview-card"><h4>${section==='publications'?'精選論文':'近期活動'}</h4><div class="preview-columns"><div><strong>修改前</strong><p>${esc(homepageModeLabel(section,before.mode))}${before.mode==='manual'?'':` · N=${before.limit}`}</p><ol>${beforeIds.map(id=>`<li>${esc(homepageNameById(data,id))}</li>`).join('')}</ol></div><div><strong>修改後</strong><p>${esc(homepageModeLabel(section,after.mode))}${after.mode==='manual'?'':` · N=${after.limit}`}</p><ol>${afterIds.map(id=>`<li>${esc(homepageNameById(data,id))}</li>`).join('')}</ol></div></div></div>`;
  }).join('');
  const label=changedSections.length===1?(changedSections[0]==='publications'?'精選論文':'近期活動'):'首頁精選與近期活動';
  return`<details class="diff"><summary><strong>${label}</strong></summary>${rows}</details>`;
}

const homepageBaseEffectiveSite=effectiveSite;
effectiveSite=function(){const data=homepageBaseEffectiveSite();initHomepageState();return applyHomepageToData(data,homepageSubmissionBundle())};
const homepageBasePayload=payload;
payload=function(){const result=homepageBasePayload();if(!homepagePreviewSuppressed&&homepageDirty())result.operations.push(homepageOperation());return result};
const homepageBaseRenderPreview=renderPreview;
renderPreview=function(refreshDictionary=true){homepagePreviewSuppressed=true;homepageBaseRenderPreview(refreshDictionary);homepagePreviewSuppressed=false;if(homepageDirty()){const op=homepageOperation();$('#preview').insertAdjacentHTML('beforeend',homepagePreviewHtml(op));const text=$('#summary').textContent;$('#summary').textContent=text==='尚無變更。'?'首頁精選有變更。':text.replace(/。$/,'')+'、首頁精選 1。'}$('#payload').textContent=JSON.stringify(payload(),null,2)};
const homepageBaseHistoryPreview=historyOperationPreviewHtml;
historyOperationPreviewHtml=function(h){if(h?.action==='homepage')return`<div class="notice"><strong>還原預覽 · 首頁精選</strong><div>${esc(historyTitle(h))}</div></div>${homepagePreviewHtml({before:h.before,after:h.after})}`;return homepageBaseHistoryPreview(h)};
const homepageBaseUndoPreview=undoPreviewHtml;
undoPreviewHtml=function(h){if(h?.action==='homepage')return homepagePreviewHtml({before:h.after,after:h.before});return homepageBaseUndoPreview(h)};
const homepageBaseRenderAll=renderAll;
renderAll=function(){homepageBaseRenderAll();if(site)renderHomepageManager()};
const homepageBaseClearSubmittedDraft=clearSubmittedDraft;
clearSubmittedDraft=function(){localStorage.removeItem(HOMEPAGE_DRAFT_KEY);homepageBaseClearSubmittedDraft()};

function installHomepageCss(){const style=document.createElement('style');style.textContent=`
.homepage-card{border:1px solid #ded3ca;border-radius:12px;padding:14px;margin:12px 0;background:#fcfaf8}.homepage-card h3{margin-top:0}.homepage-card h4{margin:14px 0 8px}.homepage-selected-row{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px;border-top:1px solid #e7ddd5;background:#fff}.homepage-selected-row>div:first-child{display:grid;gap:3px;min-width:0}.homepage-choice-list{display:grid;gap:7px}.homepage-choice{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;text-align:left;padding:9px 11px;border:1px solid #d9cec5;border-radius:9px;background:#fff;color:inherit;cursor:pointer}.homepage-choice:hover{border-color:#8f6f59}.homepage-choice span{font-weight:700;color:#79543d}.homepage-choice small{color:#70665e}.homepage-card ol{margin-bottom:0}@media(max-width:700px){.homepage-selected-row{align-items:flex-start;flex-direction:column}.homepage-selected-row .actions{width:100%}.homepage-choice{grid-template-columns:auto 1fr}.homepage-choice small{grid-column:2}}
`;document.head.append(style)}
installHomepageCss();
if(site)renderAll();
