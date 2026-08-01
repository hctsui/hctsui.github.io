import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const source=await readFile(new URL('../integrations/contact-worker.js',import.meta.url),'utf8');
const module=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const worker=module.default;
const env={
  SITE_ORIGIN:'https://hctsui.github.io',
  ADMIN_URL:'https://hctsui.github.io/admin/',
  GITHUB_REPOSITORY:'hctsui/hctsui.github.io',
  CMS_ALLOWED_GITHUB_LOGIN:'hctsui',
  GITHUB_OAUTH_CLIENT_SECRET:'client-secret',
  GITHUB_TOKEN:'github-token',
};

const start=await worker.fetch(new Request('https://worker.example/cms/auth/start'),env);
assert.equal(start.status,302);
const authorization=new URL(start.headers.get('location'));
assert.equal(authorization.origin,'https://github.com');
assert.equal(authorization.searchParams.get('client_id'),'Ov23liuhyCd8KNHvlDLA');
assert.equal(authorization.searchParams.get('code_challenge_method'),'S256');
const cookie=start.headers.get('set-cookie').match(/^cms_oauth=([^;]+)/)[1];

globalThis.fetch=async(url)=>{
  const target=String(url);
  if(target==='https://github.com/login/oauth/access_token')return Response.json({access_token:'identity-token'});
  if(target==='https://api.github.com/user')return Response.json({login:'hctsui'});
  throw new Error(`Unexpected OAuth fetch: ${target}`);
};
const callbackUrl=new URL('https://worker.example/cms/auth/callback');
callbackUrl.searchParams.set('code','temporary-code');
callbackUrl.searchParams.set('state',authorization.searchParams.get('state'));
const callback=await worker.fetch(new Request(callbackUrl,{headers:{cookie:`cms_oauth=${cookie}`}}),env);
assert.equal(callback.status,302);
const fragment=new URLSearchParams(new URL(callback.headers.get('location')).hash.slice(1));
const session=fragment.get('github_session');
assert.ok(session);
assert.equal(fragment.get('github_login'),'hctsui');

const sessionResponse=await worker.fetch(new Request('https://worker.example/cms/session',{headers:{origin:env.SITE_ORIGIN,authorization:`Bearer ${session}`}}),env);
assert.equal(sessionResponse.status,200);
assert.equal((await sessionResponse.json()).login,'hctsui');

let createdBody='';
let createCount=0;
globalThis.fetch=async(url,options={})=>{
  const target=String(url);
  if(target.includes('/issues?'))return Response.json([]);
  if(target.endsWith('/issues')&&options.method==='POST'){
    createCount+=1;
    const body=JSON.parse(options.body);
    createdBody=body.body;
    assert.match(body.title,/^\[Website: Batch\]/);
    assert.match(body.body,/gzip-base64:/);
    return Response.json({number:77,html_url:'https://github.com/hctsui/hctsui.github.io/issues/77'},{status:201});
  }
  throw new Error(`Unexpected submit fetch: ${target}`);
};
const submission={request_id:'request_1234567890abcdef',payload:{schema_version:2,created_at:new Date().toISOString(),operations:[{op:'people',before:{schema_version:1,people:[]},after:{schema_version:1,people:[]}}]}};
const submitRequest=()=>new Request('https://worker.example/cms/submit',{method:'POST',headers:{origin:env.SITE_ORIGIN,authorization:`Bearer ${session}`,'content-type':'application/json'},body:JSON.stringify(submission)});
const submitted=await worker.fetch(submitRequest(),env);
assert.equal(submitted.status,201);
assert.equal((await submitted.json()).issue.number,77);
assert.equal(createCount,1);
assert.match(createdBody,/cms-request:request_1234567890abcdef/);

globalThis.fetch=async(url)=>{
  const target=String(url);
  if(target.includes('/issues?'))return Response.json([{number:77,html_url:'https://github.com/hctsui/hctsui.github.io/issues/77',body:createdBody}]);
  throw new Error(`Duplicate submission created another issue: ${target}`);
};
const duplicate=await worker.fetch(submitRequest(),env);
assert.equal(duplicate.status,200);
assert.equal((await duplicate.json()).duplicate,true);
assert.equal(createCount,1);

globalThis.fetch=async(url)=>{
  const target=String(url);
  if(target.endsWith('/issues/77'))return Response.json({number:77,title:'[Website: Batch] status test',html_url:'https://github.com/hctsui/hctsui.github.io/issues/77'});
  if(target.includes('/actions/workflows/process-website-batch.yml/runs'))return Response.json({workflow_runs:[{status:'completed',conclusion:'success',display_title:'[Website: Batch] status test',html_url:'https://github.com/hctsui/hctsui.github.io/actions/runs/100',created_at:'2026-08-01T00:00:00Z',updated_at:'2026-08-01T00:00:30Z'}]});
  if(target.includes('/commits?sha=cms'))return Response.json([{sha:'batch-commit',commit:{message:'Apply website batch from issue #77'}}]);
  if(target.includes('/actions/workflows/deploy-cms-pages.yml/runs'))return Response.json({workflow_runs:[{status:'completed',conclusion:'success',head_sha:'batch-commit',html_url:'https://github.com/hctsui/hctsui.github.io/actions/runs/101',created_at:'2026-08-01T00:00:31Z'}]});
  throw new Error(`Unexpected status fetch: ${target}`);
};
const statusResponse=await worker.fetch(new Request('https://worker.example/cms/status?issue=77',{headers:{origin:env.SITE_ORIGIN,authorization:`Bearer ${session}`}}),env);
assert.equal(statusResponse.status,200);
const statusData=await statusResponse.json();
assert.equal(statusData.stage,'completed');
assert.match(statusData.action_url,/actions\/runs\/101/);

const unauthorized=await worker.fetch(new Request('https://worker.example/cms/submit',{method:'POST',headers:{origin:env.SITE_ORIGIN,'content-type':'application/json'},body:JSON.stringify(submission)}),env);
assert.equal(unauthorized.status,401);

const analyticsUnauthorized=await worker.fetch(new Request('https://worker.example/cms/analytics?provider=cloudflare&range=7d',{headers:{origin:env.SITE_ORIGIN}}),env);
assert.equal(analyticsUnauthorized.status,401);
const analyticsMissing=await worker.fetch(new Request('https://worker.example/cms/analytics?provider=cloudflare&range=7d',{headers:{origin:env.SITE_ORIGIN,authorization:`Bearer ${session}`}}),env);
assert.equal(analyticsMissing.status,503);
assert.equal((await analyticsMissing.json()).code,'analytics_not_configured');

globalThis.fetch=async(url,options={})=>{
  assert.equal(String(url),'https://api.cloudflare.com/client/v4/graphql');
  assert.equal(options.headers.authorization,'Bearer analytics-token');
  const request=JSON.parse(options.body);
  assert.match(request.query,/rumPageloadEventsAdaptiveGroups/);
  assert.equal(request.variables.host,'hctsui.github.io');
  return Response.json({data:{viewer:{accounts:[{
    totals:[{count:42,sum:{visits:21}}],
    daily:[{dimensions:{date:'2026-08-01'},count:42,sum:{visits:21}}],
    pages:[{dimensions:{requestPath:'/en/'},count:30}],
    referrers:[{dimensions:{refererHost:'google.com'},count:11}],
    countries:[{dimensions:{countryName:'Japan'},count:18}],
    devices:[{dimensions:{deviceType:'mobile'},count:25}],
    browsers:[{dimensions:{userAgentBrowser:'Chrome'},count:20}],
  }]}}});
};
const cloudflareEnv={...env,CLOUDFLARE_ANALYTICS_API_TOKEN:'analytics-token',CLOUDFLARE_ACCOUNT_ID:'account-id'};
const cloudflareReport=await worker.fetch(new Request('https://worker.example/cms/analytics?provider=cloudflare&range=7d',{headers:{origin:env.SITE_ORIGIN,authorization:`Bearer ${session}`}}),cloudflareEnv);
assert.equal(cloudflareReport.status,200);
const cloudflareData=await cloudflareReport.json();
assert.equal(cloudflareData.summary.views,42);
assert.equal(cloudflareData.summary.visits,21);
assert.equal(cloudflareData.top_pages[0].label,'/en/');

const {privateKey}=generateKeyPairSync('rsa',{modulusLength:2048});
const serviceAccount=JSON.stringify({client_email:'analytics@example.iam.gserviceaccount.com',private_key:privateKey.export({type:'pkcs8',format:'pem'})});
globalThis.fetch=async(url,options={})=>{
  const target=String(url);
  if(target==='https://oauth2.googleapis.com/token'){
    assert.match(String(options.body),/jwt-bearer/);
    return Response.json({access_token:'google-read-token',expires_in:3600});
  }
  if(target==='https://analyticsdata.googleapis.com/v1beta/properties/123456789:runReport'){
    assert.equal(options.headers.authorization,'Bearer google-read-token');
    const request=JSON.parse(options.body),dimension=request.dimensions?.[0]?.name;
    const metricValues=[{value:'50'},{value:'24'},{value:'19'}];
    const labels={date:'20260801',pagePath:'/zh/',sessionSource:'google',country:'Taiwan',deviceCategory:'mobile',browser:'Safari'};
    return Response.json({rows:[dimension?{dimensionValues:[{value:labels[dimension]}],metricValues}:{metricValues}]});
  }
  throw new Error(`Unexpected analytics fetch: ${target}`);
};
const googleEnv={...env,GOOGLE_ANALYTICS_PROPERTY_ID:'123456789',GOOGLE_ANALYTICS_SERVICE_ACCOUNT_JSON:serviceAccount};
const googleReport=await worker.fetch(new Request('https://worker.example/cms/analytics?provider=google&range=30d',{headers:{origin:env.SITE_ORIGIN,authorization:`Bearer ${session}`}}),googleEnv);
assert.equal(googleReport.status,200);
const googleData=await googleReport.json();
assert.equal(googleData.provider,'google');
assert.equal(googleData.summary.users,19);
assert.equal(googleData.trend[0].date,'2026-08-01');
assert.equal(googleData.devices[0].label,'mobile');

const contactBot=await worker.fetch(new Request('https://worker.example/',{method:'POST',headers:{origin:env.SITE_ORIGIN,'content-type':'application/json'},body:JSON.stringify({botcheck:'yes'})}),env);
assert.equal(contactBot.status,200);
