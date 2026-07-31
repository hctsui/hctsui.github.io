/* Editable SEO/Open Graph metadata and footer content. */
(function installSiteSettingsManager(){
  const DRAFT_KEY='hctsui-site-settings-draft';
  const PAGE_LABELS={home:'首頁',cv:'履歷',publications:'論文',activities:'學術活動',teaching:'教學'};
  const ICONS=[['none','無圖標'],['copyright','版權'],['email','Email'],['link','連結'],['github','GitHub'],['orcid','ORCID'],['location','地點'],['book','書籍'],['calendar','日曆']];
  const ALIGNMENTS=[['left','靠左'],['center','置中'],['right','靠右']];
  let remote=null,draft=null,ready=false,currentPage='home',currentSection='seo',siteDataCache={};

  const copy=value=>structuredClone(value);
  const text=(value,limit=500)=>String(value||'').trim().replace(/\s+/g,' ').slice(0,limit);
  const pair=(value,fallback={en:'',zh:''},limit=500)=>({en:text(value?.en||fallback.en,limit),zh:text(value?.zh||fallback.zh,limit)});
  const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  function safeWebUrl(value,{relative=false,mailto=false}={}){
    const raw=String(value||'').trim();if(!raw)return '';
    if(mailto&&/^mailto:[^\s@]+@[^\s@]+$/i.test(raw))return raw;
    if(relative&&!/^[A-Za-z][A-Za-z0-9+.-]*:/.test(raw)&&!raw.startsWith('//')&&!/\s/.test(raw))return raw;
    try{const url=new URL(raw);return ['http:','https:'].includes(url.protocol)&&!/[\s]/.test(raw)?raw:'';}catch{return '';}
  }
  function pageDefaults(siteData){
    const defaults={
      home:{title:{en:'Hung-Chun Tsui | Mathematics',zh:'崔鴻竣｜數學'},description:{en:'Academic website of Hung-Chun Tsui, PhD student in mathematics at National Tsing Hua University.',zh:'崔鴻竣的學術個人網站，收錄研究、論文、學術活動與教學經歷。'}},
      cv:{title:{en:'Curriculum Vitae | Hung-Chun Tsui',zh:'履歷｜崔鴻竣'},description:{en:'Curriculum vitae of Hung-Chun Tsui.',zh:'崔鴻竣的學術履歷。'}},
      publications:{title:{en:'Publications | Hung-Chun Tsui',zh:'論文｜崔鴻竣'},description:{en:'Publications and preprints by Hung-Chun Tsui.',zh:'崔鴻竣的論文與預印本。'}},
      activities:{title:{en:'Activities | Hung-Chun Tsui',zh:'學術活動｜崔鴻竣'},description:{en:'Academic talks, visits, conferences, and workshops of Hung-Chun Tsui.',zh:'崔鴻竣的學術報告、訪問、會議與工作坊紀錄。'}},
      teaching:{title:{en:'Teaching | Hung-Chun Tsui',zh:'教學｜崔鴻竣'},description:{en:'Teaching experience of Hung-Chun Tsui.',zh:'崔鴻竣的教學與課程助教經歷。'}},
    };
    for(const page of siteData?.settings?.pages||[]){
      if(!defaults[page.id]||page.id==='home')continue;
      for(const lang of ['en','zh']){
        const title=page.header?.title?.[lang],intro=page.header?.intro?.[lang];
        if(title)defaults[page.id].title[lang]=lang==='en'?`${title} | Hung-Chun Tsui`:`${title}｜崔鴻竣`;
        if(intro)defaults[page.id].description[lang]=intro;
      }
    }
    return defaults;
  }
  function defaultSettings(siteData){
    const defaults=pageDefaults(siteData),pages={};
    Object.entries(defaults).forEach(([id,value])=>pages[id]={title:copy(value.title),description:copy(value.description),og_title:{en:'',zh:''},og_description:{en:'',zh:''},og_image:''});
    return {seo:{schema_version:1,base_url:'https://hctsui.github.io',site_name:{en:'Hung-Chun Tsui',zh:'崔鴻竣'},default_image:'assets/photo-1440.webp',pages},footer:{schema_version:1,items:[{id:'copyright',text:{en:'{year} Hung-Chun Tsui',zh:'{year} Hung-Chun Tsui'},url:'',icon:'copyright',alignment:'left',new_tab:false},{id:'last-updated',text:{en:'Last updated: {updated}',zh:'最後更新：{updated}'},url:'',icon:'none',alignment:'right',new_tab:false}]}};
  }
  function normalize(value,siteData){
    const defaults=defaultSettings(siteData),source=value&&typeof value==='object'?value:{},seoSource=source.seo||{},pagesSource=seoSource.pages||{},pages={};
    const ids=[...new Set([...Object.keys(defaults.seo.pages),...Object.keys(pagesSource)])];
    for(const id of ids){const fallback=defaults.seo.pages[id]||{title:{en:id,zh:id},description:{en:'',zh:''},og_title:{en:'',zh:''},og_description:{en:'',zh:''},og_image:''},raw=pagesSource[id]||{};pages[id]={title:pair(raw.title,fallback.title,180),description:pair(raw.description,fallback.description,500),og_title:pair(raw.og_title,fallback.og_title,180),og_description:pair(raw.og_description,fallback.og_description,500),og_image:String(raw.og_image||'').trim()};}
    const footerRows=Array.isArray(source.footer?.items)?source.footer.items:defaults.footer.items;
    const used=new Set(),items=[];
    footerRows.forEach((raw,index)=>{let base=text(raw?.id||`footer-item-${index+1}`,80).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||`footer-item-${index+1}`,id=base,n=2;while(used.has(id))id=`${base}-${n++}`;used.add(id);items.push({id,text:pair(raw?.text,{en:'',zh:''},300),url:String(raw?.url||'').trim(),icon:ICONS.some(x=>x[0]===raw?.icon)?raw.icon:'none',alignment:ALIGNMENTS.some(x=>x[0]===raw?.alignment)?raw.alignment:'center',new_tab:Boolean(raw?.new_tab)});});
    return {seo:{schema_version:1,base_url:String(seoSource.base_url||defaults.seo.base_url).trim(),site_name:pair(seoSource.site_name,defaults.seo.site_name,120),default_image:String(seoSource.default_image||defaults.seo.default_image).trim(),pages},footer:{schema_version:1,items}};
  }
  function validate(){
    const errors=[];if(!ready)return errors;const value=normalize(draft,siteDataCache);
    if(!safeWebUrl(value.seo.base_url))errors.push('網站基準網址必須是完整的 http 或 https 網址');
    if(value.seo.default_image&&!safeWebUrl(value.seo.default_image,{relative:true}))errors.push('預設分享圖片必須是相對路徑或 http／https 網址');
    for(const [id,page] of Object.entries(value.seo.pages))for(const lang of ['en','zh']){if(!page.title[lang])errors.push(`${PAGE_LABELS[id]||id}：${lang==='en'?'英文':'中文'} SEO 標題不可空白`);if(page.description[lang].length>500)errors.push(`${PAGE_LABELS[id]||id}：SEO 描述過長`);} 
    if(value.footer.items.length>30)errors.push('頁尾最多 30 個項目');
    value.footer.items.forEach((item,index)=>{if(!item.text.en&&!item.text.zh)errors.push(`頁尾第 ${index+1} 項需要英文或中文文字`);if(item.url&&!safeWebUrl(item.url,{relative:true,mailto:true}))errors.push(`頁尾第 ${index+1} 項網址格式不正確`);});
    return [...new Set(errors)];
  }
  function dirty(){return ready&&!equal(normalize(remote,siteDataCache),normalize(draft,siteDataCache));}
  function loadSaved(base){
    try{const saved=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');if(saved?.base&&saved?.data&&equal(normalize(saved.base,siteDataCache),normalize(base,siteDataCache)))return normalize(saved.data,siteDataCache);if(saved)localStorage.removeItem(DRAFT_KEY);}catch{localStorage.removeItem(DRAFT_KEY);}return copy(base);
  }
  function save(rerender=true){draft=normalize(draft,siteDataCache);if(dirty())localStorage.setItem(DRAFT_KEY,JSON.stringify({base:remote,data:draft}));else localStorage.removeItem(DRAFT_KEY);if(rerender)render();else renderStatus();if(typeof site!=='undefined'&&site&&typeof renderPreview==='function')renderPreview(false);}
  function operation(){return dirty()?{op:'site_settings',before:copy(normalize(remote,siteDataCache)),after:copy(normalize(draft,siteDataCache))}:null;}
  function clearDraft(reload=false){localStorage.removeItem(DRAFT_KEY);draft=copy(remote);if(reload)render();}
  function previewHtml(op){
    const before=normalize(op?.before,siteDataCache),after=normalize(op?.after,siteDataCache);let seoChanged=0;for(const id of Object.keys(after.seo.pages))if(JSON.stringify(before.seo.pages[id])!==JSON.stringify(after.seo.pages[id]))seoChanged++;
    return `<details class="diff"><summary><strong>SEO／OG 與頁尾</strong></summary><div class="preview-columns"><div class="preview-card"><h4>SEO／OG</h4><div class="preview-value">${seoChanged} 個頁面變更<br>基準網址：${esc(after.seo.base_url)}</div></div><div class="preview-card"><h4>頁尾</h4><div class="preview-value">${before.footer.items.length} → ${after.footer.items.length} 個項目</div></div></div></details>`;
  }
  function optionRows(options,selected){return options.map(([value,label])=>`<option value="${value}" ${value===selected?'selected':''}>${label}</option>`).join('');}
  function renderSeo(){
    const page=draft.seo.pages[currentPage]||draft.seo.pages.home;
    const root=document.querySelector('#seoSettingsPane');if(!root)return;
    root.innerHTML=`<div class="site-settings-global"><div class="field"><label>網站基準網址</label><input data-seo-global="base_url" value="${esc(draft.seo.base_url)}" placeholder="https://hctsui.github.io"></div><div class="pair-grid"><div class="field"><label>網站名稱（英文）</label><input data-seo-site-name="en" value="${esc(draft.seo.site_name.en)}"></div><div class="field"><label>網站名稱（中文）</label><input data-seo-site-name="zh" value="${esc(draft.seo.site_name.zh)}"></div></div><div class="field"><label>預設 OG 分享圖片</label><input data-seo-global="default_image" value="${esc(draft.seo.default_image)}" placeholder="assets/photo-1440.webp"><p class="field-hint">可使用網站內相對路徑或完整 https 網址。</p></div></div><div class="field"><label>編輯頁面</label><select id="seoPageSelect">${Object.keys(draft.seo.pages).map(id=>`<option value="${esc(id)}" ${id===currentPage?'selected':''}>${esc(PAGE_LABELS[id]||id)}</option>`).join('')}</select></div><div class="site-settings-card"><h3>${esc(PAGE_LABELS[currentPage]||currentPage)}</h3><div class="pair-grid"><div class="field"><label>SEO 標題（英文）</label><input data-page-field="title.en" value="${esc(page.title.en)}"></div><div class="field"><label>SEO 標題（中文）</label><input data-page-field="title.zh" value="${esc(page.title.zh)}"></div></div><div class="pair-grid"><div class="field"><label>Meta description（英文）</label><textarea data-page-field="description.en">${esc(page.description.en)}</textarea></div><div class="field"><label>Meta description（中文）</label><textarea data-page-field="description.zh">${esc(page.description.zh)}</textarea></div></div><div class="pair-grid"><div class="field"><label>OG 標題（英文，留白沿用 SEO）</label><input data-page-field="og_title.en" value="${esc(page.og_title.en)}"></div><div class="field"><label>OG 標題（中文，留白沿用 SEO）</label><input data-page-field="og_title.zh" value="${esc(page.og_title.zh)}"></div></div><div class="pair-grid"><div class="field"><label>OG 描述（英文，留白沿用 Meta）</label><textarea data-page-field="og_description.en">${esc(page.og_description.en)}</textarea></div><div class="field"><label>OG 描述（中文，留白沿用 Meta）</label><textarea data-page-field="og_description.zh">${esc(page.og_description.zh)}</textarea></div></div><div class="field"><label>本頁 OG 圖片（留白沿用預設）</label><input data-page-field="og_image" value="${esc(page.og_image)}"></div></div>`;
  }
  function footerRow(item,index){return `<div class="footer-editor-row" data-footer-index="${index}"><div class="footer-editor-head"><strong>頁尾項目 ${index+1}</strong><div class="actions"><button class="button" type="button" data-footer-move="up" ${index===0?'disabled':''}>上移</button><button class="button" type="button" data-footer-move="down" ${index===draft.footer.items.length-1?'disabled':''}>下移</button><button class="button danger" type="button" data-footer-remove>刪除</button></div></div><div class="pair-grid"><div class="field"><label>文字（英文）</label><input data-footer-field="text.en" value="${esc(item.text.en)}"></div><div class="field"><label>文字（中文）</label><input data-footer-field="text.zh" value="${esc(item.text.zh)}"></div></div><div class="pair-grid"><div class="field"><label>小圖標</label><select data-footer-field="icon">${optionRows(ICONS,item.icon)}</select></div><div class="field"><label>對齊</label><select data-footer-field="alignment">${optionRows(ALIGNMENTS,item.alignment)}</select></div></div><div class="field"><label>超連結（選填）</label><input data-footer-field="url" value="${esc(item.url)}" placeholder="https://…、mailto:… 或相對路徑"></div><label class="switch"><input type="checkbox" data-footer-field="new_tab" ${item.new_tab?'checked':''}>在新分頁開啟</label></div>`;}
  function renderFooter(){const root=document.querySelector('#footerSettingsPane');if(!root)return;const zones={left:[],center:[],right:[]};draft.footer.items.forEach(item=>zones[item.alignment].push(`<span class="footer-preview-item">${item.icon!=='none'?`<span class="tag">${esc(ICONS.find(x=>x[0]===item.icon)?.[1]||item.icon)}</span>`:''}${esc(item.text.zh||item.text.en||'未填文字')}</span>`));root.innerHTML=`<p class="muted">每個項目可設定文字、小圖標、超連結與靠左／置中／靠右。可使用 <code>{year}</code> 和 <code>{updated}</code>。</p><div class="actions"><button class="button primary" type="button" id="addFooterItem">新增頁尾項目</button><button class="button" type="button" id="resetFooterItems">恢復預設頁尾</button></div><div class="footer-admin-preview"><div>${zones.left.join('')}</div><div>${zones.center.join('')}</div><div>${zones.right.join('')}</div></div><div id="footerEditorRows">${draft.footer.items.map(footerRow).join('')||'<p class="muted">目前沒有頁尾項目。</p>'}</div>`;}
  function renderStatus(){const root=document.querySelector('#siteSettingsStatus');if(!root)return;const errors=validate();root.className='notice '+(errors.length?'error':dirty()?'success':'');root.innerHTML=errors.length?`<strong>不能送出：</strong>${errors.map(esc).join('；')}`:dirty()?'SEO／OG 或頁尾已有修改，會和本次批次一起送出。':'SEO／OG 與頁尾尚未修改。';}
  function render(){if(!ready)return;document.querySelectorAll('[data-site-settings-section]').forEach(button=>button.classList.toggle('active',button.dataset.siteSettingsSection===currentSection));const seo=document.querySelector('#seoSettingsPane'),footer=document.querySelector('#footerSettingsPane');if(seo)seo.hidden=currentSection!=='seo';if(footer)footer.hidden=currentSection!=='footer';renderSeo();renderFooter();renderStatus();}
  function updatePath(target,path,value){const parts=path.split('.');let obj=target;while(parts.length>1)obj=obj[parts.shift()];obj[parts[0]]=value;}
  function installPanel(){
    const tabs=document.querySelector('#tabs'),dictionary=document.querySelector('[data-tab="dictionary"]');if(tabs&&!document.querySelector('[data-tab="siteSettings"]'))dictionary?.insertAdjacentHTML('afterend','<button class="tab" data-tab="siteSettings">網站設定</button>');
    const dictionaryTab=document.querySelector('#dictionaryTab');if(dictionaryTab&&!document.querySelector('#siteSettingsTab'))dictionaryTab.insertAdjacentHTML('afterend',`<div id="siteSettingsTab" hidden><div class="site-settings-tabs"><button class="button active" type="button" data-site-settings-section="seo">SEO／OG</button><button class="button" type="button" data-site-settings-section="footer">頁尾</button></div><div id="siteSettingsStatus" class="notice"></div><div id="seoSettingsPane"></div><div id="footerSettingsPane" hidden></div><div class="actions"><button class="button" type="button" id="resetSiteSettings">放棄網站設定修改</button></div></div>`);
    document.querySelector('#siteSettingsTab')?.addEventListener('click',event=>{const section=event.target.closest('[data-site-settings-section]');if(section){currentSection=section.dataset.siteSettingsSection;render();return;}const row=event.target.closest('[data-footer-index]');if(event.target.id==='addFooterItem'){draft.footer.items.push({id:`footer-item-${draft.footer.items.length+1}`,text:{en:'',zh:''},url:'',icon:'none',alignment:'center',new_tab:false});save();return;}if(event.target.id==='resetFooterItems'){draft.footer=defaultSettings(siteDataCache).footer;save();return;}if(event.target.id==='resetSiteSettings'){if(confirm('放棄尚未送出的 SEO／OG 與頁尾修改？')){draft=copy(remote);save();}return;}if(row){const index=Number(row.dataset.footerIndex);if(event.target.closest('[data-footer-remove]')){draft.footer.items.splice(index,1);save();return;}const move=event.target.closest('[data-footer-move]')?.dataset.footerMove;if(move){const next=move==='up'?index-1:index+1;if(next>=0&&next<draft.footer.items.length){[draft.footer.items[index],draft.footer.items[next]]=[draft.footer.items[next],draft.footer.items[index]];save();}}}});
    document.querySelector('#siteSettingsTab')?.addEventListener('input',event=>{const target=event.target;if(target.id==='seoPageSelect'){currentPage=target.value;render();return;}if(target.matches('[data-seo-global]')){draft.seo[target.dataset.seoGlobal]=target.value;save(false);return;}if(target.matches('[data-seo-site-name]')){draft.seo.site_name[target.dataset.seoSiteName]=target.value;save(false);return;}if(target.matches('[data-page-field]')){updatePath(draft.seo.pages[currentPage],target.dataset.pageField,target.value);save(false);return;}const row=target.closest('[data-footer-index]');if(row&&target.matches('[data-footer-field]')){const item=draft.footer.items[Number(row.dataset.footerIndex)],field=target.dataset.footerField;updatePath(item,field,target.type==='checkbox'?target.checked:target.value);save(false);}});
    document.querySelector('#siteSettingsTab')?.addEventListener('change',event=>{if(event.target.matches('select,[type="checkbox"]'))save();});
  }
  function installStyles(){const style=document.createElement('style');style.id='site-settings-admin-styles';style.textContent=`.site-settings-tabs,.database-type-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}.site-settings-card,.site-settings-global,.footer-editor-row{border:1px solid #dfd3ca;border-radius:12px;padding:13px;margin:10px 0;background:#fcfaf8}.footer-editor-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.footer-admin-preview{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:14px 0;padding:14px;border-radius:12px;background:#302824;color:#f4e8e1}.footer-admin-preview>div{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.footer-admin-preview>div:nth-child(2){justify-content:center}.footer-admin-preview>div:nth-child(3){justify-content:flex-end}.footer-preview-item{display:inline-flex;gap:5px;align-items:center}@media(max-width:700px){.footer-admin-preview{grid-template-columns:1fr}.footer-admin-preview>div{justify-content:flex-start!important}}`;document.head.append(style);}
  window.siteSettingsDirty=dirty;window.siteSettingsOperation=operation;window.siteSettingsPreviewHtml=previewHtml;window.siteSettingsHistoryPreviewHtml=h=>previewHtml({before:h.before,after:h.after});window.validateSiteSettingsDraft=validate;window.clearSiteSettingsDraft=clearDraft;window.renderSiteSettings=render;
  installStyles();installPanel();
  fetch('../content/site.json',{cache:'no-store'}).then(r=>r.json()).then(siteData=>{siteDataCache=siteData;remote=normalize({seo:siteData.settings?.seo,footer:siteData.settings?.footer},siteData);draft=loadSaved(remote);ready=true;render();if(typeof site!=='undefined'&&site&&typeof renderPreview==='function')renderPreview(false);}).catch(error=>{const status=document.querySelector('#siteSettingsStatus');if(status){status.className='notice error';status.textContent='讀取 SEO／頁尾設定失敗：'+error;}});
})();
