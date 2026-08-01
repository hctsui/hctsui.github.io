/* GitHub-authenticated one-tap submission. The browser keeps only a signed,
   CMS-specific 14-day session; GitHub credentials and repository tokens stay
   inside the Cloudflare Worker. */
(function installGitHubSubmit(){
  const SESSION_KEY='hctsui-github-submit-session-v1';
  const PENDING_KEY='hctsui-github-submit-pending-v1';
  const AUTO_KEY='hctsui-github-submit-after-login-v1';
  const DEFAULT_API='https://hctsui-website-worker.hctsui-math.workers.dev';
  const button=document.querySelector('#submitBatch');
  const manualButton=document.querySelector('#manualSubmitBatch');
  const loginButton=document.querySelector('#githubLogin');
  const logoutButton=document.querySelector('#githubLogout');
  const status=document.querySelector('#githubSubmitStatus');
  const issueStatus=document.querySelector('#githubIssueStatus');
  if(!button||!manualButton||!loginButton||!logoutButton||!status)return;

  const apiBase=()=>{
    const configured=String(site?.settings?.contact_form?.worker_url||'').trim();
    try{return new URL(configured||DEFAULT_API).origin}catch{return DEFAULT_API}
  };
  const readJson=(key)=>{try{return JSON.parse(localStorage.getItem(key)||'null')}catch{localStorage.removeItem(key);return null}};
  const session=()=>readJson(SESSION_KEY);
  const setStatus=(message,kind='')=>{status.className=`github-submit-status ${kind}`.trim();status.textContent=message};
  const showIssue=(html,kind='')=>{if(!issueStatus)return;issueStatus.className=`github-issue-status ${kind}`.trim();issueStatus.innerHTML=html;issueStatus.hidden=!html};
  const operationFingerprint=async(batch)=>{
    const bytes=new TextEncoder().encode(JSON.stringify({schema_version:batch.schema_version,operations:batch.operations}));
    const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
    return Array.from(digest,b=>b.toString(16).padStart(2,'0')).join('');
  };
  const requestId=()=>crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('')}`;

  function validationError(){
    const checks=[
      ['中英對照',typeof validateDictionary==='function'?validateDictionary():[]],
      ['人名連結',typeof validatePeopleDraft==='function'?validatePeopleDraft():[]],
      ['網站設定',typeof validateSiteSettingsDraft==='function'?validateSiteSettingsDraft():[]],
      ['標題欄位',typeof validateHeadingsDraft==='function'?validateHeadingsDraft():[]],
    ];
    for(const [label,errors] of checks)if(errors?.length)return `請先修正${label}：${errors[0]}`;
    return '';
  }

  function beginLogin(autoSubmit=false){
    if(autoSubmit)localStorage.setItem(AUTO_KEY,'1');
    else localStorage.removeItem(AUTO_KEY);
    location.assign(`${apiBase()}/cms/auth/start`);
  }

  function consumeLoginResult(){
    const params=new URLSearchParams(location.hash.replace(/^#/,''));
    if(!params.has('github_session')&&!params.has('github_error'))return false;
    const error=params.get('github_error');
    if(error){localStorage.removeItem(SESSION_KEY);setStatus(error,'error');flash(error)}
    else{
      const value={token:params.get('github_session'),login:params.get('github_login')||'hctsui',expires:Number(params.get('github_expires')||0)};
      localStorage.setItem(SESSION_KEY,JSON.stringify(value));
      setStatus(`已登入 ${value.login}；14 天內可直接送出`,'success');
      flash(`GitHub ${value.login} 登入成功`);
    }
    window.history.replaceState(null,'',location.pathname+location.search);
    return !error;
  }

  async function checkSession(){
    const saved=session();
    if(!saved?.token||!saved.expires||saved.expires*1000<=Date.now()){
      localStorage.removeItem(SESSION_KEY);
      loginButton.hidden=false;logoutButton.hidden=true;
      setStatus('尚未登入 GitHub');
      return false;
    }
    try{
      const response=await fetch(`${apiBase()}/cms/session`,{headers:{Authorization:`Bearer ${saved.token}`},cache:'no-store'});
      if(!response.ok)throw new Error('expired');
      const data=await response.json();
      saved.login=data.login||saved.login;saved.expires=data.expires||saved.expires;
      localStorage.setItem(SESSION_KEY,JSON.stringify(saved));
      loginButton.hidden=true;logoutButton.hidden=false;
      const until=new Date(saved.expires*1000).toLocaleDateString('zh-TW');
      setStatus(`已登入 ${saved.login}；登入有效至 ${until}`,'success');
      return true;
    }catch{
      localStorage.removeItem(SESSION_KEY);
      loginButton.hidden=false;logoutButton.hidden=true;
      setStatus('登入已過期，請重新登入 GitHub','error');
      return false;
    }
  }

  async function manualSubmit(){
    const error=validationError(),batch=payload();
    if(error)return flash(error);
    if(!batch.operations.length)return flash('尚無變更');
    const raw=JSON.stringify(batch),body=`### Batch payload / 批次資料\n\n\`\`\`json\n${raw}\n\`\`\``;
    const url=`${REPO}/issues/new?title=${encodeURIComponent(`[Website: Batch] ${new Date().toLocaleString('zh-TW')}`)}&body=${encodeURIComponent(body)}`;
    if(batch.operations.length<=3&&url.length<5500)return openIssue(url);
    try{
      const encoded=await encodeBatchForGitHub(batch);
      if(!await copyText(encoded.text))return;
      if(openIssue(`${REPO}/issues/new?template=batch-changes.yml`))flash(encoded.compressed?`已複製壓縮批次；請貼入唯一欄位`:'批次較大：已複製 JSON，請貼入唯一欄位');
    }catch(reason){flash(reason.message||String(reason))}
  }

  async function directSubmit(){
    const error=validationError(),batch=payload();
    if(error)return flash(error);
    if(!batch.operations.length)return flash('尚無變更');
    if(!await checkSession())return beginLogin(true);
    button.disabled=true;manualButton.disabled=true;button.textContent='正在安全送出…';
    try{
      const fingerprint=await operationFingerprint(batch);
      let pending=readJson(PENDING_KEY);
      if(!pending||pending.fingerprint!==fingerprint)pending={request_id:requestId(),fingerprint};
      localStorage.setItem(PENDING_KEY,JSON.stringify(pending));
      const saved=session();
      const response=await fetch(`${apiBase()}/cms/submit`,{
        method:'POST',headers:{'content-type':'application/json',Authorization:`Bearer ${saved.token}`},
        body:JSON.stringify({request_id:pending.request_id,payload:batch}),
      });
      const result=await response.json().catch(()=>({}));
      if(response.status===401){localStorage.removeItem(SESSION_KEY);return beginLogin(true)}
      if(!response.ok||!result.success)throw new Error(result.message||'送出失敗，請稍後重試');
      pending.issue=result.issue;pending.submitted_at=new Date().toISOString();
      localStorage.setItem(PENDING_KEY,JSON.stringify(pending));
      markSubmissionPending();
      document.querySelector('#confirmSubmitted')?.classList.remove('hidden');
      showIssue(`已建立修改請求 <a href="${esc(result.issue.url)}" target="_blank" rel="noopener">GitHub #${esc(result.issue.number)}</a>；系統正在檢查並更新網站。`,'success');
      flash(result.duplicate?'這份修改先前已送出，已接回原本的處理進度':'修改已安全送出，不必再貼到 GitHub');
      setTimeout(()=>refreshIssueStatus(),2500);
    }catch(reason){
      showIssue(`${esc(reason.message||String(reason))}；草稿仍完整保留，可重試或改用手動 Issue。`,'error');
      flash(reason.message||String(reason));
    }finally{
      button.disabled=false;manualButton.disabled=false;button.textContent='直接送出修改';
    }
  }

  async function refreshIssueStatus(){
    const pending=readJson(PENDING_KEY);
    if(!pending?.issue?.number)return;
    try{
      const response=await fetch(`https://api.github.com/repos/hctsui/hctsui.github.io/issues/${pending.issue.number}`,{headers:{Accept:'application/vnd.github+json'},cache:'no-store'});
      if(!response.ok)throw new Error();
      const issue=await response.json(),labels=(issue.labels||[]).map(label=>typeof label==='string'?label:label.name);
      const applied=labels.includes('website-form-applied');
      if(!applied&&issue.state!=='closed'){
        showIssue(`修改請求 <a href="${esc(pending.issue.url)}" target="_blank" rel="noopener">GitHub #${esc(pending.issue.number)}</a> 正在處理；本機草稿會先保留。`);
        return;
      }
      const current=await operationFingerprint(payload());
      if(current!==pending.fingerprint){
        showIssue(`GitHub #${esc(pending.issue.number)} 已完成；但你送出後又有新草稿，因此不會自動清除。請先送出新的修改。`,'success');
        document.querySelector('#confirmSubmitted')?.classList.add('hidden');
        return;
      }
      showIssue(`GitHub #${esc(pending.issue.number)} 已完成，網站正在部署。現在可以安全清除這批本機草稿。`,'success');
      const confirmButton=document.querySelector('#confirmSubmitted');
      if(confirmButton){confirmButton.classList.remove('hidden');confirmButton.textContent='處理完成：清除這批本機草稿'}
    }catch{showIssue(`已送出 GitHub #${esc(pending.issue.number)}；目前暫時讀不到處理狀態，本機草稿仍有保留。`)}
  }

  const baseClearSubmittedDraft=clearSubmittedDraft;
  clearSubmittedDraft=function(){
    if(typeof clearGeneralNotificationsDraft==='function')clearGeneralNotificationsDraft(false);
    localStorage.removeItem(PENDING_KEY);
    return baseClearSubmittedDraft();
  };

  button.onclick=directSubmit;
  manualButton.onclick=manualSubmit;
  loginButton.onclick=()=>beginLogin(false);
  logoutButton.onclick=()=>{localStorage.removeItem(SESSION_KEY);localStorage.removeItem(AUTO_KEY);checkSession();flash('已在這台裝置登出 GitHub 送出功能')};
  document.querySelector('#confirmSubmitted').onclick=async()=>{
    const pending=readJson(PENDING_KEY);
    if(!pending?.issue)return finishSuccessfulSubmission();
    await refreshIssueStatus();
    const current=await operationFingerprint(payload());
    if(current!==pending.fingerprint)return flash('送出後另有新草稿，為避免誤刪，請先送出新的修改');
    if(!confirm('確認清除已完成的這批本機草稿？'))return;
    clearSubmittedDraft();
  };

  const loggedIn=consumeLoginResult();
  checkSession().then(async()=>{
    await refreshIssueStatus();
    if(loggedIn&&localStorage.getItem(AUTO_KEY)==='1'){
      localStorage.removeItem(AUTO_KEY);
      directSubmit();
    }
  });
})();
