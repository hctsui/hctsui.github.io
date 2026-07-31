/* Editable footer, SEO/Open Graph, analytics providers, and 404 page. */
(function installSiteSettingsManager(){
  const DRAFT_KEY='hctsui-site-settings-draft';
  const PAGE_LABELS={home:'首頁',cv:'履歷',publications:'論文',activities:'學術活動',teaching:'教學',contact:'聯絡表單'};
  const SECTION_LABELS={footer:'頁尾',seo:'SEO／OG',analytics:'流量統計',errorPage:'404 頁面',contactForm:'聯絡表單'};
  const ICONS=[['none','無圖標'],['copyright','版權'],['link','連結'],['location','地點'],['book','書籍'],['calendar','日曆'],['other','其他']];
  const LEGACY_ICON_LABELS={email:'Email',github:'GitHub',orcid:'ORCID'};
  const ALIGNMENTS=[['left','靠左'],['center','置中'],['right','靠右']];
  const COLOR_FIELDS=[
    ['background','頁面背景'],['surface','內容卡片'],['accent','強調色'],['text','主要文字'],['muted','說明文字'],['button','按鈕'],['button_text','按鈕文字'],
  ];
  const SEO_PAGE_FIELDS=[
    ['title.en','英文 SEO 標題'],['title.zh','中文 SEO 標題'],['description.en','英文 Meta description'],['description.zh','中文 Meta description'],
    ['og_title.en','英文 OG 標題'],['og_title.zh','中文 OG 標題'],['og_description.en','英文 OG 描述'],['og_description.zh','中文 OG 描述'],['og_image','OG 圖片'],
  ];
  let remote=null,draft=null,ready=false,currentPage='home',currentSection='footer',currentContactPanel='form',siteDataCache={};

  const copy=value=>structuredClone(value);
  const own=(object,key)=>Object.prototype.hasOwnProperty.call(object||{},key);
  const text=(value,limit=500)=>String(value??'').trim().replace(/\s+/g,' ').slice(0,limit);
  const pair=(value,fallback={en:'',zh:''},limit=500)=>({
    en:own(value,'en')?text(value.en,limit):text(fallback.en,limit),
    zh:own(value,'zh')?text(value.zh,limit):text(fallback.zh,limit),
  });
  const hex=(value,fallback)=>/^#[0-9a-f]{6}$/i.test(String(value||'').trim())?String(value).trim().toLowerCase():fallback;
  function stable(value){
    if(Array.isArray(value))return value.map(stable);
    if(value&&typeof value==='object')return Object.keys(value).sort().reduce((out,key)=>(out[key]=stable(value[key]),out),{});
    return value;
  }
  const equal=(a,b)=>JSON.stringify(stable(a))===JSON.stringify(stable(b));
  function safeWebUrl(value,{relative=false,mailto=false}={}){
    const raw=String(value||'').trim();if(!raw)return '';
    if(mailto&&/^mailto:[^\s@]+@[^\s@]+$/i.test(raw))return raw;
    if(relative&&!/^[A-Za-z][A-Za-z0-9+.-]*:/.test(raw)&&!raw.startsWith('//')&&!/\s/.test(raw))return raw;
    try{const url=new URL(raw);return ['http:','https:'].includes(url.protocol)&&!/\s/.test(raw)?raw:'';}catch{return '';}
  }
  function pageDefaults(siteData){
    const defaults={
      home:{title:{en:'Hung-Chun Tsui | Mathematics',zh:'崔鴻竣｜數學'},description:{en:'Academic website of Hung-Chun Tsui, PhD student in mathematics at National Tsing Hua University.',zh:'崔鴻竣的學術個人網站，收錄研究、論文、學術活動與教學經歷。'}},
      cv:{title:{en:'Curriculum Vitae | Hung-Chun Tsui',zh:'履歷｜崔鴻竣'},description:{en:'Curriculum vitae of Hung-Chun Tsui.',zh:'崔鴻竣的學術履歷。'}},
      publications:{title:{en:'Publications | Hung-Chun Tsui',zh:'論文｜崔鴻竣'},description:{en:'Publications and preprints by Hung-Chun Tsui.',zh:'崔鴻竣的論文與預印本。'}},
      activities:{title:{en:'Activities | Hung-Chun Tsui',zh:'學術活動｜崔鴻竣'},description:{en:'Academic talks, visits, conferences, and workshops of Hung-Chun Tsui.',zh:'崔鴻竣的學術報告、訪問、會議與工作坊紀錄。'}},
      teaching:{title:{en:'Teaching | Hung-Chun Tsui',zh:'教學｜崔鴻竣'},description:{en:'Teaching experience of Hung-Chun Tsui.',zh:'崔鴻竣的教學與課程助教經歷。'}},
      contact:{title:{en:'Contact Form | Hung-Chun Tsui',zh:'聯絡表單｜崔鴻竣'},description:{en:'Contact Hung-Chun Tsui for academic invitations, research correspondence, or other inquiries.',zh:'透過聯絡表單與崔鴻竣進行學術邀請、研究交流或其他聯繫。'}},
    };
    for(const page of siteData?.settings?.pages||[]){
      if(page.id==='home')continue;
      if(!defaults[page.id])defaults[page.id]={title:{en:'',zh:''},description:{en:'',zh:''}};
      for(const lang of ['en','zh']){
        const title=page.header?.title?.[lang]||page.name?.[lang]||page.id,intro=page.header?.intro?.[lang]||'';
        defaults[page.id].title[lang]=lang==='en'?`${title} | Hung-Chun Tsui`:`${title}｜崔鴻竣`;
        defaults[page.id].description[lang]=intro;
      }
    }
    return defaults;
  }
  function defaultSettings(siteData){
    const defaults=pageDefaults(siteData),pages={};
    Object.entries(defaults).forEach(([id,value])=>pages[id]={title:copy(value.title),description:copy(value.description),og_title:{en:'',zh:''},og_description:{en:'',zh:''},og_image:''});
    return {
      footer:{schema_version:2,items:[
        {id:'copyright',text:{en:'{year} Hung-Chun Tsui',zh:'{year} Hung-Chun Tsui'},url:'',icon:'copyright',custom_icon:'',alignment:'left',new_tab:false},
        {id:'last-updated',text:{en:'Last updated: {updated}',zh:'最後更新：{updated}'},url:'',icon:'none',custom_icon:'',alignment:'right',new_tab:false},
      ]},
      seo:{schema_version:1,base_url:'https://hctsui.github.io',site_name:{en:'Hung-Chun Tsui',zh:'崔鴻竣'},default_image:'assets/photo-1440.webp',pages},
      analytics:{schema_version:2,enabled:false,provider:'cloudflare',cloudflare_token:'',google_measurement_id:''},
      contact_form:{schema_version:2,enabled:false,mode:'email_only',web3forms_access_key:'',worker_url:'',turnstile_site_key:'',email_subject:'[hctsui.github.io] New contact message',title:{en:'Send a message',zh:'傳送訊息'},intro:{en:'For academic invitations or research correspondence, you may use this form.',zh:'如有學術邀請或研究交流，可使用此表單聯絡。'},name_label:{en:'Name',zh:'姓名'},email_label:{en:'Email',zh:'電子郵件'},subject_label:{en:'Subject',zh:'主旨'},message_label:{en:'Message',zh:'訊息'},submit_label:{en:'Send message',zh:'送出訊息'},success_message:{en:'Thank you. Your message has been sent.',zh:'謝謝，訊息已送出。'},privacy_note:{en:'Your message will be delivered privately by Web3Forms.',zh:'完整訊息只會透過 Web3Forms 私下寄送，不會存入公開網站資料。'},page_design:{eyebrow:{en:'Contact',zh:'聯絡'},title:{en:'Contact Form',zh:'聯絡表單'},description:{en:'Use this form for academic invitations, research correspondence, or other inquiries.',zh:'如有學術邀請、研究交流或其他詢問，可使用此表單聯絡。'},show_navigation:true,show_footer:true,colors:{background:'#f7f3ed',surface:'#ffffff',accent:'#8d493d',text:'#2d2926',muted:'#6c625c',button:'#8d493d',button_text:'#ffffff'}}},
      error_page:{schema_version:1,
        eyebrow:{en:'Page not found',zh:'找不到頁面'},title:{en:'This page does not exist.',zh:'這個頁面不存在。'},
        description:{en:'The address may be outdated or mistyped. You can return to the homepage or continue browsing the website.',zh:'網址可能已更新或輸入有誤。你可以返回首頁，或繼續瀏覽網站內容。'},
        home_label:{en:'Return home',zh:'返回首頁'},secondary_label:{en:'View publications',zh:'查看論文'},secondary_url:{en:'publications.html',zh:'zh/publications.html'},
        show_navigation:true,show_footer:true,auto_redirect:{enabled:false,seconds:8},
        colors:{background:'#f7f3ed',surface:'#ffffff',accent:'#8d493d',text:'#2d2926',muted:'#6c625c',button:'#2d2926',button_text:'#ffffff'},
      },
    };
  }
  function normalize(value,siteData){
    const defaults=defaultSettings(siteData),source=value&&typeof value==='object'?value:{};
    const seoSource=source.seo&&typeof source.seo==='object'?source.seo:{},pagesSource=seoSource.pages&&typeof seoSource.pages==='object'?seoSource.pages:{},pages={};
    const ids=[...new Set([...Object.keys(defaults.seo.pages),...Object.keys(pagesSource)])];
    for(const id of ids){
      const fallback=defaults.seo.pages[id]||{title:{en:id,zh:id},description:{en:'',zh:''},og_title:{en:'',zh:''},og_description:{en:'',zh:''},og_image:''},raw=pagesSource[id]||{};
      pages[id]={title:pair(raw.title,fallback.title,180),description:pair(raw.description,fallback.description,500),og_title:pair(raw.og_title,fallback.og_title,180),og_description:pair(raw.og_description,fallback.og_description,500),og_image:safeWebUrl(raw.og_image,{relative:true})};
    }
    const footerRows=Array.isArray(source.footer?.items)?source.footer.items:defaults.footer.items,used=new Set(),items=[];
    footerRows.forEach((raw,index)=>{
      let base=text(raw?.id||`footer-item-${index+1}`,80).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||`footer-item-${index+1}`,id=base,n=2;
      while(used.has(id))id=`${base}-${n++}`;used.add(id);
      const icon=[...ICONS.map(x=>x[0]),...Object.keys(LEGACY_ICON_LABELS)].includes(raw?.icon)?raw.icon:'none';
      items.push({id,text:pair(raw?.text,{en:'',zh:''},300),url:safeWebUrl(raw?.url,{relative:true,mailto:true}),icon,custom_icon:safeWebUrl(raw?.custom_icon,{relative:true}),alignment:ALIGNMENTS.some(x=>x[0]===raw?.alignment)?raw.alignment:'center',new_tab:Boolean(raw?.new_tab)});
    });
    const analyticsSource=source.analytics&&typeof source.analytics==='object'?source.analytics:{};
    const contactSource=source.contact_form&&typeof source.contact_form==='object'?source.contact_form:{};
    const contactPageSource=contactSource.page_design&&typeof contactSource.page_design==='object'?contactSource.page_design:{},contactPageColors=contactPageSource.colors&&typeof contactPageSource.colors==='object'?contactPageSource.colors:{};
    const errorSource=source.error_page&&typeof source.error_page==='object'?source.error_page:{},redirect=errorSource.auto_redirect&&typeof errorSource.auto_redirect==='object'?errorSource.auto_redirect:{},colors=errorSource.colors&&typeof errorSource.colors==='object'?errorSource.colors:{},seconds=Math.max(1,Math.min(300,parseInt(redirect.seconds??defaults.error_page.auto_redirect.seconds,10)||defaults.error_page.auto_redirect.seconds));
    return {
      footer:{schema_version:2,items},
      seo:{schema_version:1,base_url:safeWebUrl(own(seoSource,'base_url')?seoSource.base_url:defaults.seo.base_url)||defaults.seo.base_url,site_name:pair(seoSource.site_name,defaults.seo.site_name,120),default_image:safeWebUrl(own(seoSource,'default_image')?seoSource.default_image:defaults.seo.default_image,{relative:true})||defaults.seo.default_image,pages},
      analytics:{schema_version:2,enabled:Boolean(analyticsSource.enabled),provider:['cloudflare','google'].includes(String(analyticsSource.provider||'cloudflare').toLowerCase())?String(analyticsSource.provider||'cloudflare').toLowerCase():'cloudflare',cloudflare_token:text(own(analyticsSource,'cloudflare_token')?analyticsSource.cloudflare_token:analyticsSource.token,80),google_measurement_id:text(analyticsSource.google_measurement_id,40).toUpperCase()},
      contact_form:{schema_version:2,enabled:Boolean(contactSource.enabled),mode:['email_only','worker'].includes(String(contactSource.mode||'email_only'))?String(contactSource.mode||'email_only'):'email_only',web3forms_access_key:text(contactSource.web3forms_access_key,80),worker_url:safeWebUrl(contactSource.worker_url),turnstile_site_key:text(contactSource.turnstile_site_key,120),email_subject:text(contactSource.email_subject||defaults.contact_form.email_subject,160),title:pair(contactSource.title,defaults.contact_form.title,160),intro:pair(contactSource.intro,defaults.contact_form.intro,500),name_label:pair(contactSource.name_label,defaults.contact_form.name_label,80),email_label:pair(contactSource.email_label,defaults.contact_form.email_label,80),subject_label:pair(contactSource.subject_label,defaults.contact_form.subject_label,80),message_label:pair(contactSource.message_label,defaults.contact_form.message_label,80),submit_label:pair(contactSource.submit_label,defaults.contact_form.submit_label,100),success_message:pair(contactSource.success_message,defaults.contact_form.success_message,300),privacy_note:pair(contactSource.privacy_note,defaults.contact_form.privacy_note,300),page_design:{eyebrow:pair(contactPageSource.eyebrow,defaults.contact_form.page_design.eyebrow,120),title:pair(contactPageSource.title,defaults.contact_form.page_design.title,180),description:pair(contactPageSource.description,defaults.contact_form.page_design.description,600),show_navigation:own(contactPageSource,'show_navigation')?Boolean(contactPageSource.show_navigation):true,show_footer:own(contactPageSource,'show_footer')?Boolean(contactPageSource.show_footer):true,colors:Object.fromEntries(Object.entries(defaults.contact_form.page_design.colors).map(([key,fallback])=>[key,hex(contactPageColors[key],fallback)]))}},
      error_page:{schema_version:1,eyebrow:pair(errorSource.eyebrow,defaults.error_page.eyebrow,120),title:pair(errorSource.title,defaults.error_page.title,180),description:pair(errorSource.description,defaults.error_page.description,600),home_label:pair(errorSource.home_label,defaults.error_page.home_label,100),secondary_label:pair(errorSource.secondary_label,defaults.error_page.secondary_label,100),secondary_url:{en:safeWebUrl(errorSource.secondary_url?.en,{relative:true})||defaults.error_page.secondary_url.en,zh:safeWebUrl(errorSource.secondary_url?.zh,{relative:true})||defaults.error_page.secondary_url.zh},show_navigation:own(errorSource,'show_navigation')?Boolean(errorSource.show_navigation):true,show_footer:own(errorSource,'show_footer')?Boolean(errorSource.show_footer):true,auto_redirect:{enabled:Boolean(redirect.enabled),seconds},colors:Object.fromEntries(Object.entries(defaults.error_page.colors).map(([key,fallback])=>[key,hex(colors[key],fallback)]))},
    };
  }
  const normalizedRemote=()=>normalize(remote,siteDataCache);
  const normalizedDraft=()=>normalize(draft,siteDataCache);
  function validate(){
    const errors=[];if(!ready)return errors;const value=normalizedDraft();
    if(!safeWebUrl(value.seo.base_url))errors.push('網站基準網址必須是完整的 http 或 https 網址');
    if(value.seo.default_image&&!safeWebUrl(value.seo.default_image,{relative:true}))errors.push('預設分享圖片必須是相對路徑或 http／https 網址');
    for(const [id,page] of Object.entries(value.seo.pages))for(const lang of ['en','zh']){
      if(!page.title[lang])errors.push(`${PAGE_LABELS[id]||id}：${lang==='en'?'英文':'中文'} SEO 標題不可空白`);
      if(page.title[lang].length>180)errors.push(`${PAGE_LABELS[id]||id}：SEO 標題過長`);
      if(page.description[lang].length>500)errors.push(`${PAGE_LABELS[id]||id}：SEO 描述過長`);
    }
    if(value.footer.items.length>30)errors.push('頁尾最多 30 個項目');
    value.footer.items.forEach((item,index)=>{
      if(!item.text.en&&!item.text.zh)errors.push(`頁尾第 ${index+1} 項需要英文或中文文字`);
      if(item.url&&!safeWebUrl(item.url,{relative:true,mailto:true}))errors.push(`頁尾第 ${index+1} 項網址格式不正確`);
      if(item.icon==='other'&&!item.custom_icon)errors.push(`頁尾第 ${index+1} 項選擇「其他」時必須填圖標檔案路徑`);
    });
    if(value.analytics.enabled&&value.analytics.provider==='cloudflare'&&!/^[0-9a-f]{32}$/i.test(value.analytics.cloudflare_token))errors.push('Cloudflare Site Token 必須是 32 個十六進位字元');
    if(value.analytics.enabled&&value.analytics.provider==='google'&&!/^G-[A-Z0-9]{4,20}$/i.test(value.analytics.google_measurement_id))errors.push('Google Analytics Measurement ID 必須是 G- 開頭的代碼');
    if(value.contact_form.enabled&&!value.contact_form.email_subject)errors.push('聯絡表單啟用時需要固定通知信主旨');
    if(value.contact_form.enabled&&value.contact_form.mode==='email_only'&&!/^[0-9a-f-]{20,80}$/i.test(value.contact_form.web3forms_access_key))errors.push('聯絡表單已啟用 Email 模式：請填入有效的 Web3Forms Access Key，或先關閉聯絡表單');
    if(value.contact_form.enabled&&value.contact_form.mode==='worker'&&!safeWebUrl(value.contact_form.worker_url))errors.push('聯絡表單已啟用 Worker 通知模式：請填入完整的 Cloudflare Worker URL，或改選 Web3Forms Email／先關閉聯絡表單');
    for(const field of ['eyebrow','title','description'])for(const lang of ['en','zh'])if(!value.contact_form.page_design[field][lang])errors.push(`聯絡表單頁面的${lang==='en'?'英文':'中文'}欄位不可空白`);
    for(const field of ['eyebrow','title','description','home_label'])for(const lang of ['en','zh'])if(!value.error_page[field][lang])errors.push(`404 頁面的${lang==='en'?'英文':'中文'}欄位不可空白`);
    return [...new Set(errors)];
  }
  function dirty(){return ready&&!equal(normalizedRemote(),normalizedDraft());}
  function loadSaved(base){
    try{const saved=JSON.parse(localStorage.getItem(DRAFT_KEY)||'null');if(saved?.base&&saved?.data&&equal(normalize(saved.base,siteDataCache),normalize(base,siteDataCache)))return copy(saved.data);if(saved)localStorage.removeItem(DRAFT_KEY);}catch{localStorage.removeItem(DRAFT_KEY);}return copy(base);
  }
  function save(rerender=true){
    if(dirty())localStorage.setItem(DRAFT_KEY,JSON.stringify({base:normalizedRemote(),data:draft}));else localStorage.removeItem(DRAFT_KEY);
    if(rerender)render();else renderStatus();
    if(typeof site!=='undefined'&&site&&typeof renderPreview==='function')renderPreview(false);
  }
  function operation(){return dirty()?{op:'site_settings',before:copy(normalizedRemote()),after:copy(normalizedDraft())}:null;}
  function clearDraft(reload=false){localStorage.removeItem(DRAFT_KEY);draft=copy(remote);if(reload)render();}
  function valueAt(object,path){return path.split('.').reduce((value,key)=>value?.[key],object);}
  function displayValue(value){if(typeof value==='boolean')return value?'開啟':'關閉';return String(value??'')||'（空白）';}
  function changeItem(label,before,after){return `<li><strong>${esc(label)}</strong><span class="settings-old">${esc(displayValue(before))}</span><span class="settings-arrow">→</span><span class="settings-new">${esc(displayValue(after))}</span></li>`;}
  function changeSections(before,after){
    const sections=[];
    const footer=[];
    const beforeById=new Map(before.footer.items.map(item=>[item.id,item])),afterById=new Map(after.footer.items.map(item=>[item.id,item]));
    for(const item of after.footer.items)if(!beforeById.has(item.id))footer.push(`<li><strong>新增頁尾項目</strong><span class="settings-new">${esc(item.text.zh||item.text.en||item.id)}</span></li>`);
    for(const item of before.footer.items)if(!afterById.has(item.id))footer.push(`<li><strong>刪除頁尾項目</strong><span class="settings-old">${esc(item.text.zh||item.text.en||item.id)}</span></li>`);
    for(const item of after.footer.items){const old=beforeById.get(item.id);if(!old)continue;for(const [path,label] of [['text.en','英文文字'],['text.zh','中文文字'],['icon','小圖標'],['custom_icon','自訂圖標路徑'],['url','超連結'],['alignment','對齊'],['new_tab','新分頁']]){const a=valueAt(old,path),b=valueAt(item,path);if(!equal(a,b))footer.push(changeItem(`${item.text.zh||item.text.en||item.id}：${label}`,a,b));}}
    const beforeOrder=before.footer.items.map(x=>x.id),afterOrder=after.footer.items.map(x=>x.id);if(!equal(beforeOrder,afterOrder)&&beforeOrder.length===afterOrder.length&&beforeOrder.every(id=>afterOrder.includes(id)))footer.push('<li><strong>頁尾項目順序</strong><span class="settings-new">已重新排列</span></li>');
    if(footer.length)sections.push(['頁尾',footer]);
    const seo=[];
    for(const [path,label] of [['base_url','基準網址'],['site_name.en','英文網站名稱'],['site_name.zh','中文網站名稱'],['default_image','預設分享圖片']]){const a=valueAt(before.seo,path),b=valueAt(after.seo,path);if(!equal(a,b))seo.push(changeItem(label,a,b));}
    for(const [id,page] of Object.entries(after.seo.pages)){const old=before.seo.pages[id]||{};for(const [path,label] of SEO_PAGE_FIELDS){const a=valueAt(old,path),b=valueAt(page,path);if(!equal(a,b))seo.push(changeItem(`${PAGE_LABELS[id]||id}：${label}`,a,b));}}
    if(seo.length)sections.push(['SEO／OG',seo]);
    const analytics=[];
    if(before.analytics.enabled!==after.analytics.enabled)analytics.push(changeItem('啟用流量統計',before.analytics.enabled,after.analytics.enabled));
    if(before.analytics.provider!==after.analytics.provider)analytics.push(changeItem('統計提供者',before.analytics.provider==='google'?'Google Analytics 4':'Cloudflare Web Analytics',after.analytics.provider==='google'?'Google Analytics 4':'Cloudflare Web Analytics'));
    if(before.analytics.cloudflare_token!==after.analytics.cloudflare_token)analytics.push('<li><strong>Cloudflare Site Token</strong><span class="settings-new">已更新（內容隱藏）</span></li>');
    if(before.analytics.google_measurement_id!==after.analytics.google_measurement_id)analytics.push(changeItem('Google Measurement ID',before.analytics.google_measurement_id,after.analytics.google_measurement_id));
    if(analytics.length)sections.push(['流量統計',analytics]);
    const contact=[];
    for(const [path,label] of [['enabled','啟用聯絡表單'],['mode','傳送模式'],['email_subject','通知信固定主旨'],['worker_url','Worker URL'],['turnstile_site_key','Turnstile Site Key'],['title.en','表單英文標題'],['title.zh','表單中文標題'],['intro.en','表單英文說明'],['intro.zh','表單中文說明'],['submit_label.en','英文送出按鈕'],['submit_label.zh','中文送出按鈕'],['success_message.en','英文成功訊息'],['success_message.zh','中文成功訊息'],['privacy_note.en','英文隱私說明'],['privacy_note.zh','中文隱私說明'],['page_design.eyebrow.en','頁面英文小標'],['page_design.eyebrow.zh','頁面中文小標'],['page_design.title.en','頁面英文標題'],['page_design.title.zh','頁面中文標題'],['page_design.description.en','頁面英文說明'],['page_design.description.zh','頁面中文說明'],['page_design.show_navigation','頁面顯示導覽列'],['page_design.show_footer','頁面顯示頁尾']]){const a=valueAt(before.contact_form,path),b=valueAt(after.contact_form,path);if(!equal(a,b))contact.push(changeItem(label,a,b));}
    for(const [key,label] of COLOR_FIELDS){const a=before.contact_form.page_design.colors[key],b=after.contact_form.page_design.colors[key];if(a!==b)contact.push(changeItem(`聯絡表單頁面顏色：${label}`,a,b));}
    if(before.contact_form.web3forms_access_key!==after.contact_form.web3forms_access_key)contact.push('<li><strong>Web3Forms Access Key</strong><span class="settings-new">已更新（內容隱藏）</span></li>');
    if(contact.length)sections.push(['聯絡表單',contact]);
    const error=[];
    for(const [path,label] of [
      ['eyebrow.en','英文小標'],['eyebrow.zh','中文小標'],['title.en','英文標題'],['title.zh','中文標題'],['description.en','英文說明'],['description.zh','中文說明'],['home_label.en','英文首頁按鈕'],['home_label.zh','中文首頁按鈕'],['secondary_label.en','英文次要按鈕'],['secondary_label.zh','中文次要按鈕'],['secondary_url.en','英文次要網址'],['secondary_url.zh','中文次要網址'],['show_navigation','顯示導覽列'],['show_footer','顯示頁尾'],['auto_redirect.enabled','自動返回首頁'],['auto_redirect.seconds','自動返回秒數'],
    ]){const a=valueAt(before.error_page,path),b=valueAt(after.error_page,path);if(!equal(a,b))error.push(changeItem(label,a,b));}
    for(const [key,label] of COLOR_FIELDS){const a=before.error_page.colors[key],b=after.error_page.colors[key];if(a!==b)error.push(changeItem(`顏色：${label}`,a,b));}
    if(error.length)sections.push(['404 頁面',error]);
    return sections;
  }
  function previewHtml(op){
    const before=normalize(op?.before,siteDataCache),after=normalize(op?.after,siteDataCache),sections=changeSections(before,after),total=sections.reduce((n,section)=>n+section[1].length,0);
    if(!sections.length)return '';
    return `<details class="diff settings-diff" open><summary><strong>網站設定：${total} 項實際變更</strong></summary>${sections.map(([title,items])=>`<section class="settings-diff-section"><h4>${esc(title)}</h4><ul>${items.join('')}</ul></section>`).join('')}</details>`;
  }
  function optionRows(options,selected){
    const rows=[...options];if(LEGACY_ICON_LABELS[selected]&&!rows.some(x=>x[0]===selected))rows.push([selected,`${LEGACY_ICON_LABELS[selected]}（舊設定）`]);
    return rows.map(([value,label])=>`<option value="${value}" ${value===selected?'selected':''}>${label}</option>`).join('');
  }
  function renderSeo(){
    const page=draft.seo.pages[currentPage]||draft.seo.pages.home,root=document.querySelector('#seoSettingsPane');if(!root)return;
    root.innerHTML=`<div class="settings-intro"><strong>SEO／OG</strong><span>管理搜尋結果標題、描述、分享圖片與社群預覽。留白的 OG 欄位會沿用 SEO 欄位。</span></div><div class="site-settings-card"><h3>全站設定</h3><div class="field"><label>網站基準網址</label><input data-seo-global="base_url" value="${esc(draft.seo.base_url)}" placeholder="https://hctsui.github.io"></div><div class="pair-grid"><div class="field"><label>網站名稱（英文）</label><input data-seo-site-name="en" value="${esc(draft.seo.site_name.en)}"></div><div class="field"><label>網站名稱（中文）</label><input data-seo-site-name="zh" value="${esc(draft.seo.site_name.zh)}"></div></div><div class="field"><label>預設 OG 分享圖片</label><input data-seo-global="default_image" value="${esc(draft.seo.default_image)}" placeholder="assets/photo-1440.webp"><p class="field-hint">可使用網站內相對路徑或完整 https 網址。</p></div></div><div class="field settings-page-select"><label>編輯頁面</label><select id="seoPageSelect">${Object.keys(draft.seo.pages).map(id=>`<option value="${esc(id)}" ${id===currentPage?'selected':''}>${esc(PAGE_LABELS[id]||id)}</option>`).join('')}</select></div><div class="site-settings-card"><h3>${esc(PAGE_LABELS[currentPage]||currentPage)}</h3><div class="pair-grid"><div class="field"><label>SEO 標題（英文）</label><input data-page-field="title.en" value="${esc(page.title.en)}"></div><div class="field"><label>SEO 標題（中文）</label><input data-page-field="title.zh" value="${esc(page.title.zh)}"></div></div><div class="pair-grid"><div class="field"><label>Meta description（英文）</label><textarea data-page-field="description.en">${esc(page.description.en)}</textarea></div><div class="field"><label>Meta description（中文）</label><textarea data-page-field="description.zh">${esc(page.description.zh)}</textarea></div></div><div class="pair-grid"><div class="field"><label>OG 標題（英文，留白沿用 SEO）</label><input data-page-field="og_title.en" value="${esc(page.og_title.en)}"></div><div class="field"><label>OG 標題（中文，留白沿用 SEO）</label><input data-page-field="og_title.zh" value="${esc(page.og_title.zh)}"></div></div><div class="pair-grid"><div class="field"><label>OG 描述（英文，留白沿用 Meta）</label><textarea data-page-field="og_description.en">${esc(page.og_description.en)}</textarea></div><div class="field"><label>OG 描述（中文，留白沿用 Meta）</label><textarea data-page-field="og_description.zh">${esc(page.og_description.zh)}</textarea></div></div><div class="field"><label>本頁 OG 圖片（留白沿用預設）</label><input data-page-field="og_image" value="${esc(page.og_image)}"></div></div>`;
  }
  function iconPreview(item){
    if(item.icon==='none')return '';
    if(item.icon==='other')return item.custom_icon?`<img src="${esc(item.custom_icon)}" alt="">`:'<span class="footer-preview-icon">?</span>';
    return `<span class="footer-preview-icon">${esc(ICONS.find(x=>x[0]===item.icon)?.[1]||LEGACY_ICON_LABELS[item.icon]||item.icon)}</span>`;
  }
  function footerPreviewLanguage(lang){
    const zones={left:[],center:[],right:[]};
    draft.footer.items.forEach(item=>{const label=(item.text[lang]||item.text.en||item.text.zh||'未填文字').replaceAll('{year}',String(new Date().getFullYear())).replaceAll('{updated}','2026/8/1');zones[item.alignment].push(`<span class="footer-preview-item">${iconPreview(item)}<span>${esc(label)}</span></span>`);});
    return `<div class="footer-preview-language"><div class="footer-preview-language-label">${lang==='en'?'English footer':'中文頁尾'}</div><div class="footer-preview-zones"><div>${zones.left.join('')}</div><div>${zones.center.join('')}</div><div>${zones.right.join('')}</div></div></div>`;
  }
  function footerRow(item,index){
    return `<div class="footer-editor-row" data-footer-index="${index}"><div class="footer-editor-head"><strong>頁尾項目 ${index+1}</strong><div class="actions"><button class="button" type="button" data-footer-move="up" ${index===0?'disabled':''}>上移</button><button class="button" type="button" data-footer-move="down" ${index===draft.footer.items.length-1?'disabled':''}>下移</button><button class="button danger" type="button" data-footer-remove>刪除</button></div></div><div class="pair-grid"><div class="field"><label>文字（英文）</label><input data-footer-field="text.en" value="${esc(item.text.en)}"></div><div class="field"><label>文字（中文）</label><input data-footer-field="text.zh" value="${esc(item.text.zh)}"></div></div><div class="pair-grid"><div class="field"><label>小圖標</label><select data-footer-field="icon">${optionRows(ICONS,item.icon)}</select></div><div class="field"><label>對齊</label><select data-footer-field="alignment">${optionRows(ALIGNMENTS,item.alignment)}</select></div></div>${item.icon==='other'?`<div class="field custom-icon-field"><label>其他圖標檔案路徑</label><input data-footer-field="custom_icon" value="${esc(item.custom_icon)}" placeholder="assets/icons/my-icon.svg"><p class="field-hint">請先把 SVG、PNG、WebP 等圖檔放進 repository，再填相對路徑；也可填完整 https 網址。</p></div>`:''}<div class="field"><label>超連結（選填）</label><input data-footer-field="url" value="${esc(item.url)}" placeholder="https://…、mailto:… 或相對路徑"></div><label class="switch"><input type="checkbox" data-footer-field="new_tab" ${item.new_tab?'checked':''}>在新分頁開啟</label></div>`;
  }
  function renderFooter(){
    const root=document.querySelector('#footerSettingsPane');if(!root)return;
    root.innerHTML=`<div class="settings-intro"><strong>頁尾</strong><span>先在預覽確認中英文頁面的效果，再編輯文字、圖標、連結與位置。</span></div><div class="footer-admin-preview">${footerPreviewLanguage('en')}${footerPreviewLanguage('zh')}</div><div class="settings-toolbar"><button class="button primary" type="button" id="addFooterItem">新增頁尾項目</button><button class="button" type="button" id="resetFooterItems">恢復預設頁尾</button></div><p class="field-hint">文字可使用 <code>{year}</code> 和 <code>{updated}</code>。三個位置會各自依項目順序排列。</p><div id="footerEditorRows">${draft.footer.items.map(footerRow).join('')||'<p class="muted">目前沒有頁尾項目。</p>'}</div>`;
  }
  function renderAnalytics(){
    const root=document.querySelector('#analyticsSettingsPane');if(!root)return;
    const provider=draft.analytics.provider==='google'?'google':'cloudflare';
    const providerName=provider==='google'?'Google Analytics 4':'Cloudflare Web Analytics';
    const readyForProvider=provider==='google'?/^G-[A-Z0-9]{4,20}$/i.test(draft.analytics.google_measurement_id):/^[0-9a-f]{32}$/i.test(draft.analytics.cloudflare_token);
    const providerFields=provider==='google'
      ? `<div class="field"><label>Google Analytics Measurement ID</label><input data-analytics-field="google_measurement_id" value="${esc(draft.analytics.google_measurement_id)}" autocomplete="off" spellcheck="false" placeholder="G-XXXXXXXXXX"><p class="field-hint">從 GA4 的網頁資料串流複製 Measurement ID。Google Analytics 的追蹤與隱私設定較複雜，啟用前請確認是否需要 cookie／consent 說明。</p></div><div class="analytics-actions"><a class="button" href="https://analytics.google.com/analytics/web/" target="_blank" rel="noopener">開啟 Google Analytics 儀表板</a></div>`
      : `<div class="field"><label>Cloudflare Site Token</label><input data-analytics-field="cloudflare_token" value="${esc(draft.analytics.cloudflare_token)}" autocomplete="off" spellcheck="false" placeholder="32 個十六進位字元"><p class="field-hint">在 Cloudflare Web Analytics 的 Manage site 複製 JavaScript snippet；只需貼上其中 <code>token</code> 的值，不要貼整段 script。</p></div><div class="analytics-actions"><a class="button" href="https://dash.cloudflare.com/" target="_blank" rel="noopener">開啟 Cloudflare 儀表板</a></div>`;
    root.innerHTML=`<div class="site-settings-card analytics-card"><label class="switch"><input type="checkbox" data-analytics-field="enabled" ${draft.analytics.enabled?'checked':''}>啟用流量統計</label><div class="field"><label>統計提供者</label><select data-analytics-field="provider"><option value="cloudflare" ${provider==='cloudflare'?'selected':''}>Cloudflare Web Analytics</option><option value="google" ${provider==='google'?'selected':''}>Google Analytics 4</option></select></div>${providerFields}<div class="analytics-status ${draft.analytics.enabled&&readyForProvider?'enabled':'disabled'}"><strong>${draft.analytics.enabled?`${providerName} ${readyForProvider?'已可送出':'尚未設定完成'}`:'目前關閉'}</strong><span>${draft.analytics.enabled?(readyForProvider?'送出後會在所有公開頁面載入對應追蹤碼。':'請先填寫有效的識別碼。'):'網站不會載入任何分析程式。'}</span></div></div>`;
  }
  function contactPanelButtons(){
    return `<div class="contact-settings-choices"><button class="contact-settings-choice ${currentContactPanel==='form'?'active':''}" type="button" data-contact-panel="form"><strong>表單設定</strong></button><button class="contact-settings-choice ${currentContactPanel==='design'?'active':''}" type="button" data-contact-panel="design"><strong>頁面設計</strong></button></div>`;
  }
  function renderContactFormSettings(c){
    const worker=c.mode==='worker';
    const workerMissing=c.enabled&&worker&&!safeWebUrl(c.worker_url),emailMissing=c.enabled&&!worker&&!/^[0-9a-f-]{20,80}$/i.test(c.web3forms_access_key);
    const delivery=worker
      ? `${workerMissing?'<div class="notice error contact-setup-warning"><strong>尚不能送出：</strong>請填入完整的 Cloudflare Worker URL；若還沒設定 Worker，請改選 Web3Forms Email 或先關閉聯絡表單。</div>':''}<div class="field ${workerMissing?'field-error':''}"><label>Cloudflare Worker URL${c.enabled?'（必填）':''}</label><input data-contact-field="worker_url" value="${esc(c.worker_url)}" placeholder="https://contact-bridge.example.workers.dev" ${c.enabled?'required':''} aria-invalid="${workerMissing?'true':'false'}"></div><div class="field"><label>Cloudflare Turnstile Site Key（建議）</label><input data-contact-field="turnstile_site_key" value="${esc(c.turnstile_site_key)}" autocomplete="off"></div>`
      : `${emailMissing?'<div class="notice error contact-setup-warning"><strong>尚不能送出：</strong>請填入 Web3Forms Access Key；若還沒申請，請先關閉聯絡表單。</div>':''}<div class="field ${emailMissing?'field-error':''}"><label>Web3Forms Access Key${c.enabled?'（必填）':''}</label><input data-contact-field="web3forms_access_key" value="${esc(c.web3forms_access_key)}" autocomplete="off" spellcheck="false" ${c.enabled?'required':''} aria-invalid="${emailMissing?'true':'false'}"></div>`;
    return `<div class="site-settings-card"><label class="switch"><input type="checkbox" data-contact-field="enabled" ${c.enabled?'checked':''}>啟用聯絡表單</label><div class="field"><label>通知信固定主旨</label><input data-contact-field="email_subject" value="${esc(c.email_subject)}" maxlength="160" placeholder="[hctsui.github.io] New contact message"></div><div class="field"><label>傳送模式</label><select data-contact-field="mode"><option value="email_only" ${worker?'':'selected'}>Web3Forms Email（免費、無 Admin 通知）</option><option value="worker" ${worker?'selected':''}>Cloudflare Worker 橋接（Email＋匿名 Admin 通知）</option></select></div>${delivery}</div><div class="site-settings-card"><h3>表單文字</h3><div class="pair-grid"><div class="field"><label>表單標題（英文）</label><input data-contact-field="title.en" value="${esc(c.title.en)}"></div><div class="field"><label>表單標題（中文）</label><input data-contact-field="title.zh" value="${esc(c.title.zh)}"></div></div><div class="pair-grid"><div class="field"><label>表單說明（英文）</label><textarea data-contact-field="intro.en">${esc(c.intro.en)}</textarea></div><div class="field"><label>表單說明（中文）</label><textarea data-contact-field="intro.zh">${esc(c.intro.zh)}</textarea></div></div><div class="pair-grid"><div class="field"><label>姓名欄（英文）</label><input data-contact-field="name_label.en" value="${esc(c.name_label.en)}"></div><div class="field"><label>姓名欄（中文）</label><input data-contact-field="name_label.zh" value="${esc(c.name_label.zh)}"></div></div><div class="pair-grid"><div class="field"><label>Email 欄（英文）</label><input data-contact-field="email_label.en" value="${esc(c.email_label.en)}"></div><div class="field"><label>Email 欄（中文）</label><input data-contact-field="email_label.zh" value="${esc(c.email_label.zh)}"></div></div><div class="pair-grid"><div class="field"><label>主旨欄（英文）</label><input data-contact-field="subject_label.en" value="${esc(c.subject_label.en)}"></div><div class="field"><label>主旨欄（中文）</label><input data-contact-field="subject_label.zh" value="${esc(c.subject_label.zh)}"></div></div><div class="pair-grid"><div class="field"><label>訊息欄（英文）</label><input data-contact-field="message_label.en" value="${esc(c.message_label.en)}"></div><div class="field"><label>訊息欄（中文）</label><input data-contact-field="message_label.zh" value="${esc(c.message_label.zh)}"></div></div><div class="pair-grid"><div class="field"><label>送出按鈕（英文）</label><input data-contact-field="submit_label.en" value="${esc(c.submit_label.en)}"></div><div class="field"><label>送出按鈕（中文）</label><input data-contact-field="submit_label.zh" value="${esc(c.submit_label.zh)}"></div></div><div class="pair-grid"><div class="field"><label>成功訊息（英文）</label><input data-contact-field="success_message.en" value="${esc(c.success_message.en)}"></div><div class="field"><label>成功訊息（中文）</label><input data-contact-field="success_message.zh" value="${esc(c.success_message.zh)}"></div></div><div class="pair-grid"><div class="field"><label>隱私說明（英文）</label><textarea data-contact-field="privacy_note.en">${esc(c.privacy_note.en)}</textarea></div><div class="field"><label>隱私說明（中文）</label><textarea data-contact-field="privacy_note.zh">${esc(c.privacy_note.zh)}</textarea></div></div></div>`;
  }
  function contactColorEditor(key,label){const value=draft.contact_form.page_design.colors[key];return `<div class="field color-field"><label>${esc(label)}</label><div class="color-control"><input type="color" data-contact-color-picker="${key}" value="${esc(value)}"><input data-contact-color="${key}" value="${esc(value)}" maxlength="7" spellcheck="false"></div></div>`;}
  function renderContactPagePreview(){
    const c=draft.contact_form,p=c.page_design,colors=p.colors;
    return `<div class="contact-page-preview" style="--cp-bg:${esc(colors.background)};--cp-surface:${esc(colors.surface)};--cp-accent:${esc(colors.accent)};--cp-text:${esc(colors.text)};--cp-muted:${esc(colors.muted)};--cp-button:${esc(colors.button)};--cp-button-text:${esc(colors.button_text)}"><div class="contact-preview-nav"><strong>Hung-Chun Tsui</strong><span>${p.show_navigation?'Home　CV　Publications　Activities　Teaching　Contact':'（不顯示導覽列）'}</span><b>中文</b></div><div class="contact-preview-hero"><small>${esc(p.eyebrow.en)}</small><h3>${esc(p.title.en)}</h3><p>${esc(p.description.en)}</p></div><div class="contact-preview-card"><h4>${esc(c.title.en)}</h4><p>${esc(c.intro.en)}</p><div class="contact-preview-fields"><span>${esc(c.name_label.en)}</span><span>${esc(c.email_label.en)}</span><span class="wide">${esc(c.subject_label.en)}</span><span class="wide textarea">${esc(c.message_label.en)}</span></div><button type="button">${esc(c.submit_label.en)}</button></div>${p.show_footer?'<div class="contact-preview-footer">頁尾</div>':''}</div>`;
  }
  function renderContactPageDesign(c){
    const p=c.page_design;
    return `${renderContactPagePreview()}<div class="site-settings-card"><h3>頁面文字</h3><div class="pair-grid"><div class="field"><label>小標（英文）</label><input data-contact-page-field="eyebrow.en" value="${esc(p.eyebrow.en)}"></div><div class="field"><label>小標（中文）</label><input data-contact-page-field="eyebrow.zh" value="${esc(p.eyebrow.zh)}"></div></div><div class="pair-grid"><div class="field"><label>頁面標題（英文）</label><input data-contact-page-field="title.en" value="${esc(p.title.en)}"></div><div class="field"><label>頁面標題（中文）</label><input data-contact-page-field="title.zh" value="${esc(p.title.zh)}"></div></div><div class="pair-grid"><div class="field"><label>頁面說明（英文）</label><textarea data-contact-page-field="description.en">${esc(p.description.en)}</textarea></div><div class="field"><label>頁面說明（中文）</label><textarea data-contact-page-field="description.zh">${esc(p.description.zh)}</textarea></div></div></div><div class="site-settings-card"><h3>顯示</h3><div class="form-options"><label class="switch"><input type="checkbox" data-contact-page-field="show_navigation" ${p.show_navigation?'checked':''}>顯示導覽列</label><label class="switch"><input type="checkbox" data-contact-page-field="show_footer" ${p.show_footer?'checked':''}>顯示頁尾</label></div></div><div class="site-settings-card"><h3>顏色</h3><div class="color-grid">${COLOR_FIELDS.map(([key,label])=>contactColorEditor(key,label)).join('')}</div><button class="button" type="button" id="resetContactColors">恢復預設顏色</button></div>`;
  }
  function renderContactForm(){
    const root=document.querySelector('#contactFormSettingsPane');if(!root)return;const c=draft.contact_form;
    root.innerHTML=contactPanelButtons()+(currentContactPanel==='design'?renderContactPageDesign(c):renderContactFormSettings(c));
  }
  function colorEditor(key,label){const value=draft.error_page.colors[key];return `<div class="field color-field"><label>${esc(label)}</label><div class="color-control"><input type="color" data-error-color-picker="${key}" value="${esc(value)}"><input data-error-color="${key}" value="${esc(value)}" maxlength="7" spellcheck="false"></div></div>`;}
  function currentNavigationPages(){
    let source=siteDataCache;
    try{if(typeof effectiveSite==='function')source=effectiveSite();}catch{}
    return (source?.settings?.pages||[]).filter(page=>page&&page.show_in_navigation!==false&&page.path?.en);
  }
  function renderErrorPreview(){
    const e=draft.error_page,c=e.colors,pages=currentNavigationPages();
    const labels=pages.map(page=>page.name?.en||page.name?.zh||page.id).filter(Boolean);
    labels.push('Contact');
    const navigation=e.show_navigation?labels.map(esc).join('　'):'（不顯示導覽列）';
    return `<div class="error-page-preview" style="--p-bg:${esc(c.background)};--p-surface:${esc(c.surface)};--p-accent:${esc(c.accent)};--p-text:${esc(c.text)};--p-muted:${esc(c.muted)};--p-button:${esc(c.button)};--p-button-text:${esc(c.button_text)}"><div class="error-preview-nav"><strong>Hung-Chun Tsui</strong><span>${navigation}</span><b>中文</b></div><div class="error-preview-card"><div class="error-preview-code">404</div><small>${esc(e.eyebrow.en)}</small><h3>${esc(e.title.en)}</h3><p>${esc(e.description.en)}</p>${e.auto_redirect.enabled?`<div class="error-preview-redirect">${esc(e.auto_redirect.seconds)} 秒後返回首頁</div>`:''}<div class="error-preview-actions"><span>${esc(e.home_label.en)}</span>${e.secondary_label.en?`<span class="secondary">${esc(e.secondary_label.en)}</span>`:''}</div></div>${e.show_footer?'<div class="error-preview-footer">頁尾會使用「頁尾」分頁中的設定</div>':'<div class="error-preview-footer muted-preview">不顯示頁尾</div>'}</div>`;
  }
  function renderErrorPage(){
    const root=document.querySelector('#errorPageSettingsPane');if(!root)return;const e=draft.error_page;
    root.innerHTML=`${renderErrorPreview()}<div class="site-settings-card"><h3>文字</h3><div class="pair-grid"><div class="field"><label>小標（英文）</label><input data-error-field="eyebrow.en" value="${esc(e.eyebrow.en)}"></div><div class="field"><label>小標（中文）</label><input data-error-field="eyebrow.zh" value="${esc(e.eyebrow.zh)}"></div></div><div class="pair-grid"><div class="field"><label>標題（英文）</label><input data-error-field="title.en" value="${esc(e.title.en)}"></div><div class="field"><label>標題（中文）</label><input data-error-field="title.zh" value="${esc(e.title.zh)}"></div></div><div class="pair-grid"><div class="field"><label>說明（英文）</label><textarea data-error-field="description.en">${esc(e.description.en)}</textarea></div><div class="field"><label>說明（中文）</label><textarea data-error-field="description.zh">${esc(e.description.zh)}</textarea></div></div><div class="pair-grid"><div class="field"><label>返回首頁按鈕（英文）</label><input data-error-field="home_label.en" value="${esc(e.home_label.en)}"></div><div class="field"><label>返回首頁按鈕（中文）</label><input data-error-field="home_label.zh" value="${esc(e.home_label.zh)}"></div></div><div class="pair-grid"><div class="field"><label>次要按鈕（英文；可留白）</label><input data-error-field="secondary_label.en" value="${esc(e.secondary_label.en)}"></div><div class="field"><label>次要按鈕（中文；可留白）</label><input data-error-field="secondary_label.zh" value="${esc(e.secondary_label.zh)}"></div></div><div class="pair-grid"><div class="field"><label>次要網址（英文）</label><input data-error-field="secondary_url.en" value="${esc(e.secondary_url.en)}"></div><div class="field"><label>次要網址（中文）</label><input data-error-field="secondary_url.zh" value="${esc(e.secondary_url.zh)}"></div></div></div><div class="site-settings-card"><h3>顯示與自動返回</h3><div class="form-options"><label class="switch"><input type="checkbox" data-error-field="show_navigation" ${e.show_navigation?'checked':''}>顯示導覽列</label><label class="switch"><input type="checkbox" data-error-field="show_footer" ${e.show_footer?'checked':''}>顯示頁尾</label><label class="switch"><input type="checkbox" data-error-field="auto_redirect.enabled" ${e.auto_redirect.enabled?'checked':''}>自動返回首頁</label></div><div class="field redirect-seconds ${e.auto_redirect.enabled?'':'disabled-field'}"><label>幾秒後返回首頁</label><input type="number" min="1" max="300" data-error-field="auto_redirect.seconds" value="${esc(e.auto_redirect.seconds)}" ${e.auto_redirect.enabled?'':'disabled'}><p class="field-hint">可設定 1–300 秒。訪客切換語言後，會跳到相同語言的首頁。</p></div></div><div class="site-settings-card"><h3>顏色</h3><div class="color-grid">${COLOR_FIELDS.map(([key,label])=>colorEditor(key,label)).join('')}</div><button class="button" type="button" id="resetErrorColors">恢復預設顏色</button></div>`;
  }
  function renderStatus(){
    const root=document.querySelector('#siteSettingsStatus');if(!root)return;const errors=validate(),sections=dirty()?changeSections(normalizedRemote(),normalizedDraft()):[];
    if(!errors.length&&!dirty()){root.className='notice hidden';root.innerHTML='';return;}
    root.className='notice '+(errors.length?'error':'success');
    root.innerHTML=errors.length?`<strong>不能送出：</strong>${errors.map(esc).join('；')}`:`<strong>網站設定有 ${sections.reduce((n,x)=>n+x[1].length,0)} 項實際變更。</strong>`;
  }
  function render(){
    if(!ready)return;
    document.querySelectorAll('[data-site-settings-section]').forEach(button=>button.classList.toggle('active',button.dataset.siteSettingsSection===currentSection));
    const panes={footer:'footerSettingsPane',seo:'seoSettingsPane',analytics:'analyticsSettingsPane',errorPage:'errorPageSettingsPane',contactForm:'contactFormSettingsPane'};
    Object.entries(panes).forEach(([key,id])=>{const pane=document.querySelector(`#${id}`);if(pane)pane.hidden=currentSection!==key;});
    renderFooter();renderSeo();renderAnalytics();renderErrorPage();renderContactForm();renderStatus();
  }
  function updatePath(target,path,value){const parts=path.split('.');let obj=target;while(parts.length>1)obj=obj[parts.shift()];obj[parts[0]]=value;}
  function installPanel(){
    const tabs=document.querySelector('#tabs'),dictionary=document.querySelector('[data-tab="dictionary"]');if(tabs&&!document.querySelector('[data-tab="siteSettings"]'))dictionary?.insertAdjacentHTML('afterend','<button class="tab" data-tab="siteSettings">網站設定</button>');
    const dictionaryTab=document.querySelector('#dictionaryTab');if(dictionaryTab&&!document.querySelector('#siteSettingsTab'))dictionaryTab.insertAdjacentHTML('afterend',`<div id="siteSettingsTab" hidden><div class="site-settings-nav-shell"><div class="site-settings-tabs"><button class="button active" type="button" data-site-settings-section="footer">頁尾</button><button class="button" type="button" data-site-settings-section="contactForm">聯絡表單</button><button class="button" type="button" data-site-settings-section="seo">SEO／OG</button><button class="button" type="button" data-site-settings-section="analytics">流量統計</button><button class="button" type="button" data-site-settings-section="errorPage">404 頁面</button></div></div><div id="siteSettingsStatus" class="notice hidden"></div><div id="footerSettingsPane"></div><div id="seoSettingsPane" hidden></div><div id="analyticsSettingsPane" hidden></div><div id="errorPageSettingsPane" hidden></div><div id="contactFormSettingsPane" hidden></div><div class="actions settings-reset-actions"><button class="button" type="button" id="resetSiteSettings">放棄全部網站設定修改</button></div></div>`);
    const panel=document.querySelector('#siteSettingsTab');
    panel?.addEventListener('click',event=>{
      const section=event.target.closest('[data-site-settings-section]');if(section){currentSection=section.dataset.siteSettingsSection;render();return;}
      const contactPanel=event.target.closest('[data-contact-panel]');if(contactPanel){currentContactPanel=contactPanel.dataset.contactPanel==='design'?'design':'form';render();return;}
      const row=event.target.closest('[data-footer-index]');
      if(event.target.id==='addFooterItem'){draft.footer.items.push({id:`footer-item-${Date.now().toString(36)}`,text:{en:'',zh:''},url:'',icon:'none',custom_icon:'',alignment:'center',new_tab:false});save();return;}
      if(event.target.id==='resetFooterItems'){draft.footer=copy(defaultSettings(siteDataCache).footer);save();return;}
      if(event.target.id==='resetErrorColors'){draft.error_page.colors=copy(defaultSettings(siteDataCache).error_page.colors);save();return;}
      if(event.target.id==='resetContactColors'){draft.contact_form.page_design.colors=copy(defaultSettings(siteDataCache).contact_form.page_design.colors);save();return;}
      if(event.target.id==='resetSiteSettings'){if(confirm('放棄尚未送出的頁尾、聯絡表單、SEO／OG、流量統計與 404 頁面修改？')){draft=copy(remote);save();}return;}
      if(row){const index=Number(row.dataset.footerIndex);if(event.target.closest('[data-footer-remove]')){draft.footer.items.splice(index,1);save();return;}const move=event.target.closest('[data-footer-move]')?.dataset.footerMove;if(move){const next=move==='up'?index-1:index+1;if(next>=0&&next<draft.footer.items.length){[draft.footer.items[index],draft.footer.items[next]]=[draft.footer.items[next],draft.footer.items[index]];save();}}}
    });
    panel?.addEventListener('input',event=>{
      const target=event.target;
      if(target.id==='seoPageSelect'){currentPage=target.value;render();return;}
      if(target.matches('[data-seo-global]')){draft.seo[target.dataset.seoGlobal]=target.value;save(false);return;}
      if(target.matches('[data-seo-site-name]')){draft.seo.site_name[target.dataset.seoSiteName]=target.value;save(false);return;}
      if(target.matches('[data-page-field]')){updatePath(draft.seo.pages[currentPage],target.dataset.pageField,target.value);save(false);return;}
      if(target.matches('[data-analytics-field]')){draft.analytics[target.dataset.analyticsField]=target.type==='checkbox'?target.checked:target.value;save(false);return;}
      if(target.matches('[data-contact-field]')){const value=target.type==='checkbox'?target.checked:target.value;updatePath(draft.contact_form,target.dataset.contactField,value);save(false);return;}
      if(target.matches('[data-contact-page-field]')){const value=target.type==='checkbox'?target.checked:target.value;updatePath(draft.contact_form.page_design,target.dataset.contactPageField,value);save(false);return;}
      if(target.matches('[data-contact-color]')){draft.contact_form.page_design.colors[target.dataset.contactColor]=target.value;const picker=panel.querySelector(`[data-contact-color-picker="${target.dataset.contactColor}"]`);if(/^#[0-9a-f]{6}$/i.test(target.value)&&picker)picker.value=target.value;save(false);return;}
      if(target.matches('[data-contact-color-picker]')){draft.contact_form.page_design.colors[target.dataset.contactColorPicker]=target.value;const input=panel.querySelector(`[data-contact-color="${target.dataset.contactColorPicker}"]`);if(input)input.value=target.value;save(false);return;}
      if(target.matches('[data-error-field]')){const value=target.type==='checkbox'?target.checked:target.type==='number'?Number(target.value):target.value;updatePath(draft.error_page,target.dataset.errorField,value);save(false);return;}
      if(target.matches('[data-error-color]')){draft.error_page.colors[target.dataset.errorColor]=target.value;const picker=panel.querySelector(`[data-error-color-picker="${target.dataset.errorColor}"]`);if(/^#[0-9a-f]{6}$/i.test(target.value)&&picker)picker.value=target.value;save(false);return;}
      if(target.matches('[data-error-color-picker]')){draft.error_page.colors[target.dataset.errorColorPicker]=target.value;const input=panel.querySelector(`[data-error-color="${target.dataset.errorColorPicker}"]`);if(input)input.value=target.value;save(false);return;}
      const row=target.closest('[data-footer-index]');if(row&&target.matches('[data-footer-field]')){const item=draft.footer.items[Number(row.dataset.footerIndex)],field=target.dataset.footerField;updatePath(item,field,target.type==='checkbox'?target.checked:target.value);save(false);}
    });
    panel?.addEventListener('change',event=>{if(event.target.matches('select,[type="checkbox"],[type="color"],[type="number"]'))save();});
  }
  function installStyles(){
    const style=document.createElement('style');style.id='site-settings-admin-styles';style.textContent=`
      .site-settings-nav-shell,.database-type-shell{margin-top:20px;padding-top:18px;border-top:1px solid #e3d8cf}
      .site-settings-tabs,.database-type-tabs{display:flex;gap:9px;flex-wrap:wrap;margin:0 0 10px}
      .site-settings-tabs .button.active,.database-type-tabs .button.active{background:#2d2926;color:#fff;border-color:#2d2926}
      .settings-intro{display:grid;gap:3px;margin:18px 0 12px;padding:12px 14px;border-left:4px solid #8d493d;border-radius:9px;background:#f7f0eb;color:#2d2926}.settings-intro span{color:#6c625c}
      .site-settings-card,.footer-editor-row{border:1px solid #dfd3ca;border-radius:13px;padding:15px;margin:12px 0;background:#fcfaf8}.site-settings-card h3{margin-top:0}
      .settings-toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 8px}.settings-page-select{max-width:360px;margin:16px 0}.settings-reset-actions{margin-top:20px;padding-top:16px;border-top:1px solid #e5dbd3}
      .footer-editor-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.footer-admin-preview{display:grid;gap:12px;margin:14px 0 18px}
      .footer-preview-language{border:1px solid #584941;border-radius:12px;overflow:hidden;background:#2f2723;color:#fff}.footer-preview-language-label{padding:7px 11px;background:#1f1a18;color:#f2dfd5;font-size:.74rem;font-weight:900;letter-spacing:.04em}
      .footer-preview-zones{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;padding:15px}.footer-preview-zones>div{display:flex;gap:9px;flex-wrap:wrap;align-items:center;min-height:28px}.footer-preview-zones>div:nth-child(2){justify-content:center}.footer-preview-zones>div:nth-child(3){justify-content:flex-end}
      .footer-preview-item{display:inline-flex;gap:6px;align-items:center;color:#fff!important;font-weight:700}.footer-preview-icon{display:inline-flex;padding:2px 6px;border-radius:999px;background:#f3e5dd;color:#3c2d27!important;font-size:.7rem}.footer-preview-item img{width:18px;height:18px;object-fit:contain;background:#fff;border-radius:4px;padding:1px}
      .custom-icon-field{padding:10px;border-radius:10px;background:#fff4df;border:1px solid #e8c98d}
      .contact-setup-warning{margin:12px 0}.field-error{padding:10px;border:1px solid #c94b45;border-radius:10px;background:#fff7f6}.field-error input{border-color:#c94b45!important;box-shadow:0 0 0 2px #c94b4522}
      .analytics-status{display:grid;gap:3px;margin-top:14px;padding:12px;border-radius:10px}.analytics-status.enabled{background:#eef8f1;border-left:4px solid #247a46}.analytics-status.disabled{background:#f3efec;border-left:4px solid #8b7a70}.analytics-status span{color:#6c625c}.analytics-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.analytics-report-note{display:grid;gap:4px;margin-top:14px;padding:12px;border-radius:10px;background:#f7f0eb;border-left:4px solid #8d493d}.analytics-report-note span{color:#6c625c}
      .color-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.color-control{display:grid;grid-template-columns:48px 1fr;gap:8px}.color-control input[type=color]{padding:2px;height:42px}
      .disabled-field{opacity:.55}.error-page-preview{margin:14px 0 18px;padding:14px;border-radius:14px;background:var(--p-bg);color:var(--p-text);border:1px solid color-mix(in srgb,var(--p-text) 15%,transparent)}
      .error-preview-nav{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:4px 4px 12px;color:var(--p-text)}.error-preview-nav span{flex:1;text-align:right;color:var(--p-muted);font-size:.78rem}.error-preview-nav b{border:1px solid color-mix(in srgb,var(--p-text) 20%,transparent);border-radius:999px;padding:4px 8px;font-size:.76rem}.error-preview-card{text-align:center;padding:28px;border-radius:14px;background:var(--p-surface);box-shadow:0 10px 28px color-mix(in srgb,var(--p-text) 10%,transparent)}
      .error-preview-code{font:800 3.5rem/.9 Georgia,serif;color:color-mix(in srgb,var(--p-accent) 25%,transparent)}.error-preview-card small{color:var(--p-accent);font-weight:900;text-transform:uppercase;letter-spacing:.1em}.error-preview-card h3{color:var(--p-text);margin:.4rem 0}.error-preview-card p{color:var(--p-muted);margin:.4rem auto;max-width:520px}.error-preview-redirect{color:var(--p-accent);font-weight:800;margin-top:8px}
      .error-preview-actions{display:flex;justify-content:center;gap:8px;margin-top:16px}.error-preview-actions span{padding:8px 12px;border-radius:999px;background:var(--p-button);color:var(--p-button-text);font-weight:800}.error-preview-actions span.secondary{background:transparent;color:var(--p-button);border:1px solid var(--p-button)}.error-preview-footer{text-align:center;margin-top:10px;color:var(--p-muted);font-size:.78rem}.muted-preview{opacity:.7}
      .contact-settings-choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0 18px}.contact-settings-choice{min-height:72px;border:1px solid #d7c9bf;border-radius:14px;background:#fff;color:#2d2926;padding:18px;font:inherit;font-size:1rem;text-align:center;cursor:pointer}.contact-settings-choice:hover,.contact-settings-choice.active{border-color:#8d493d;background:#8d493d;color:#fff}.contact-settings-choice strong{font-weight:850}
      .contact-page-preview{margin:14px 0 18px;padding:14px;border:1px solid color-mix(in srgb,var(--cp-text) 16%,transparent);border-radius:15px;background:var(--cp-bg);color:var(--cp-text)}.contact-preview-nav{display:flex;align-items:center;gap:12px;padding:3px 3px 13px}.contact-preview-nav span{margin-left:auto;color:var(--cp-muted);font-size:.76rem}.contact-preview-nav b{border:1px solid color-mix(in srgb,var(--cp-text) 20%,transparent);border-radius:999px;padding:4px 8px;font-size:.74rem}.contact-preview-hero{text-align:center;padding:22px 12px}.contact-preview-hero small{color:var(--cp-accent);font-weight:900;text-transform:uppercase;letter-spacing:.12em}.contact-preview-hero h3{margin:.45rem 0;color:var(--cp-text);font-size:1.75rem}.contact-preview-hero p{margin:0 auto;max-width:560px;color:var(--cp-muted)}.contact-preview-card{max-width:680px;margin:0 auto;padding:22px;border-radius:15px;background:var(--cp-surface);box-shadow:0 12px 30px color-mix(in srgb,var(--cp-text) 10%,transparent)}.contact-preview-card h4{margin:0 0 .35rem;color:var(--cp-text)}.contact-preview-card>p{color:var(--cp-muted)}.contact-preview-fields{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0}.contact-preview-fields span{display:block;min-height:36px;padding:9px;border:1px solid color-mix(in srgb,var(--cp-text) 18%,transparent);border-radius:8px;color:var(--cp-muted);background:var(--cp-bg);font-size:.78rem}.contact-preview-fields .wide{grid-column:1/-1}.contact-preview-fields .textarea{min-height:66px}.contact-preview-card button{border:0;border-radius:999px;background:var(--cp-button);color:var(--cp-button-text);padding:9px 15px;font:inherit;font-weight:850}.contact-preview-footer{text-align:center;margin-top:12px;color:var(--cp-muted);font-size:.78rem}
      .settings-diff{color:#2d2926}.settings-diff-section{margin:12px 0;padding:12px;border:1px solid #dfd3ca;border-radius:10px;background:#fff;color:#2d2926}.settings-diff-section h4{margin:0 0 8px}.settings-diff-section ul{list-style:none;padding:0;margin:0;display:grid;gap:7px}.settings-diff-section li{display:grid;grid-template-columns:minmax(130px,.8fr) minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:start;padding:8px;border-radius:8px;background:#f8f4f0;color:#2d2926}.settings-old,.settings-new{display:block;padding:5px 7px;border-radius:7px;overflow-wrap:anywhere}.settings-old{background:#fff0ee;color:#7d2f28}.settings-new{background:#eaf7ed;color:#1f6539}.settings-arrow{font-weight:900;color:#766c65}
      @media(max-width:700px){.footer-preview-zones,.color-grid,.contact-settings-choices,.contact-preview-fields{grid-template-columns:1fr}.footer-preview-zones>div{justify-content:flex-start!important}.settings-diff-section li{grid-template-columns:1fr}.settings-arrow{display:none}.footer-editor-head{align-items:flex-start;flex-direction:column}}
    `;document.head.append(style);
  }
  window.siteSettingsDirty=dirty;window.siteSettingsOperation=operation;window.siteSettingsPreviewHtml=previewHtml;window.siteSettingsHistoryPreviewHtml=history=>previewHtml({before:history.before,after:history.after});window.validateSiteSettingsDraft=validate;window.clearSiteSettingsDraft=clearDraft;window.renderSiteSettings=render;window.openSiteSettingsSection=function(section,subsection){currentSection=SECTION_LABELS[section]?section:'footer';if(section==='contactForm')currentContactPanel=subsection==='design'?'design':'form';render();};
  installStyles();installPanel();
  fetch('../content/site.json',{cache:'no-store'}).then(response=>response.json()).then(siteData=>{
    siteDataCache=siteData;remote=normalize({footer:siteData.settings?.footer,seo:siteData.settings?.seo,analytics:siteData.settings?.analytics,contact_form:siteData.settings?.contact_form,error_page:siteData.settings?.error_page},siteData);draft=loadSaved(remote);ready=true;render();if(typeof site!=='undefined'&&site&&typeof renderPreview==='function')renderPreview(false);
  }).catch(error=>{const status=document.querySelector('#siteSettingsStatus');if(status){status.className='notice error';status.textContent='讀取網站設定失敗：'+error;}});
})();
