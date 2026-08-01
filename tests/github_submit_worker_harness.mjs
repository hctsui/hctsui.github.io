import assert from 'node:assert/strict';
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

const unauthorized=await worker.fetch(new Request('https://worker.example/cms/submit',{method:'POST',headers:{origin:env.SITE_ORIGIN,'content-type':'application/json'},body:JSON.stringify(submission)}),env);
assert.equal(unauthorized.status,401);

const contactBot=await worker.fetch(new Request('https://worker.example/',{method:'POST',headers:{origin:env.SITE_ORIGIN,'content-type':'application/json'},body:JSON.stringify({botcheck:'yes'})}),env);
assert.equal(contactBot.status,200);
