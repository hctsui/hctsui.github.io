'use strict';

/* Dossier, mixed-category and additional-placement controls layered on top of
   the current schema-3 layout manager. No core Admin file is replaced. */
(function installDossierCategoryManager(){
  if(typeof normalizeLayoutBundle!=='function')return;

  CATEGORY_KIND_LABELS.mixed='一般內容';
  const PROFILE_CATEGORY_ID='personal-profile';
  const PERSONAL_PAGE_ID='personal-profile';
  const PDF_CV_PAGE_ID='pdf-cv';
  const CV_PERSONAL_CATEGORY_ID='cv-personal';
  const VIRTUAL_PAGE_IDS=new Set([PDF_CV_PAGE_ID,PERSONAL_PAGE_ID]);
  const VIRTUAL_PAGES=[
    {id:PDF_CV_PAGE_ID,name:{en:'PDF CV',zh:'PDF 履歷'},path:{en:'',zh:''},languages:['en','zh'],header:null,color:'#735748',show_in_navigation:false,order:9000,virtual:true,virtual_kind:'pdf_cv'},
    {id:PERSONAL_PAGE_ID,name:{en:'Personal Information',zh:'個人資料'},path:{en:'',zh:''},languages:['en','zh'],header:null,color:'#675c83',show_in_navigation:false,order:9001,virtual:true,virtual_kind:'personal_profile'},
  ];
  const EXCLUDED_KINDS=new Set(['featured_publications','upcoming','contact']);
  const DEFAULT_DOSSIER_KINDS=new Set(['interest','education','honor','publication','talk','teaching']);
  const STYLE_ORDER=['publication','conference','talk','visit','organization','teaching','honor','generic','education','interest','contact','personal','mixed'];

  const virtualPage=id=>VIRTUAL_PAGES.find(page=>page.id===id)||null;
  const isVirtualPage=id=>VIRTUAL_PAGE_IDS.has(String(id||''));
  const ensureVirtualPages=pages=>{
    const result=(Array.isArray(pages)?pages:[]).filter(page=>page&&!isVirtualPage(page.id)).map(page=>clone(page));
    VIRTUAL_PAGES.forEach(page=>result.push(clone(page)));
    return result;
  };
  function enforceVirtualCategories(result){
    const profile=result.categories.find(category=>category.id===PROFILE_CATEGORY_ID);
    if(profile){profile.page_id=PERSONAL_PAGE_ID;profile.kind='mixed';profile.show_on_web=false;profile.show_on_cv=false}
    const cvPersonal=result.categories.find(category=>category.id===CV_PERSONAL_CATEGORY_ID);
    if(cvPersonal){cvPersonal.page_id=PDF_CV_PAGE_ID;cvPersonal.kind='personal';cvPersonal.show_on_web=false;cvPersonal.show_on_cv=true;if(!result.cv_category_order.includes(CV_PERSONAL_CATEGORY_ID))result.cv_category_order.push(CV_PERSONAL_CATEGORY_ID)}
    return result;
  }

  const categoryEligible=category=>!!category&&!new Set([PROFILE_CATEGORY_ID,CV_PERSONAL_CATEGORY_ID]).has(category.id)&&!EXCLUDED_KINDS.has(String(category.kind||''));
  const kindLabel=kind=>kind==='mixed'?'一般內容（不限風格）':GENERAL_FORMAT_LABELS[kind]?`一般內容（${GENERAL_FORMAT_LABELS[kind]}）`:(CATEGORY_KIND_LABELS[kind]||kind);
  const kindOptions=selected=>STYLE_ORDER.map(kind=>`<option value="${esc(kind)}" ${kind===selected?'selected':''}>${esc(kindLabel(kind))}</option>`).join('');
  const cloneRows=rows=>(Array.isArray(rows)?rows:[]).map(row=>({category_id:String(row?.category_id||''),order:Number.isFinite(Number(row?.order))?Number(row.order):999999}));

  function defaultDossierOrder(categories,cvOrder=[]){
    const rows=categories.filter(category=>categoryEligible(category)&&DEFAULT_DOSSIER_KINDS.has(category.kind));
    const known=new Set(rows.map(category=>category.id)),result=[];
    for(const id of cvOrder||[])if(known.has(id)&&!result.includes(id))result.push(id);
    for(const category of rows)if(!result.includes(category.id))result.push(category.id);
    return result;
  }
  function normalizedDossierOrder(bundle,result){
    const known=new Set(result.categories.filter(categoryEligible).map(category=>category.id));
    const source=Array.isArray(bundle?.dossier_category_order)?bundle.dossier_category_order:defaultDossierOrder(result.categories,result.cv_category_order);
    return [...new Set(source.map(String).filter(id=>known.has(id)))];
  }
  function normalizedPlacements(bundle,result){
    const knownCategories=new Set(result.categories.map(category=>category.id));
    const itemIds=new Set(Object.keys(result.assignments||{}));
    const source=bundle?.placements&&typeof bundle.placements==='object'?bundle.placements:{};
    const output={};
    for(const id of itemIds){
      const primary=String(result.assignments[id]?.category_id||''),seen=new Set(),rows=[];
      for(const [index,row] of cloneRows(source[id]).entries()){
        const categoryId=String(row.category_id||'');
        if(!categoryId||categoryId===primary||!knownCategories.has(categoryId)||seen.has(categoryId))continue;
        seen.add(categoryId);rows.push({category_id:categoryId,order:Number.isFinite(Number(row.order))?Number(row.order):index});
      }
      output[id]=rows;
    }
    for(const category of result.categories){
      const refs=[];
      for(const [id,state] of Object.entries(result.assignments||{}))if(state.category_id===category.id)refs.push({id,kind:'primary',order:Number(state.order)||0});
      for(const [id,rows] of Object.entries(output))for(const row of rows)if(row.category_id===category.id)refs.push({id,kind:'placement',order:Number(row.order)||0});
      refs.sort((a,b)=>a.order-b.order||a.id.localeCompare(b.id));
      refs.forEach((ref,index)=>{
        if(ref.kind==='primary')result.assignments[ref.id].order=index;
        else{const row=output[ref.id].find(value=>value.category_id===category.id);if(row)row.order=index}
      });
    }
    for(const rows of Object.values(output))rows.sort((a,b)=>a.category_id.localeCompare(b.category_id)||a.order-b.order);
    return output;
  }

  const baseNormalizeLayoutBundle=normalizeLayoutBundle;
  normalizeLayoutBundle=function(bundle){
    const source=bundle&&typeof bundle==='object'?bundle:{};
    const result=enforceVirtualCategories(baseNormalizeLayoutBundle({...source,pages:ensureVirtualPages(source.pages)}));
    result.pages=ensureVirtualPages(result.pages);
    result.dossier_category_order=normalizedDossierOrder(source,result);
    result.placements=normalizedPlacements(source,result);
    return result;
  };

  const baseLayoutBundle=layoutBundle;
  layoutBundle=function(data){
    const result=baseLayoutBundle(data),stored=data?.settings?.dossier_category_order;
    const placements=Object.fromEntries(layoutItems(data).map(item=>[String(item.id),cloneRows(item.display_placements)]));
    return normalizeLayoutBundle({...result,dossier_category_order:Array.isArray(stored)?clone(stored):undefined,placements});
  };

  const baseApplyLayoutToData=applyLayoutToData;
  applyLayoutToData=function(data,bundle){
    const normalized=normalizeLayoutBundle(bundle),result=baseApplyLayoutToData(data,normalized);
    result.settings=result.settings||{};
    result.settings.pages=(result.settings.pages||[]).filter(page=>!isVirtualPage(page?.id));
    result.settings.categories=enforceVirtualCategories({...normalized,categories:clone(normalized.categories),cv_category_order:clone(normalized.cv_category_order)}).categories;
    result.settings.cv_category_order=clone(normalized.cv_category_order);
    result.settings.dossier_category_order=clone(normalized.dossier_category_order);
    const byId=new Map(layoutItems(result).map(item=>[String(item.id),item]));
    for(const [id,rows] of Object.entries(normalized.placements||{})){const item=byId.get(id);if(item)item.display_placements=cloneRows(rows)}
    return result;
  };

  layoutStructuralSignature=function(bundle){
    const value=normalizeLayoutBundle(bundle);
    return JSON.stringify({pages:value.pages,categories:value.categories,cv_category_order:value.cv_category_order,dossier_category_order:value.dossier_category_order,placements:value.placements});
  };

  const currentDossierOrder=()=>Array.isArray(layoutDraft?.dossier_category_order)?layoutDraft.dossier_category_order:[];
  const inDossier=id=>currentDossierOrder().includes(String(id||''));
  function setDossierMembership(id,enabled){
    if(!layoutDraft||!id)return;
    const category=layoutDraft.categories.find(row=>row.id===id),next=currentDossierOrder().filter(value=>value!==id);
    if(enabled&&categoryEligible(category))next.push(id);
    layoutDraft.dossier_category_order=next;
  }

  function categoryRefs(categoryId){
    const refs=[];
    for(const [id,state] of Object.entries(layoutDraft?.assignments||{}))if(state?.category_id===categoryId)refs.push({id,placement:false,order:Number(state.order)||0});
    for(const [id,rows] of Object.entries(layoutDraft?.placements||{}))for(const row of rows||[])if(row.category_id===categoryId)refs.push({id,placement:true,order:Number(row.order)||0});
    refs.sort((a,b)=>a.order-b.order||a.id.localeCompare(b.id));return refs;
  }
  const categoryHasItems=id=>categoryRefs(id).length>0;
  function setPlacement(itemId,categoryId,enabled){
    layoutDraft.placements=layoutDraft.placements||{};
    const primary=layoutDraft.assignments?.[itemId]?.category_id,rows=cloneRows(layoutDraft.placements[itemId]).filter(row=>row.category_id!==categoryId);
    if(enabled&&categoryId&&categoryId!==primary)rows.push({category_id:categoryId,order:categoryRefs(categoryId).length});
    layoutDraft.placements[itemId]=rows;
    layoutDraft=normalizeLayoutBundle(layoutDraft);
  }

  function previewMarkup(kind){
    const label=kind==='mixed'?'不限風格':GENERAL_FORMAT_LABELS[kind];
    if(!label)return `<div class="category-style-preview specialized"><span class="tag">${esc(kindLabel(kind))}</span><p>專用資料排版會依日期、機構、身分與連結欄位顯示。</p></div>`;
    const samples={
      generic:'<div class="style-demo style-demo-timeline"><span class="style-demo-date">2026</span><div><strong>Example entry</strong><small>Organization · Description</small></div></div>',
      education:'<div class="style-demo style-demo-columns"><span>2025–Present</span><div><strong>Position or degree</strong><small>Institution</small></div></div>',
      interest:'<div class="style-demo style-demo-headings"><strong>Function Field Arithmetic</strong><strong>Multiple Zeta Values</strong></div>',
      contact:'<div class="style-demo style-demo-card"><strong>Email</strong><span>name@example.edu</span></div>',
      personal:'<div class="style-demo style-demo-tags"><span>Language</span><span>ORCID</span><span>Website</span></div>',
      honor:'<div class="style-demo style-demo-compact"><span>2026</span><strong>Award or distinction</strong></div>',
      mixed:'<div class="style-demo style-demo-mixed"><div class="style-demo-card"><strong>Name</strong><span>Hung-Chun Tsui</span></div><div class="style-demo-compact"><span>2026</span><strong>Employment</strong></div></div>'
    };
    return `<div class="category-style-preview"><div class="category-style-preview-head"><strong>${esc(label)}</strong><span>${esc(kindLabel(kind))}</span></div>${samples[kind]||''}</div>`;
  }
  function attachPreview(select){
    if(!select)return;let holder=select.closest('.field')?.querySelector(':scope > [data-category-style-preview]');
    if(!holder){holder=document.createElement('div');holder.dataset.categoryStylePreview='';select.closest('.field')?.append(holder)}
    const render=()=>{holder.innerHTML=previewMarkup(select.value)};
    if(!select.dataset.dossierPreviewBound){select.dataset.dossierPreviewBound='1';select.addEventListener('change',render)}render();
  }
  function appendDossierCheckbox(root,category,kindSelect){
    if(!root||root.querySelector('[data-dossier-category]'))return;const options=root.querySelector('.form-options');if(!options)return;
    const label=document.createElement('label');label.className='switch';label.innerHTML=`<input type="checkbox" data-dossier-category ${category&&inDossier(category.id)?'checked':''}>放進審查資料`;options.append(label);
    const checkbox=label.querySelector('input'),refresh=()=>{const probe={id:category?.id,kind:kindSelect?.value||category?.kind||''};checkbox.disabled=!categoryEligible(probe);if(checkbox.disabled)checkbox.checked=false};kindSelect?.addEventListener('change',refresh);refresh();
  }
  function categoryTypeField(root){return [...root.querySelectorAll('.field')].find(field=>/項目類型|顯示風格/.test(field.querySelector('label')?.textContent||''))}
  function enhanceCategoryRoot(root,category){
    if(!root)return;let select=root.querySelector('select[data-category-field="kind"]');const typeField=categoryTypeField(root);
    if(!select){const input=typeField?.querySelector('input[disabled]');if(input&&category&&!categoryHasItems(category.id)){select=document.createElement('select');select.dataset.categoryField='kind';select.innerHTML=kindOptions(category.kind);input.replaceWith(select);typeField.insertAdjacentHTML('beforeend','<p class="field-hint">此類別沒有項目或引用，可以安全修改顯示風格。</p>')}else if(input&&category)input.value=kindLabel(category.kind)}
    if(select){const selected=select.value||category?.kind||'generic';select.innerHTML=kindOptions(selected);if(category)select.disabled=categoryHasItems(category.id);const hint=select.closest('.field')?.querySelector('.field-hint');if(hint&&category)hint.textContent=categoryHasItems(category.id)?'已有項目或引用的類別會鎖定風格；請先移出後再修改。':'此類別沒有項目或引用，可以安全修改顯示風格。';attachPreview(select)}
    else if(typeField&&category&&!typeField.querySelector('[data-category-style-preview]')){const holder=document.createElement('div');holder.dataset.categoryStylePreview='';holder.innerHTML=previewMarkup(category.kind);typeField.append(holder)}
    appendDossierCheckbox(root,category,select);
  }

  const baseCategoriesForEditor=categoriesForEditor;
  categoriesForEditor=function(type,record){const rows=baseCategoriesForEditor(type,record),mixed=layoutDraft.categories.filter(category=>category.kind==='mixed');return [...new Map([...rows,...mixed].map(category=>[category.id,category])).values()].sort(categorySort)};
  const baseCompatibleCategory=compatibleCategory;
  compatibleCategory=function(category,item){return category?.kind==='mixed'||baseCompatibleCategory(category,item)};

  const baseCategoryFormHtml=categoryFormHtml;
  categoryFormHtml=function(category){
    const template=document.createElement('template');template.innerHTML=baseCategoryFormHtml(category);const root=template.content,select=root.querySelector('select[data-category-field="kind"]');
    if(select){const selected=category?.kind||select.value||'generic';select.innerHTML=kindOptions(selected);if(category)select.disabled=categoryHasItems(category.id);const holder=document.createElement('div');holder.dataset.categoryStylePreview='';holder.innerHTML=previewMarkup(selected);select.closest('.field')?.append(holder)}
    const options=root.querySelector('.form-options');if(options){const allowed=categoryEligible({id:category?.id,kind:category?.kind||select?.value||'generic'});options.insertAdjacentHTML('beforeend',`<label class="switch"><input type="checkbox" data-dossier-category ${category&&inDossier(category.id)?'checked':''} ${allowed?'':'disabled'}>放進審查資料</label>`)}
    return template.innerHTML;
  };
  const baseCategoryEditorHtml=categoryEditorHtml;
  categoryEditorHtml=function(category){
    const template=document.createElement('template');template.innerHTML=baseCategoryEditorHtml(category);const root=template.content,typeField=categoryTypeField(root),input=typeField?.querySelector('input[disabled]'),systemCategory=[PROFILE_CATEGORY_ID,CV_PERSONAL_CATEGORY_ID].includes(category.id);
    if(input&&!categoryHasItems(category.id)&&!systemCategory){const select=document.createElement('select');select.dataset.categoryField='kind';select.innerHTML=kindOptions(category.kind);input.replaceWith(select);typeField.insertAdjacentHTML('beforeend','<p class="field-hint">此類別沒有項目或引用，可以安全修改顯示風格。</p>')}else if(input)input.value=kindLabel(category.kind);
    if(typeField){const holder=document.createElement('div');holder.dataset.categoryStylePreview='';holder.innerHTML=previewMarkup(category.kind);typeField.append(holder)}
    if(systemCategory){const pageSelect=root.querySelector('[data-category-field="page_id"]');if(pageSelect)pageSelect.disabled=true;const deleteButton=root.querySelector('[data-delete-category]');if(deleteButton){deleteButton.disabled=true;deleteButton.title='這是系統管理的特殊類別，不能刪除。'}root.querySelector('.actions')?.insertAdjacentHTML('beforebegin','<p class="field-hint">此類別屬於特殊管理頁面；主要頁面與顯示用途由系統維護。</p>')}
    const options=root.querySelector('.form-options');if(options)options.insertAdjacentHTML('beforeend',`<label class="switch"><input type="checkbox" data-dossier-category ${inDossier(category.id)?'checked':''} ${categoryEligible(category)?'':'disabled'}>放進審查資料</label>`);return template.innerHTML;
  };

  const baseOpenLayoutEditor=openLayoutEditor;
  openLayoutEditor=function(type,record){baseOpenLayoutEditor(type,record);if(type==='category'){const category=record?layoutDraft.categories.find(row=>row.id===record._layout_id):null;enhanceCategoryRoot(currentEditor?.root,category)}};
  const formValid=root=>['label.en','label.zh','title.en','title.zh'].every(path=>String(root.querySelector(`[data-category-field="${path}"]`)?.value||'').trim());
  const baseSaveLayoutCategory=saveLayoutCategory;
  saveLayoutCategory=function(id,root){const checked=!!root.querySelector('[data-dossier-category]')?.checked,before=new Set(layoutDraft.categories.map(row=>row.id)),valid=formValid(root);baseSaveLayoutCategory(id,root);if(!valid)return;const categoryId=id||layoutDraft.categories.find(row=>!before.has(row.id))?.id;if(!categoryId)return;setDossierMembership(categoryId,checked);saveLayoutDraft(checked?'已加入審查資料草稿':'已更新審查資料設定')};
  function enforceCategoryPage(category){
    if(!category)return;
    if(category.id===PROFILE_CATEGORY_ID){category.page_id=PERSONAL_PAGE_ID;category.kind='mixed';category.show_on_web=false;category.show_on_cv=false}
    if(category.id===CV_PERSONAL_CATEGORY_ID){category.page_id=PDF_CV_PAGE_ID;category.kind='personal';category.show_on_web=false;category.show_on_cv=true;if(!layoutDraft.cv_category_order.includes(CV_PERSONAL_CATEGORY_ID))layoutDraft.cv_category_order.push(CV_PERSONAL_CATEGORY_ID)}
    if(category.page_id===PDF_CV_PAGE_ID){category.show_on_web=false;category.show_on_cv=true;if(!layoutDraft.cv_category_order.includes(category.id))layoutDraft.cv_category_order.push(category.id)}
    if(category.page_id===PERSONAL_PAGE_ID){category.show_on_web=false;category.show_on_cv=false;layoutDraft.cv_category_order=layoutDraft.cv_category_order.filter(value=>value!==category.id)}
  }
  const baseSetCategoryFromEditor=setCategoryFromEditor;
  setCategoryFromEditor=function(id,root){if(formValid(root))setDossierMembership(id,!!root.querySelector('[data-dossier-category]')?.checked);const result=baseSetCategoryFromEditor(id,root);enforceCategoryPage(layoutDraft.categories.find(category=>category.id===id));layoutDraft=normalizeLayoutBundle(layoutDraft);return result};

  function placementEditor(root,type,record){
    if(!root||['page','category','academic_event'].includes(type)||root.querySelector('[data-placement-editor]'))return;
    const itemType=record?.type||type,primary=root.querySelector('#itemCategorySelector'),itemId=String(record?.id||'');
    const displayStyle=record?.display_style||itemType;
    const candidates=layoutDraft.categories.filter(category=>!EXCLUDED_KINDS.has(category.kind)&&category.id!==PROFILE_CATEGORY_ID&&(category.kind==='mixed'||category.kind===ITEM_KIND[itemType]||category.kind===displayStyle));
    const details=document.createElement('details');details.dataset.placementEditor='';details.className='placement-editor';details.open=true;
    details._placementRows=cloneRows(itemId?layoutDraft?.placements?.[itemId]||record?.display_placements:[]);
    details.innerHTML='<summary><strong>額外顯示位置</strong><span class="muted">用下拉選單逐一加入；同一筆資料仍只維護一份。</span></summary><div data-placement-current-list></div><div class="placement-add-row"><select data-placement-add-select aria-label="選擇額外顯示位置"></select><button class="button" type="button" data-placement-add-button>新增引用位置</button></div>';
    (primary?.closest('.field')||root.querySelector('.form-options')||root).after(details);
    const render=()=>{
      const main=String(primary?.value||record?.category_id||'');
      details._placementRows=cloneRows(details._placementRows).filter(row=>row.category_id!==main&&candidates.some(category=>category.id===row.category_id));
      const current=new Set(details._placementRows.map(row=>row.category_id)),list=details.querySelector('[data-placement-current-list]'),select=details.querySelector('[data-placement-add-select]');
      list.innerHTML=details._placementRows.map((row,index)=>{const category=candidates.find(value=>value.id===row.category_id);return category?`<div class="placement-current-row" data-placement-row="${esc(category.id)}"><span><strong>${index+1}. ${esc(pageName(category.page_id))}</strong><small>${esc(categoryName(category))}</small></span><button class="button danger" type="button" data-placement-remove="${esc(category.id)}">移除</button></div>`:''}).join('')||'<p class="muted">目前沒有額外顯示位置。</p>';
      const available=candidates.filter(category=>category.id!==main&&!current.has(category.id));
      select.innerHTML='<option value="">選擇要引用到的頁面與類別…</option>'+available.map(category=>`<option value="${esc(category.id)}">${esc(pageName(category.page_id))} → ${esc(categoryName(category))}</option>`).join('');
      select.disabled=!available.length;details.querySelector('[data-placement-add-button]').disabled=!available.length;
    };
    details.addEventListener('click',event=>{
      const remove=event.target.closest('[data-placement-remove]');
      if(remove){details._placementRows=details._placementRows.filter(row=>row.category_id!==remove.dataset.placementRemove);render();return}
      const add=event.target.closest('[data-placement-add-button]');
      if(add){const select=details.querySelector('[data-placement-add-select]'),id=select.value;if(!id)return;details._placementRows.push({category_id:id,order:details._placementRows.length});render()}
    });
    primary?.addEventListener('change',render);render();
  }

  const baseOpenEditor=openEditor;
  openEditor=function(type,record,options={}){
    baseOpenEditor(type,record,options);if(['page','category','academic_event'].includes(type)||record?._layout_kind)return;
    const root=currentEditor?.root;if(!root)return;
    if(type==='generic'&&!record){
      const format=root.querySelector('#generalContentFormat'),category=root.querySelector('#itemCategorySelector');
      const appendMixed=()=>{if(!format||!category)return;for(const row of layoutDraft.categories.filter(value=>value.kind==='mixed'))if(![...category.options].some(option=>option.value===row.id))category.add(new Option(`${pageName(row.page_id)} → ${categoryName(row)}`,row.id));if(category.options.length){category.disabled=false;root.querySelector('#saveEditor').disabled=false}};
      const original=format?.onchange;if(format)format.onchange=event=>{original?.call(format,event);appendMixed()};queueMicrotask(appendMixed);
    }
    placementEditor(root,type,record);
    if(record?.type==='generic'&&!root.querySelector('[data-mixed-item-style]')){
      const field=document.createElement('div');field.className='field';field.dataset.mixedItemStyle='';
      const selected=record.display_style||'generic';
      field.innerHTML=`<label>在「不限風格」類別中的排版</label><select id="mixedItemDisplayStyle">${GENERAL_FORMAT_ORDER.map(kind=>`<option value="${esc(kind)}" ${kind===selected?'selected':''}>${esc(GENERAL_FORMAT_LABELS[kind])}</option>`).join('')}</select><p class="field-hint">這只決定項目放進「一般內容（不限風格）」類別時的外觀，不會改變其他類別。</p>`;
      root.querySelector('[data-placement-editor]')?.before(field);
    }
  };

  const baseCollectEditor=collectEditor;
  collectEditor=function(type,base){
    const result=baseCollectEditor(type,base),root=currentEditor?.root,editor=root?.querySelector('[data-placement-editor]');
    const selectedStyle=root?.querySelector('#mixedItemDisplayStyle')?.value||root?.querySelector('#generalContentFormat')?.value||'';
    if(selectedStyle&&GENERAL_FORMAT_ORDER.includes(selectedStyle))result.o.display_style=selectedStyle;
    if(!editor)return result;
    const main=String(result.o.category_id||''),old=cloneRows(layoutDraft?.placements?.[result.o.id]||base?.display_placements),oldMap=new Map(old.map(row=>[row.category_id,row.order]));
    const selected=cloneRows(editor._placementRows).filter(row=>row.category_id!==main).map((row,index)=>({category_id:row.category_id,order:oldMap.has(row.category_id)?oldMap.get(row.category_id):index}));
    result.o.display_placements=selected;layoutDraft.placements=layoutDraft.placements||{};layoutDraft.placements[result.o.id]=cloneRows(selected);return result;
  };

  const baseDeleteCategory=deleteCategory;
  deleteCategory=function(id){const dossierBefore=clone(currentDossierOrder()),placementBefore=clone(layoutDraft?.placements||{});baseDeleteCategory(id);if(!layoutDraft.categories.some(row=>row.id===id)){layoutDraft.dossier_category_order=dossierBefore.filter(value=>value!==id);for(const itemId of Object.keys(layoutDraft.placements||{}))layoutDraft.placements[itemId]=cloneRows(layoutDraft.placements[itemId]).filter(row=>row.category_id!==id);saveLayoutDraft('已移除刪除類別的審查資料與引用')}else{layoutDraft.dossier_category_order=dossierBefore;layoutDraft.placements=placementBefore}};

  const basePageEditorHtml=pageEditorHtml;
  pageEditorHtml=function(page){
    const virtual=virtualPage(page?.id);
    if(!virtual)return basePageEditorHtml(page);
    const kind=page.id===PDF_CV_PAGE_ID?'PDF 文件頁面':'資料管理頁面';
    const purpose=page.id===PDF_CV_PAGE_ID?'只用於設定 PDF 履歷的專屬類別；不會生成可瀏覽的 HTML 頁面。':'集中保存個人資料主項目；其他網頁與 PDF 履歷只引用這些資料。';
    return `<div class="notice virtual-page-notice"><strong>${esc(kind)} · 雙語</strong><p>${esc(purpose)}</p><div class="virtual-page-language-row"><span class="tag">English</span><span class="tag">中文</span><span class="tag">不公開</span></div></div>`;
  };

  const baseRenderLayoutManager=renderLayoutManager;
  renderLayoutManager=function(){
    baseRenderLayoutManager();const box=$('#layoutManager');if(!box)return;const addSelect=box.querySelector('#newCategoryKind');
    if(addSelect){const selected=addSelect.value||'generic';addSelect.innerHTML=kindOptions(selected);attachPreview(addSelect);const body=addSelect.closest('.layout-tool-body');if(body&&!body.querySelector('[data-new-category-dossier]')){const label=document.createElement('label');label.className='switch';label.innerHTML='<input type="checkbox" data-new-category-dossier>放進審查資料';body.querySelector('#addCategoryButton')?.before(label);const checkbox=label.querySelector('input'),refresh=()=>{checkbox.disabled=!categoryEligible({kind:addSelect.value});if(checkbox.disabled)checkbox.checked=false};addSelect.addEventListener('change',refresh);refresh()}}
    box.querySelectorAll('[data-category-editor]').forEach(root=>enhanceCategoryRoot(root,layoutDraft.categories.find(row=>row.id===root.dataset.categoryEditor)));
  };
  const baseAddCategoryFromManager=addCategoryFromManager;
  addCategoryFromManager=function(){const checked=!!document.querySelector('[data-new-category-dossier]')?.checked,before=new Set(layoutDraft.categories.map(row=>row.id)),valid=String($('#newCategoryEn')?.value||'').trim()&&String($('#newCategoryZh')?.value||'').trim();baseAddCategoryFromManager();if(!valid)return;const category=layoutDraft.categories.find(row=>!before.has(row.id));if(!category)return;enforceCategoryPage(category);if(checked)setDossierMembership(category.id,true);layoutDraft=normalizeLayoutBundle(layoutDraft);saveLayoutDraft(checked?'已新增類別並加入審查資料草稿':'已新增類別草稿')};

  const baseFillOrderPageSelector=fillOrderPageSelector;
  fillOrderPageSelector=function(){
    const select=$('#layoutOrderPage'),old=select?.value;baseFillOrderPageSelector();if(!select)return;
    [...select.options].filter(option=>['dossier','__dossier__',PDF_CV_PAGE_ID].includes(option.value)).forEach(option=>option.remove());
    const cv=[...select.options].find(option=>option.value==='__cv__');if(cv)cv.textContent='PDF 履歷';else select.add(new Option('PDF 履歷','__cv__'));
    const personal=[...select.options].find(option=>option.value===PERSONAL_PAGE_ID);if(personal)personal.textContent='個人資料';else select.add(new Option('個人資料',PERSONAL_PAGE_ID));
    select.add(new Option('審查資料','__dossier__'));
    const specialOrder=['__cv__',PERSONAL_PAGE_ID,'__dossier__'];
    specialOrder.forEach(value=>{const option=[...select.options].find(row=>row.value===value);if(option)select.append(option)});
    const next=old==='dossier'?'__dossier__':old===PDF_CV_PAGE_ID?'__cv__':old;
    if(next&&[...select.options].some(option=>option.value===next))select.value=next;
  };

  const baseOrderCategoryCard=orderCategoryCard;
  orderCategoryCard=function(category,index,total,map,cvMode=false){
    const mode=$('#layoutOrderPage')?.value||'';
    if(!cvMode&&['featured_publications','upcoming'].includes(category.kind))return baseOrderCategoryCard(category,index,total,map,cvMode);
    const refs=categoryRefs(category.id),first=map.get(refs[0]?.id),compatible=first?layoutDraft.categories.filter(value=>compatibleCategory(value,first)&&value.id!==category.id):[];
    const pageLabel=mode==='__cv__'?'PDF 履歷':pageName(category.page_id);
    return `<div class="layout-order-category" data-order-category="${esc(category.id)}"><div class="layout-order-category-head"><div><span class="tag">${esc(kindLabel(category.kind))}</span><strong>${index+1}. ${esc(categoryName(category))}</strong><span class="muted">${esc(pageLabel)} · ${refs.length} 個項目／引用</span></div><div class="actions"><button class="button" data-category-up="${esc(category.id)}" ${index===0?'disabled':''}>類別 ↑</button><button class="button" data-category-down="${esc(category.id)}" ${index===total-1?'disabled':''}>類別 ↓</button><button class="button" data-edit-category-jump="${esc(category.id)}">編輯類別</button></div></div>${!cvMode?`<div class="order-sort-tools"><span class="muted">此類別快速排序：</span><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="newest">日期新到舊</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="oldest">日期舊到新</button><button class="button" data-sort-category="${esc(category.id)}" data-sort-mode="title">名稱</button></div>`:''}<div>${refs.map((ref,rowIndex)=>{const item=map.get(ref.id);if(!item)return'';const key=`${ref.id}@@${category.id}`,referenceTag=ref.placement?'<span class="tag">引用個人資料</span> ':'';return `<div class="layout-order-item"><div><strong>${rowIndex+1}. ${esc(itemName(item))}</strong><span class="muted">${referenceTag}${esc(itemMetaChinese(item))}</span></div><div class="layout-order-item-actions"><button class="button" data-item-up="${esc(key)}" ${rowIndex===0?'disabled':''}>↑</button><button class="button" data-item-down="${esc(key)}" ${rowIndex===refs.length-1?'disabled':''}>↓</button>${ref.placement&&!cvMode?`<button class="button danger" data-remove-placement="${esc(key)}">移除引用</button>`:!ref.placement&&compatible.length&&!cvMode?`<select data-move-item="${esc(ref.id)}"><option value="">移到其他類別…</option>${compatible.map(value=>`<option value="${esc(value.id)}">${esc(pageName(value.page_id))} → ${esc(categoryName(value))}</option>`).join('')}</select>`:''}</div></div>`}).join('')||'<p class="muted">此類別目前沒有項目。</p>'}</div></div>`;
  };

  const baseMoveItem=moveItem;
  moveItem=function(key,delta){
    if(!String(key).includes('@@'))return baseMoveItem(key,delta);const [id,categoryId]=String(key).split('@@'),refs=categoryRefs(categoryId),index=refs.findIndex(ref=>ref.id===id);if(!moveInArray(refs,index,delta))return;
    refs.forEach((ref,order)=>{if(ref.placement){const row=layoutDraft.placements[ref.id].find(value=>value.category_id===categoryId);if(row)row.order=order}else layoutDraft.assignments[ref.id].order=order});saveLayoutDraft('已調整類別內項目與引用順序');
  };
  const baseSortCategory=sortCategory;
  sortCategory=function(id,mode){
    const refs=categoryRefs(id),map=new Map(layoutItems(effectiveSite()).map(item=>[String(item.id),item]));if(!refs.some(ref=>ref.placement))return baseSortCategory(id,mode);
    refs.sort((a,b)=>{const x=map.get(a.id),y=map.get(b.id);if(mode==='title')return itemName(x).localeCompare(itemName(y),'zh-Hant');const value=recordSortValue(x).localeCompare(recordSortValue(y));return(mode==='newest'?-value:value)||itemName(x).localeCompare(itemName(y),'zh-Hant')});
    refs.forEach((ref,order)=>{if(ref.placement){const row=layoutDraft.placements[ref.id].find(value=>value.category_id===id);if(row)row.order=order}else layoutDraft.assignments[ref.id].order=order});saveLayoutDraft('已套用類別內快速排序');
  };
  const baseUnifiedOrderClick=unifiedOrderClick;
  unifiedOrderClick=function(event){const button=event.target.closest('[data-remove-placement]');if(button){const [id,categoryId]=button.dataset.removePlacement.split('@@');setPlacement(id,categoryId,false);saveLayoutDraft('已移除額外顯示位置');return}return baseUnifiedOrderClick(event)};

  function bindDossierOrderControls(){
    const select=$('#layoutOrderPage'),editor=$('#layoutOrderEditor');
    if(select)select.onchange=()=>renderUnifiedOrder();
    if(editor){editor.onclick=event=>unifiedOrderClick(event);editor.onchange=event=>unifiedOrderChange(event)}
  }
  const baseRenderUnifiedOrder=renderUnifiedOrder;
  renderUnifiedOrder=function(){
    if($('#layoutOrderPage')?.value!=='__dossier__'){const result=baseRenderUnifiedOrder();bindDossierOrderControls();return result}
    initLayoutState();syncLayoutAssignments();fillOrderPageSelector();const byId=new Map(layoutDraft.categories.map(row=>[row.id,row])),categories=currentDossierOrder().map(id=>byId.get(id)).filter(Boolean),items=new Map(layoutItems(effectiveSite()).map(item=>[String(item.id),item]));
    $('#layoutOrderEditor').innerHTML='<div class="notice"><strong>審查資料排序</strong><p>操作方式與 PDF 履歷相同：上方調整類別順序，下方調整各類別中的項目與引用順序。</p></div>'+(categories.map((category,index)=>orderCategoryCard(category,index,categories.length,items,true)).join('')||'<p class="muted">尚未選擇類別；請先在類別設定勾選「放進審查資料」。</p>');
    bindDossierOrderControls();
  };
  const baseMoveCategory=moveCategory;
  moveCategory=function(id,delta){if($('#layoutOrderPage')?.value!=='__dossier__')return baseMoveCategory(id,delta);const index=currentDossierOrder().indexOf(id);if(moveInArray(layoutDraft.dossier_category_order,index,delta))saveLayoutDraft('已調整審查資料類別順序')};

  const baseLayoutPreviewHtml=layoutPreviewHtml;
  layoutPreviewHtml=function(op){let html=baseLayoutPreviewHtml(op),before=normalizeLayoutBundle(op.before),after=normalizeLayoutBundle(op.after);if(JSON.stringify(before.dossier_category_order)!==JSON.stringify(after.dossier_category_order)){const names=after.dossier_category_order.map(id=>categoryName(after.categories.find(row=>row.id===id))).join(' → ');html+=`<details class="diff"><summary><strong>審查資料順序有變更</strong></summary><div class="preview-card"><p>${esc(names||'目前沒有類別')}</p></div></details>`}if(JSON.stringify(before.placements)!==JSON.stringify(after.placements))html+='<details class="diff"><summary><strong>額外顯示位置有變更</strong></summary><div class="preview-card"><p>同一筆資料的引用位置或獨立排序已更新。</p></div></details>';return html};

  function decorateRecordPageBadges(){
    const categories=new Map((layoutDraft?.categories||[]).map(category=>[category.id,category]));
    const records=new Map([...(typeof allRecords==='function'?allRecords(effectiveSite()):[]),...(typeof layoutCatalogRecords==='function'?layoutCatalogRecords():[])].map(item=>[String(item.id),item]));
    document.querySelectorAll('#records .row').forEach(row=>{
      const id=row.querySelector('[data-edit]')?.dataset.edit,item=records.get(String(id||''));
      if(!item||['page','category'].includes(item.type))return;
      const primaryId=String(layoutDraft?.assignments?.[id]?.category_id||item.category_id||''),placements=cloneRows(layoutDraft?.placements?.[id]||item.display_placements),pageRows=[];
      const addPage=(categoryId,primary=false)=>{const category=categories.get(categoryId),pageId=category?.page_id;if(!pageId||pageRows.some(value=>value.pageId===pageId))return;pageRows.push({pageId,category,primary})};
      addPage(primaryId,true);placements.forEach(value=>addPage(value.category_id,false));
      const badges=row.querySelector('.record-badges');if(!badges)return;
      badges.querySelectorAll('.record-badge-page').forEach(node=>node.remove());
      const categoryBadge=badges.querySelector('.record-badge-category');
      pageRows.forEach(value=>{const badge=document.createElement('span');badge.className='record-badge record-badge-page';badge.title=value.category?categoryName(value.category):'';badge.innerHTML=`<span>${value.primary?'所在頁面':'引用頁面'}</span><strong>${esc(pageName(value.pageId))}</strong>`;categoryBadge?badges.insertBefore(badge,categoryBadge):badges.append(badge)});
    });
  }
  const baseRenderRecordsWithPlacements=renderRecords;
  renderRecords=function(){const result=baseRenderRecordsWithPlacements();decorateRecordPageBadges();return result};

  const style=document.createElement('style');style.textContent=`
    [data-category-style-preview]{margin-top:8px}.category-style-preview{border:1px solid #ded3ca;border-radius:12px;padding:10px;background:#fcfaf8;display:grid;gap:8px}.category-style-preview.specialized p{margin:0;color:#6f655e;font-size:.78rem}.category-style-preview-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.category-style-preview-head span{font-size:.72rem;color:#766c65}.style-demo{border:1px solid #e4dad2;border-radius:9px;padding:9px;background:#fff;min-height:56px}.style-demo small{display:block;color:#766c65;margin-top:3px}.style-demo-timeline{display:grid;grid-template-columns:54px 1fr;gap:9px;border-left:4px solid #8d493d}.style-demo-date{font-weight:800;color:#8d493d}.style-demo-columns{display:grid;grid-template-columns:100px 1fr;gap:10px}.style-demo-headings{display:grid;gap:7px}.style-demo-headings strong{padding-bottom:6px;border-bottom:1px solid #eee4dc}.style-demo-card{display:grid;grid-template-columns:90px 1fr;gap:8px;box-shadow:0 7px 18px #3d2b2310}.style-demo-tags{display:flex;gap:6px;flex-wrap:wrap}.style-demo-tags span{background:#eee5de;border-radius:999px;padding:4px 8px;font-size:.75rem;font-weight:700}.style-demo-compact{display:flex;gap:12px;align-items:center}.style-demo-compact span{font-weight:800;color:#8d493d}.style-demo-mixed{display:grid;gap:7px}.placement-editor{border:1px solid #ded3ca;border-radius:11px;padding:10px;margin:10px 0}.placement-editor>summary{cursor:pointer;display:flex;gap:8px;justify-content:space-between}.placement-options{display:grid;gap:5px;margin-top:8px}.placement-options .switch{margin:0}.placement-add-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;margin-top:10px}.placement-current-row{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #eee5de}.placement-current-row span{display:grid;gap:2px}.placement-current-row small{color:#766c65}@media(max-width:650px){.placement-add-row{grid-template-columns:1fr}.placement-current-row{align-items:flex-start;flex-direction:column}}`;document.head.append(style);

  if(layoutReady){const stored=site?.settings?.dossier_category_order,placements=Object.fromEntries(layoutItems(site||{}).map(item=>[String(item.id),cloneRows(item.display_placements)]));layoutBase=normalizeLayoutBundle({...layoutBase,dossier_category_order:Array.isArray(stored)?stored:layoutBase?.dossier_category_order,placements});layoutDraft=normalizeLayoutBundle({...layoutDraft,dossier_category_order:layoutDraft?.dossier_category_order||layoutBase.dossier_category_order,placements:layoutDraft?.placements||placements})}
  const dossierBaseRenderAll=renderAll;
  renderAll=function(){const result=dossierBaseRenderAll();bindDossierOrderControls();decorateRecordPageBadges();return result};
  bindDossierOrderControls();
  if(site)renderAll();
})();
