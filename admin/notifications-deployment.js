'use strict';

/* Deployment polling for the Admin notification center.
 * The notification UI remains in notifications.js; this bridge only replaces
 * its anonymous GitHub API request with the authenticated Cloudflare Worker.
 */
(function installWorkerDeploymentPolling(){
  if(window.__hctsuiWorkerDeploymentPollingInstalled)return;
  window.__hctsuiWorkerDeploymentPollingInstalled=true;

  const SESSION_KEY='hctsui-github-submit-session-v1';
  const DEFAULT_WORKER='https://hctsui-website-worker.hctsui-math.workers.dev';
  const POLL_MS=5000;
  let workerOriginPromise=null;
  let installed=false;

  function savedSession(){
    try{return JSON.parse(localStorage.getItem(SESSION_KEY)||'null')}catch{return null}
  }

  async function workerOrigin(){
    if(workerOriginPromise)return workerOriginPromise;
    workerOriginPromise=(async()=>{
      let configured='';
      try{
        const response=await fetch('../content/media-config.json',{cache:'no-store'});
        if(response.ok)configured=String((await response.json())?.worker_origin||'').trim();
      }catch{}
      configured=String(window.site?.settings?.contact_form?.worker_url||configured||DEFAULT_WORKER).trim();
      try{return new URL(configured).origin}catch{return DEFAULT_WORKER}
    })();
    return workerOriginPromise;
  }

  async function fetchDeploymentThroughWorker(){
    if(typeof deploymentRequestInFlight==='undefined'||typeof deploymentState==='undefined')return;
    if(deploymentRequestInFlight)return;
    deploymentRequestInFlight=true;
    deploymentState={loading:!deploymentState.run,error:'',run:deploymentState.run};
    if(typeof renderDeploymentCard==='function')renderDeploymentCard();
    try{
      const session=savedSession();
      if(!session?.token)throw new Error('請重新登入 GitHub');
      const origin=await workerOrigin();
      const response=await fetch(`${origin}/cms/deployment`,{
        headers:{authorization:`Bearer ${session.token}`,accept:'application/json'},
        cache:'no-store'
      });
      const result=await response.json().catch(()=>({}));
      if(response.status===401)throw new Error('GitHub 登入已過期，請重新登入');
      if(!response.ok||result.success===false)throw new Error(result.message||`部署狀態服務錯誤（${response.status}）`);
      deploymentState={loading:false,error:'',run:result.run||null};
    }catch(error){
      deploymentState={loading:false,error:String(error?.message||error),run:null};
    }finally{
      deploymentRequestInFlight=false;
      if(typeof renderDeploymentCard==='function')renderDeploymentCard();
    }
  }

  function stopWorkerPolling(){
    if(typeof deploymentPollTimer!=='undefined'&&deploymentPollTimer){
      clearInterval(deploymentPollTimer);
      deploymentPollTimer=null;
    }
  }

  function startWorkerDeploymentPolling(){
    stopWorkerPolling();
    if(document.hidden)return;
    fetchDeploymentThroughWorker();
    if(typeof deploymentPollTimer==='undefined')return;
    deploymentPollTimer=setInterval(()=>{
      const panel=document.querySelector('[data-notification-panel]');
      if(document.hidden||!panel||panel.classList.contains('hidden')){
        stopWorkerPolling();
        return;
      }
      fetchDeploymentThroughWorker();
    },POLL_MS);
  }

  function install(){
    if(installed)return true;
    if(typeof window.fetchDeploymentStatus!=='function' || typeof window.startDeploymentPolling!=='function')return false;
    try{fetchDeploymentStatus=fetchDeploymentThroughWorker}catch{}
    try{startDeploymentPolling=startWorkerDeploymentPolling}catch{}
    try{stopDeploymentPolling=stopWorkerPolling}catch{}
    window.fetchDeploymentStatus=fetchDeploymentThroughWorker;
    window.startDeploymentPolling=startWorkerDeploymentPolling;
    window.stopDeploymentPolling=stopWorkerPolling;
    installed=true;
    return true;
  }

  let attempts=0;
  const timer=setInterval(()=>{
    attempts+=1;
    if(install()||attempts>=200)clearInterval(timer);
  },25);
  install();

  document.addEventListener('visibilitychange',()=>{
    if(!installed&&!install())return;
    const panel=document.querySelector('[data-notification-panel]');
    if(document.hidden){stopWorkerPolling();return;}
    if(panel&&!panel.classList.contains('hidden'))startWorkerDeploymentPolling();
  });
})();
