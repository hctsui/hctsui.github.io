'use strict';

/* Inline navigation ordering and clearer website-identity placement previews. */
(function installInlineNavigationAndIdentitySettings(){
  if(window.__hctsuiInlineNavigationSettingsInstalled)return;
  window.__hctsuiInlineNavigationSettingsInstalled=true;

  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);
  const pageLabel=page=>page?.name?.zh||page?.name?.en||page?.id||'未命名頁面';
  const pagePath=page=>[page?.path?.en,page?.path?.zh].filter(Boolean).join(' ／ ')||'沒有公開網址';

  function layoutIsReady(){
    try{
      if(typeof initLayoutState!=='function'||typeof saveLayoutDraft!=='function')return false;
      initLayoutState();
      return typeof layoutDraft!=='undefined'&&Array.isArray(layoutDraft?.pages);
    }catch{return false;}
  }

  function visibleNavigationPages(){
    if(!layoutIsReady())return[];
    return layoutDraft.pages.filter(page=>page&&page.show_in_navigation!==false);
  }

  function navigationPreview(){
    const labels=visibleNavigationPages().map(page=>escapeHtml(pageLabel(page)));
    return `<div class="inline-nav-preview"><span class="inline-nav-preview-brand">品牌</span><span>${labels.join('　')||'（目前沒有導覽頁面）'}</span></div>`;
  }

  function navigationRow(page,index,pages){
    const visible=page.show_in_navigation!==false;
    return `<div class="inline-nav-row" data-inline-nav-page="${escapeHtml(page.id)}">
      <div class="inline-nav-main">
        <strong>${escapeHtml(pageLabel(page))}</strong>
        <span>${escapeHtml(pagePath(page))}</span>
      </div>
      <label class="switch inline-nav-visible"><input type="checkbox" data-inline-nav-visible="${escapeHtml(page.id)}" ${visible?'checked':''}>顯示</label>
      <div class="actions inline-nav-actions">
        <button class="button" type="button" data-inline-nav-move="up" data-page-id="${escapeHtml(page.id)}" ${index===0?'disabled':''}>上移</button>
        <button class="button" type="button" data-inline-nav-move="down" data-page-id="${escapeHtml(page.id)}" ${index===pages.length-1?'disabled':''}>下移</button>
      </div>
    </div>`;
  }

  function buildInlineNavigationEditor(){
    if(!layoutIsReady())return '<div class="notice error">頁面資料尚未載入，請重新整理後再試。</div>';
    const pages=layoutDraft.pages;
    return `<div data-inline-navigation-editor>
      <div class="site-settings-subnote inline-nav-help"><strong>直接調整導覽列</strong><span>在這裡決定頁面是否顯示，並用上移／下移調整順序。修改會建立「頁面與類別配置」草稿，和其他草稿一起送出。</span></div>
      ${navigationPreview()}
      <div class="inline-nav-list">${pages.map((page,index)=>navigationRow(page,index,pages)).join('')||'<p class="muted">目前沒有頁面。</p>'}</div>
    </div>`;
  }

  function enhanceNavigationPanel(){
    const pane=document.querySelector('#generalSettingsPane');
    const active=pane?.querySelector('[data-general-panel="navigation"].active');
    if(!pane||!active)return false;
    const card=[...pane.querySelectorAll('.site-settings-card')].find(node=>node.querySelector('h3')?.textContent?.trim()==='公開導覽列');
    if(!card||card.querySelector('[data-inline-navigation-editor]'))return !!card;
    const oldButton=card.querySelector('[data-open-page-manager]');
    const oldSummary=oldButton?.previousElementSibling?.classList?.contains('site-settings-subnote')?oldButton.previousElementSibling:null;
    oldSummary?.remove();
    oldButton?.remove();
    card.insertAdjacentHTML('beforeend',buildInlineNavigationEditor());
    return true;
  }

  function identityValues(card){
    const value=path=>card.querySelector(`[data-general-field="${path}"]`)?.value||'';
    return {
      brandEn:value('identity.brand.en'),
      brandZh:value('identity.brand.zh'),
      menuEn:value('identity.menu_label.en'),
      menuZh:value('identity.menu_label.zh'),
    };
  }

  function identityPreviewHtml(values){
    const brandEn=escapeHtml(values.brandEn||'Brand');
    const brandZh=escapeHtml(values.brandZh||values.brandEn||'品牌');
    const menuEn=escapeHtml(values.menuEn||'Menu');
    const menuZh=escapeHtml(values.menuZh||'選單');
    return `<div data-identity-placement-guide>
      <div class="site-settings-subnote identity-location-help"><strong>顯示位置</strong><span>品牌名稱固定顯示在公開網站導覽列最左上角，點擊後返回首頁。選單按鈕只在手機或窄螢幕顯示，用來展開導覽項目。</span></div>
      <div class="identity-preview-grid">
        <section class="identity-preview-card desktop"><small>桌面版</small><div><strong data-identity-preview-brand-en>${brandEn}</strong><span>Home　CV　Publications</span><b>中文</b></div></section>
        <section class="identity-preview-card mobile"><small>手機版</small><div><strong data-identity-preview-brand-zh>${brandZh}</strong><button type="button" tabindex="-1"><span data-identity-preview-menu-en>${menuEn}</span>／<span data-identity-preview-menu-zh>${menuZh}</span></button></div></section>
      </div>
    </div>`;
  }

  function relabelIdentityFields(card){
    const replacements={
      '品牌名稱（英文）':'品牌名稱（英文，左上角）',
      '品牌名稱（中文）':'品牌名稱（中文，左上角）',
      '選單按鈕（英文）':'手機選單按鈕（英文）',
      '選單按鈕（中文）':'手機選單按鈕（中文）',
    };
    card.querySelectorAll('label').forEach(label=>{
      const current=label.textContent.trim();
      if(replacements[current])label.textContent=replacements[current];
    });
  }

  function enhanceIdentityPanel(){
    const pane=document.querySelector('#generalSettingsPane');
    const active=pane?.querySelector('[data-general-panel="identity"].active');
    if(!pane||!active)return false;
    const card=[...pane.querySelectorAll('.site-settings-card')].find(node=>node.querySelector('h3')?.textContent?.trim()==='網站識別');
    if(!card)return false;
    relabelIdentityFields(card);
    if(!card.querySelector('[data-identity-placement-guide]')){
      card.querySelector('h3')?.insertAdjacentHTML('afterend',identityPreviewHtml(identityValues(card)));
    }
    return true;
  }

  function updateIdentityPreview(input){
    const card=input.closest('.site-settings-card');
    if(!card?.querySelector('[data-identity-placement-guide]'))return;
    const values=identityValues(card);
    const set=(selector,value)=>{const node=card.querySelector(selector);if(node)node.textContent=value;};
    set('[data-identity-preview-brand-en]',values.brandEn||'Brand');
    set('[data-identity-preview-brand-zh]',values.brandZh||values.brandEn||'品牌');
    set('[data-identity-preview-menu-en]',values.menuEn||'Menu');
    set('[data-identity-preview-menu-zh]',values.menuZh||'選單');
  }

  function rerenderSettings(){
    if(typeof window.renderSiteSettings==='function')window.renderSiteSettings();
    queueMicrotask(enhance);
  }

  function savePageLayout(message){
    if(!layoutIsReady())return;
    layoutDraft.pages.forEach((page,index)=>{page.order=index;});
    saveLayoutDraft(message);
    rerenderSettings();
  }

  function movePage(pageId,direction){
    if(!layoutIsReady())return;
    const pages=layoutDraft.pages,index=pages.findIndex(page=>page.id===pageId);
    const next=direction==='up'?index-1:index+1;
    if(index<0||next<0||next>=pages.length)return;
    [pages[index],pages[next]]=[pages[next],pages[index]];
    savePageLayout('已調整公開導覽列順序');
  }

  function setPageVisibility(pageId,visible){
    if(!layoutIsReady())return;
    const page=layoutDraft.pages.find(item=>item.id===pageId);
    if(!page)return;
    page.show_in_navigation=visible;
    savePageLayout(visible?'已將頁面加入公開導覽列':'已將頁面從公開導覽列隱藏');
  }

  function enhance(){
    enhanceNavigationPanel();
    enhanceIdentityPanel();
  }

  document.addEventListener('click',event=>{
    const move=event.target.closest('[data-inline-nav-move]');
    if(move){movePage(move.dataset.pageId,move.dataset.inlineNavMove);return;}
  });
  document.addEventListener('change',event=>{
    const checkbox=event.target.closest('[data-inline-nav-visible]');
    if(checkbox){setPageVisibility(checkbox.dataset.inlineNavVisible,checkbox.checked);}
  });
  document.addEventListener('input',event=>{
    if(event.target.matches('[data-general-field^="identity."]'))updateIdentityPreview(event.target);
  });

  const style=document.createElement('style');
  style.id='inline-navigation-settings-styles';
  style.textContent=`
    [data-inline-navigation-editor]{display:grid;gap:12px;margin-top:14px}
    .inline-nav-help{margin:0}.inline-nav-preview{display:flex;align-items:center;gap:18px;padding:12px 14px;border:1px solid #ded3ca;border-radius:11px;background:#fff;overflow:auto;white-space:nowrap}.inline-nav-preview-brand{font-family:Georgia,serif;font-weight:900;color:#2d2926}.inline-nav-preview>span:last-child{margin-left:auto;color:#6c625c;font-size:.82rem}
    .inline-nav-list{display:grid;gap:8px}.inline-nav-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:11px;border:1px solid #e3d8cf;border-radius:11px;background:#fff}.inline-nav-main{display:grid;gap:2px;min-width:0}.inline-nav-main strong{overflow-wrap:anywhere}.inline-nav-main span{color:#766c65;font:11px ui-monospace,monospace;overflow-wrap:anywhere}.inline-nav-visible{margin:0}.inline-nav-actions{justify-content:flex-end}.inline-nav-actions .button{padding:7px 10px;min-height:36px}
    .identity-location-help{margin:0 0 12px}.identity-preview-grid{display:grid;grid-template-columns:1.35fr .8fr;gap:10px;margin:10px 0 16px}.identity-preview-card{padding:11px;border:1px solid #ded3ca;border-radius:11px;background:#fff}.identity-preview-card small{display:block;margin-bottom:7px;color:#766c65;font-weight:850}.identity-preview-card>div{display:flex;align-items:center;gap:10px;min-height:42px}.identity-preview-card strong{font-family:Georgia,serif;font-size:1.05rem}.identity-preview-card.desktop span{margin-left:auto;color:#6c625c;font-size:.72rem}.identity-preview-card.desktop b{padding:3px 7px;border:1px solid #d6c8bd;border-radius:999px;font-size:.68rem}.identity-preview-card.mobile>div{justify-content:space-between}.identity-preview-card.mobile button{border:1px solid #d6c8bd;border-radius:8px;background:#fff;padding:7px 9px;color:#2d2926;font:inherit;font-size:.74rem;font-weight:800;pointer-events:none}
    @media(max-width:760px){.inline-nav-row{grid-template-columns:1fr auto}.inline-nav-actions{grid-column:1/-1;justify-content:flex-start}.identity-preview-grid{grid-template-columns:1fr}.inline-nav-preview{align-items:flex-start;flex-direction:column}.inline-nav-preview>span:last-child{margin-left:0}}
  `;
  document.head.append(style);

  let scheduled=false;
  const schedule=()=>{if(scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;enhance();});};
  const observer=new MutationObserver(schedule);
  observer.observe(document.body,{childList:true,subtree:true});
  schedule();
})();
