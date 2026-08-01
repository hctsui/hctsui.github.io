/* Authenticated, provider-neutral traffic report for the Admin site settings. */
(function installAnalyticsReport(){
  const SESSION_KEY='hctsui-github-submit-session-v1';
  const DEFAULT_API='https://hctsui-website-worker.hctsui-math.workers.dev';
  const state={provider:'cloudflare',range:'7d',workerUrl:'',sequence:0,mounted:false};
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const readSession=()=>{try{return JSON.parse(localStorage.getItem(SESSION_KEY)||'null')}catch{localStorage.removeItem(SESSION_KEY);return null}};
  const format=value=>value==null?'—':new Intl.NumberFormat('zh-TW',{maximumFractionDigits:0}).format(Number(value)||0);
  const providerName=()=>state.provider==='google'?'Google Analytics 4':'Cloudflare Web Analytics';
  const dashboardUrl=()=>state.provider==='google'?'https://analytics.google.com/analytics/web/':'https://dash.cloudflare.com/';
  function apiBase(){
    const configured=String(state.workerUrl||site?.settings?.contact_form?.worker_url||'').trim();
    try{return new URL(configured||DEFAULT_API).origin}catch{return DEFAULT_API}
  }
  function panel(){return document.querySelector('#analyticsReportPanel')}
  function sessionValid(saved){return Boolean(saved?.token&&saved?.expires&&saved.expires*1000>Date.now())}
  function ranges(){return [['1d','今天'],['7d','7 天'],['30d','30 天'],['90d','90 天']].map(([value,label])=>`<button class="button ${state.range===value?'active':''}" type="button" data-analytics-range="${value}">${label}</button>`).join('')}
  function providers(){return [['cloudflare','Cloudflare 報表'],['google','Google 報表']].map(([value,label])=>`<button class="button ${state.provider===value?'active':''}" type="button" data-analytics-report-provider="${value}">${label}</button>`).join('')}
  function head(subtitle='直接在 Admin 查看彙整資料，不必另外開啟服務商後台。'){
    return `<div class="analytics-report-head"><div><h3>${esc(providerName())} 報表</h3><p>${esc(subtitle)}</p></div><div class="analytics-range-tabs" aria-label="報表範圍">${ranges()}</div></div><div class="analytics-report-provider-tabs" aria-label="報表提供者">${providers()}</div>`;
  }
  function setupText(message){
    const instructions=state.provider==='google'
      ? '需在 Worker 設定 GA4 Property ID 與服務帳戶 JSON，並在 GA4 將該服務帳戶加入「檢視者」。'
      : '需在 Worker 設定 Cloudflare Account ID 與只有 Account Analytics: Read 權限的 API Token。';
    return `${head()}<div class="analytics-report-error"><strong>${esc(message||'報表尚未設定完成')}</strong><p>${esc(instructions)}</p><div class="analytics-actions"><button class="button primary" type="button" data-analytics-retry>重新檢查</button><a class="button" href="${dashboardUrl()}" target="_blank" rel="noopener">開啟${esc(providerName())}</a></div></div>`;
  }
  function loginHtml(){
    return `${head()}<div class="analytics-report-error"><strong>請先登入 GitHub</strong><p>報表沿用網站修改功能的 14 天登入，只開放給網站管理者。</p><div class="analytics-actions"><button class="button primary" type="button" data-analytics-login>登入 GitHub 並查看報表</button></div></div>`;
  }
  function bars(title,rows){
    const list=Array.isArray(rows)?rows:[],max=Math.max(1,...list.map(row=>Number(row.value)||0));
    return `<section class="analytics-detail"><h4>${esc(title)}</h4>${list.length?`<div class="analytics-bars">${list.map(row=>`<div class="analytics-bar-row" title="${esc(row.label)}：${format(row.value)}"><span class="analytics-bar-label">${esc(row.label)}</span><span class="analytics-bar-value">${format(row.value)}</span><span class="analytics-bar-track"><span class="analytics-bar-fill" style="width:${Math.max(2,Math.round((Number(row.value)||0)/max*100))}%"></span></span></div>`).join('')}</div>`:'<div class="analytics-empty">這段期間沒有資料</div>'}</section>`;
  }
  function chart(rows){
    const list=Array.isArray(rows)?rows:[],max=Math.max(1,...list.map(row=>Number(row.views)||0)),step=Math.max(1,Math.ceil(list.length/6));
    if(!list.length)return '<div class="analytics-empty">這段期間還沒有每日趨勢資料。</div>';
    return `<div class="analytics-chart" role="img" aria-label="每日瀏覽量趨勢">${list.map((row,index)=>`<span class="analytics-chart-column" title="${esc(row.date)}：${format(row.views)} 次瀏覽"><span class="analytics-chart-bar" style="height:${Math.max(2,Math.round((Number(row.views)||0)/max*100))}%"></span>${index%step===0||index===list.length-1?`<small>${esc(String(row.date||'').slice(5))}</small>`:''}</span>`).join('')}</div>`;
  }
  function reportHtml(data){
    const note=data.cached?'使用 5 分鐘快取資料':'剛剛更新';
    return `${head(`${providerName()} · ${data.days} 天彙整`)}<div class="analytics-summary-grid"><div class="analytics-summary-item"><strong>${format(data.summary?.views)}</strong><span>瀏覽量</span></div><div class="analytics-summary-item"><strong>${format(data.summary?.visits)}</strong><span>${state.provider==='google'?'工作階段':'造訪'}</span></div><div class="analytics-summary-item"><strong>${format(data.summary?.users)}</strong><span>${state.provider==='google'?'使用者':'Cloudflare 不提供使用者數'}</span></div></div><h4>每日趨勢</h4>${chart(data.trend)}<div class="analytics-detail-grid">${bars('熱門頁面',data.top_pages)}${bars('流量來源',data.referrers)}${bars('國家／地區',data.countries)}${bars('裝置',data.devices)}${bars('瀏覽器',data.browsers)}</div><div class="analytics-report-footer"><span>${esc(note)} · ${esc(new Date(data.generated_at||Date.now()).toLocaleString('zh-TW'))}</span><div class="analytics-actions"><button class="button" type="button" data-analytics-retry>重新整理</button><a class="button" href="${dashboardUrl()}" target="_blank" rel="noopener">完整儀表板</a></div></div>`;
  }
  function bind(root){
    root.onclick=event=>{
      const provider=event.target.closest('[data-analytics-report-provider]');
      if(provider){state.provider=provider.dataset.analyticsReportProvider==='google'?'google':'cloudflare';load();return}
      const range=event.target.closest('[data-analytics-range]');
      if(range){state.range=range.dataset.analyticsRange;load(true);return}
      if(event.target.closest('[data-analytics-retry]')){load(true);return}
      if(event.target.closest('[data-analytics-login]'))location.assign(`${apiBase()}/cms/auth/start`);
    };
  }
  async function load(force=false){
    const root=panel();if(!root)return;
    const sequence=++state.sequence;
    bind(root);
    const saved=readSession();
    if(!sessionValid(saved)){root.innerHTML=loginHtml();bind(root);return}
    root.innerHTML=`${head()}<div class="analytics-report-loading">正在讀取 ${esc(providerName())}…</div>`;bind(root);
    try{
      const response=await fetch(`${apiBase()}/cms/analytics?provider=${encodeURIComponent(state.provider)}&range=${encodeURIComponent(state.range)}${force?'&refresh=1':''}`,{headers:{Authorization:`Bearer ${saved.token}`},cache:'no-store'});
      const data=await response.json().catch(()=>({}));
      if(sequence!==state.sequence||root!==panel())return;
      if(response.status===401){localStorage.removeItem(SESSION_KEY);root.innerHTML=loginHtml();return}
      if(!response.ok||!data.success){
        const message=response.status===404?'Worker 尚未更新到流量報表版本，請先部署最新的 Worker 程式。':data.message||'目前無法讀取流量報表';
        root.innerHTML=setupText(message);return
      }
      root.innerHTML=reportHtml(data);
    }catch{
      if(sequence!==state.sequence||root!==panel())return;
      root.innerHTML=setupText('Worker 暫時無法連線，請稍後重新整理。');
    }finally{if(sequence===state.sequence&&root===panel())bind(root)}
  }
  function mount(options={}){
    if(!state.mounted)state.provider=options.initialProvider==='google'?'google':'cloudflare';
    state.mounted=true;
    state.workerUrl=String(options.workerUrl||'');
    const root=panel();if(!root)return;
    root.dataset.analyticsProvider=state.provider;
    load();
  }
  function mountFromPage(){
    const mode=document.querySelector('[data-analytics-field="tracking_mode"]')?.value;
    if(panel())mount({initialProvider:mode==='google'?'google':'cloudflare',workerUrl:site?.settings?.contact_form?.worker_url||''});
  }
  window.hctsuiAnalyticsReport={mount,refresh:()=>load(true)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mountFromPage,{once:true});
  else setTimeout(mountFromPage,0);
})();
