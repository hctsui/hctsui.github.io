'use strict';

const ARXIV_SUGGESTIONS_DRAFT_KEY = 'hctsui-arxiv-suggestions-draft-v1';
let arxivSuggestionsBase = null;
let arxivSuggestionsDraft = null;
let arxivSuggestionsReady = false;

function arxivCleanId(value) {
  return String(value || '')
    .trim()
    .replace(/^https?:\/\/(?:export\.)?arxiv\.org\/(?:abs|pdf)\//i, '')
    .replace(/\.pdf$/i, '')
    .replace(/v\d+$/i, '');
}

function normalizeArxivSuggestions(value) {
  const raw = value && typeof value === 'object' ? value : {};
  const search = raw.search && typeof raw.search === 'object' ? raw.search : {};
  const ignored = [];
  for (const item of Array.isArray(raw.ignored_ids) ? raw.ignored_ids : []) {
    const id = arxivCleanId(item);
    if (id && !ignored.includes(id)) ignored.push(id);
  }
  const ignoredSet = new Set(ignored);
  const suggestions = [];
  const seen = new Set();
  for (const item of Array.isArray(raw.suggestions) ? raw.suggestions : []) {
    if (!item || typeof item !== 'object') continue;
    const id = arxivCleanId(item.arxiv_id || item.id);
    if (!id || seen.has(id) || ignoredSet.has(id)) continue;
    seen.add(id);
    suggestions.push({
      arxiv_id: id,
      title: String(item.title || '').trim(),
      authors: (Array.isArray(item.authors) ? item.authors : []).map(x => String(x || '').trim()).filter(Boolean),
      summary: String(item.summary || '').trim(),
      published: String(item.published || '').trim(),
      updated: String(item.updated || '').trim(),
      primary_category: String(item.primary_category || '').trim(),
      categories: (Array.isArray(item.categories) ? item.categories : []).map(x => String(x || '').trim()).filter(Boolean),
      arxiv_url: String(item.arxiv_url || `https://arxiv.org/abs/${id}`).trim(),
      pdf_url: String(item.pdf_url || `https://arxiv.org/pdf/${id}`).trim(),
      doi: String(item.doi || '').trim(),
      journal_ref: String(item.journal_ref || '').trim(),
      discovered_at: String(item.discovered_at || item.published || '').trim(),
      starred: Boolean(item.starred),
      read: Boolean(item.read),
    });
  }
  suggestions.sort((a, b) => String(b.published).localeCompare(String(a.published)) || b.arxiv_id.localeCompare(a.arxiv_id));
  return {
    schema_version: 1,
    search: {
      author_query: String(search.author_query || 'Hung-Chun Tsui').trim(),
      author_names: (Array.isArray(search.author_names) ? search.author_names : ['Hung-Chun Tsui']).map(x => String(x || '').trim()).filter(Boolean),
      max_results: Math.max(1, Math.min(100, Number.parseInt(search.max_results, 10) || 30)),
    },
    ignored_ids: ignored,
    checked_at: String(raw.checked_at || '').trim(),
    suggestions,
  };
}

function arxivSuggestionSignature(value) {
  return JSON.stringify(normalizeArxivSuggestions(value));
}

function saveArxivSuggestionsDraft() {
  if (!arxivSuggestionsReady) return;
  if (arxivSuggestionSignature(arxivSuggestionsDraft) === arxivSuggestionSignature(arxivSuggestionsBase)) {
    localStorage.removeItem(ARXIV_SUGGESTIONS_DRAFT_KEY);
  } else {
    localStorage.setItem(ARXIV_SUGGESTIONS_DRAFT_KEY, JSON.stringify({
      base_signature: arxivSuggestionSignature(arxivSuggestionsBase),
      draft: arxivSuggestionsDraft,
    }));
  }
  renderNotificationCenter();
  if (typeof renderPreview === 'function') renderPreview(false);
}

function clearArxivSuggestionsDraft(refresh = true) {
  localStorage.removeItem(ARXIV_SUGGESTIONS_DRAFT_KEY);
  if (arxivSuggestionsBase) arxivSuggestionsDraft = clone(arxivSuggestionsBase);
  if (refresh) {
    renderNotificationCenter();
    if (typeof renderPreview === 'function') renderPreview(false);
  }
}

function arxivSuggestionsOperation() {
  if (!arxivSuggestionsReady || arxivSuggestionSignature(arxivSuggestionsDraft) === arxivSuggestionSignature(arxivSuggestionsBase)) return null;
  return {
    op: 'arxiv_suggestions',
    before: clone(arxivSuggestionsBase),
    after: clone(arxivSuggestionsDraft),
  };
}

function existingArxivIds() {
  const ids = new Set();
  const data = typeof effectiveSite === 'function' ? effectiveSite() : site;
  for (const item of data?.publications || []) {
    const id = arxivCleanId(item.arxiv);
    if (id) ids.add(id);
    for (const link of item.links || []) {
      const candidate = arxivCleanId(link?.url);
      if (/^(?:[a-z-]+\/\d{7}|\d{4}\.\d{4,5})$/i.test(candidate)) ids.add(candidate);
    }
  }
  return ids;
}

function pendingArxivSuggestions() {
  if (!arxivSuggestionsReady) return [];
  const existing = existingArxivIds();
  const ignored = new Set(arxivSuggestionsDraft.ignored_ids || []);
  return (arxivSuggestionsDraft.suggestions || []).filter(item => !existing.has(item.arxiv_id) && !ignored.has(item.arxiv_id));
}

function englishAuthorLine(authors) {
  const list = (authors || []).filter(Boolean);
  if (list.length <= 1) return list[0] || '';
  if (list.length === 2) return `${list[0]} and ${list[1]}`;
  return `${list.slice(0, -1).join(', ')}, and ${list.at(-1)}`;
}

function arxivSuggestionPublication(item) {
  const date = String(item.published || '').slice(0, 10) || new Date().toISOString().slice(0, 10);
  const arxivUrl = item.arxiv_url || `https://arxiv.org/abs/${item.arxiv_id}`;
  const pdfUrl = item.pdf_url || `https://arxiv.org/pdf/${item.arxiv_id}`;
  const categories = site?.settings?.categories || [];
  const category = categories.find(x => x.kind === 'publication' && x.page_id === 'publications');
  const record = {
    id: newId('publication', date, item.title),
    type: 'publication',
    date,
    year: Number(date.slice(0, 4)),
    order: 999,
    arxiv: item.arxiv_id,
    primary_category: item.primary_category || '',
    title: { en: item.title, zh: '' },
    authors: { en: englishAuthorLine(item.authors), zh: '' },
    venue: {
      en: item.journal_ref || `arXiv:${item.arxiv_id}`,
      zh: `arXiv:${item.arxiv_id}`,
    },
    arxiv_url: arxivUrl,
    pdf_url: pdfUrl,
    doi_url: item.doi ? `https://doi.org/${item.doi}` : '',
    journal_url: '',
    code_url: '',
    bibtex: '',
    bibitem: '',
    links: [
      { label: { en: 'arXiv', zh: 'arXiv' }, url: arxivUrl },
      { label: { en: 'PDF', zh: 'PDF' }, url: pdfUrl },
      ...(item.doi ? [{ label: { en: 'DOI', zh: 'DOI' }, url: `https://doi.org/${item.doi}` }] : []),
    ],
    group_id: 'preprints',
  };
  if (category?.id) record.category_id = category.id;
  return record;
}


const GENERAL_NOTIFICATIONS_DRAFT_KEY = 'hctsui-general-notifications-draft-v1';
let generalNotificationsBase = null;
let generalNotificationsDraft = null;
let generalNotificationsReady = false;
let notificationSearch = '';
let notificationUnreadOnly = false;
let deploymentState = { loading: true, error: '', run: null };
let deploymentPollTimer = null;
let deploymentRequestInFlight = false;

function normalizeGeneralNotifications(value) {
  const source = value && typeof value === 'object' ? value : {};
  const rows = [];
  const seen = new Set();
  for (const raw of Array.isArray(source.notifications) ? source.notifications : []) {
    if (!raw || typeof raw !== 'object') continue;
    const key = String(raw.key || '').trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    rows.push({
      id: String(raw.id || key).trim(),
      key,
      type: String(raw.type || 'system').trim(),
      title: String(raw.title || '').trim(),
      message: String(raw.message || '').trim(),
      created_at: String(raw.created_at || '').trim(),
      updated_at: String(raw.updated_at || raw.created_at || '').trim(),
      starred: Boolean(raw.starred),
      read: Boolean(raw.read),
      status: String(raw.status || 'open') === 'resolved' ? 'resolved' : 'open',
      source_url: String(raw.source_url || '').trim(),
      payload: raw.payload && typeof raw.payload === 'object' ? clone(raw.payload) : {},
      actions: (Array.isArray(raw.actions) ? raw.actions : []).filter(x => x && x.id && x.label).map(x => ({ id: String(x.id), label: String(x.label) })),
    });
  }
  rows.sort((a,b) => Number(b.starred)-Number(a.starred) || String(b.updated_at).localeCompare(String(a.updated_at)) || String(b.created_at).localeCompare(String(a.created_at)));
  return {
    schema_version: 1,
    retention_days: Math.max(1, Math.min(3650, Number.parseInt(source.retention_days,10) || 60)),
    notifications: rows,
  };
}

function generalNotificationSignature(value) { return JSON.stringify(normalizeGeneralNotifications(value)); }
function generalNotificationsDirty() { return generalNotificationsReady && generalNotificationSignature(generalNotificationsDraft) !== generalNotificationSignature(generalNotificationsBase); }
function saveGeneralNotificationsDraft() {
  if (!generalNotificationsReady) return;
  if (!generalNotificationsDirty()) localStorage.removeItem(GENERAL_NOTIFICATIONS_DRAFT_KEY);
  else localStorage.setItem(GENERAL_NOTIFICATIONS_DRAFT_KEY, JSON.stringify({ base_signature: generalNotificationSignature(generalNotificationsBase), draft: generalNotificationsDraft }));
  renderNotificationCenter();
  if (typeof renderPreview === 'function') renderPreview(false);
}
function clearGeneralNotificationsDraft(refresh=true) {
  localStorage.removeItem(GENERAL_NOTIFICATIONS_DRAFT_KEY);
  if (generalNotificationsBase) generalNotificationsDraft = clone(generalNotificationsBase);
  if (refresh) { renderNotificationCenter(); if (typeof renderPreview === 'function') renderPreview(false); }
}
function notificationsOperation() {
  if (!generalNotificationsDirty()) return null;
  return { op: 'notifications', before: clone(generalNotificationsBase), after: clone(generalNotificationsDraft) };
}

function addArxivSuggestionToDraft(id) {
  const item = pendingArxivSuggestions().find(x => x.arxiv_id === id);
  if (!item) return flash('找不到這筆 arXiv 通知，請重新整理');
  const record = arxivSuggestionPublication(item);
  queueOperation({ op: 'add', type: 'publication', after: record, notes: ['由 arXiv 通知建立；請確認中文題目、中文作者與 PDF 連結'] });
  const operation = contentOps().find(op => op.op === 'add' && op.after?.id === record.id);
  const index = draft.indexOf(operation);
  if (operation && index >= 0) { openEditor('publication', operation.after, { draftIndex: index, draftOp: 'add' }); switchTab('add'); }
  markArxivRead(id, true);
  renderNotificationCenter();
  flash('已加入論文草稿，請確認中英文資料後再送出');
}

function ignoreArxivSuggestion(id) {
  if (!arxivSuggestionsReady) return;
  const clean = arxivCleanId(id);
  if (!clean || arxivSuggestionsDraft.ignored_ids.includes(clean)) return;
  arxivSuggestionsDraft.ignored_ids.push(clean);
  arxivSuggestionsDraft.suggestions = arxivSuggestionsDraft.suggestions.filter(x => x.arxiv_id !== clean);
  saveArxivSuggestionsDraft();
  flash('已加入忽略草稿；送出批次後才會永久忽略');
}
function restoreIgnoredArxivSuggestions() { clearArxivSuggestionsDraft(true); flash('已復原本次 arXiv 忽略草稿'); }
function arxivDateLabel(value) {
  const text = String(value || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return text || '日期不明';
  const [year, month, day] = text.split('-'); return `${year}/${Number(month)}/${Number(day)}`;
}
function arxivItem(id) { return (arxivSuggestionsDraft?.suggestions || []).find(x => x.arxiv_id === arxivCleanId(id)); }
function toggleArxivStar(id) { const item=arxivItem(id); if(!item)return; item.starred=!item.starred; saveArxivSuggestionsDraft(); }
function markArxivRead(id, value=true) { const item=arxivItem(id); if(!item)return; item.read=Boolean(value); saveArxivSuggestionsDraft(); }

function generalItem(id) { return (generalNotificationsDraft?.notifications || []).find(x => x.id === id); }
function toggleGeneralStar(id) { const item=generalItem(id); if(!item)return; item.starred=!item.starred; item.updated_at=new Date().toISOString(); saveGeneralNotificationsDraft(); }
function markGeneralRead(id, value=true) { const item=generalItem(id); if(!item)return; item.read=Boolean(value); item.updated_at=new Date().toISOString(); saveGeneralNotificationsDraft(); }
function deleteGeneralNotification(id) { if(!generalNotificationsReady)return; generalNotificationsDraft.notifications=generalNotificationsDraft.notifications.filter(x=>x.id!==id); saveGeneralNotificationsDraft(); flash('已加入刪除草稿；送出批次後才會永久刪除'); }
function resolveGeneralNotification(id) { const item=generalItem(id); if(!item)return; item.status='resolved'; item.read=true; item.updated_at=new Date().toISOString(); saveGeneralNotificationsDraft(); flash('已標記為已處理；送出批次後生效'); }
function clearReadGeneralNotifications() { if(!generalNotificationsReady)return; generalNotificationsDraft.notifications=generalNotificationsDraft.notifications.filter(x=>x.starred || !x.read); for(const item of arxivSuggestionsDraft.suggestions||[])if(item.read&&!item.starred)item.read=false; saveGeneralNotificationsDraft(); saveArxivSuggestionsDraft(); flash('已刪除一般已讀通知；arXiv 已讀狀態已重設'); }

function notificationTypeLabel(type) {
  return ({arxiv:'arXiv 新論文',publication_status:'正式出版',broken_link:'失效連結',contact:'聯絡留言',system:'系統'})[type] || type;
}
function notificationEmoji(type) { return ({arxiv:'📄',publication_status:'🎓',broken_link:'⚠️',contact:'📨',system:'⚙️'})[type] || '🔔'; }
function notificationDate(value) { const d=new Date(value); return Number.isNaN(d.getTime())?'日期不明':d.toLocaleString('zh-TW',{year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
function matchesNotification(item) {
  const q=notificationSearch.trim().toLocaleLowerCase();
  if (notificationUnreadOnly && item.read) return false;
  if (!q) return true;
  return [item.title,item.message,item.type,item.searchText].join(' ').toLocaleLowerCase().includes(q);
}

function publishFromNotification(id) {
  const notice=generalItem(id); if(!notice)return flash('找不到這筆出版通知');
  const entryId=String(notice.payload?.entry_id||'');
  const data=typeof effectiveSite==='function'?effectiveSite():site;
  const current=(data.publications||[]).find(x=>x.id===entryId);
  if(!current)return flash('找不到原本的預印本，可能已經被修改或刪除');
  const updated=clone(current), p=notice.payload||{};
  updated.group_id='journal-articles'; updated.category_id='publication-journal-articles';
  if(p.year){updated.year=Number(p.year); if(updated.date)updated.date=`${p.year}-01-01`;}
  updated.doi_url=String(p.doi_url||p.source_url||notice.source_url||'');
  updated.journal_url=String(p.journal_url||updated.doi_url||'');
  const journal=[p.journal,p.volume?`vol. ${p.volume}`:'',p.issue?`no. ${p.issue}`:'',p.pages||'',p.year||''].filter(Boolean).join(', ');
  if(journal){updated.venue=updated.venue||{en:'',zh:''};updated.venue.en=journal;updated.venue.zh=journal;}
  updated.links=Array.isArray(updated.links)?updated.links:[];
  if(updated.doi_url&&!updated.links.some(x=>String(x?.label?.en||'').toUpperCase()==='DOI'))updated.links.push({label:{en:'DOI',zh:'DOI'},url:updated.doi_url});
  queueOperation({op:'update',type:'publication',id:updated.id,before:clone(current),after:updated,notes:['由 Crossref 正式出版通知建立；請人工確認期刊卷期頁碼']});
  markGeneralRead(id,true); notice.status='resolved'; saveGeneralNotificationsDraft();
  const operation=contentOps().find(op=>op.op==='update'&&op.after?.id===updated.id); const index=draft.indexOf(operation);
  if(operation&&index>=0){openEditor('publication',operation.after,{draftIndex:index,draftOp:'update'});switchTab('add');}
  flash('已建立 Published 修改草稿，請確認資料後送出');
}

function openNotificationTarget(id) {
  const notice=generalItem(id); if(!notice)return;
  markGeneralRead(id,true);
  const p=notice.payload||{}, type=String(p.target_type||''), entryId=String(p.entry_id||'');
  if(type==='person'&&typeof openPeopleRecord==='function'){switchTab('dictionary');openPeopleRecord(entryId);return;}
  if(type==='site_settings'){switchTab('siteSettings');if(typeof openSiteSettingsSection==='function')openSiteSettingsSection('footer');else if(typeof renderSiteSettings==='function')renderSiteSettings();return;}
  const data=typeof effectiveSite==='function'?effectiveSite():site;
  const section=type==='publication'?'publications':(type==='honor'?'honors':type==='teaching'?'teaching':type==='conference'||type==='talk'||type==='visit'||type==='organization'?'activities':'profile_items');
  const row=(data?.[section]||[]).find(x=>x.id===entryId);
  if(row){openEditor(type,row);switchTab('add');flash(`已開啟 ${p.field||'連結'} 欄位所在項目`);} else flash('找不到原項目，請從項目列表搜尋');
}

function deploymentHtml() {
  if(deploymentState.loading)return '<article class="notification-item deployment-card" data-deployment-card><h3>⏳ 正在讀取部署狀態…</h3></article>';
  if(deploymentState.error)return `<article class="notification-item deployment-card" data-deployment-card><h3>⚠️ 無法讀取部署狀態</h3><p class="notification-summary">${esc(deploymentState.error)}</p><div class="notification-actions"><a class="button" href="${REPO}/actions/workflows/deploy-cms-pages.yml" target="_blank" rel="noopener">開啟 GitHub Actions</a></div></article>`;
  const run=deploymentState.run;if(!run)return '<article class="notification-item deployment-card" data-deployment-card><h3>⚙️ 尚無部署紀錄</h3></article>';
  const inProgress=run.status!=='completed'; const success=run.conclusion==='success';
  const title=inProgress?'⏳ 部署中…':success?'✅ 網站部署成功！':'❌ 部署失敗';
  return `<article class="notification-item deployment-card ${success?'deployment-success':inProgress?'deployment-running':'deployment-failed'}" data-deployment-card><h3>${title}</h3><div class="notification-meta"><span>${esc(notificationDate(run.updated_at||run.created_at))}</span><span>${esc(String(run.head_sha||'').slice(0,7))}</span></div><div class="notification-actions"><a class="button" href="${esc(run.html_url||`${REPO}/actions`)}" target="_blank" rel="noopener">檢視 Log</a>${!inProgress&&!success?`<a class="button primary" href="${esc(run.html_url||`${REPO}/actions`)}" target="_blank" rel="noopener">前往 GitHub 重新執行</a>`:''}</div></article>`;
}

function renderDeploymentCard(){
  const current=document.querySelector('[data-deployment-card]');if(!current)return;
  const template=document.createElement('template');template.innerHTML=deploymentHtml().trim();
  current.replaceWith(template.content.firstElementChild);
}

function arxivCards() {
  return pendingArxivSuggestions().map(item=>({
    id:`arxiv:${item.arxiv_id}`,type:'arxiv',title:item.title||item.arxiv_id,message:item.summary||'',created_at:item.discovered_at||item.published,updated_at:item.updated||item.published,starred:Boolean(item.starred),read:Boolean(item.read),searchText:`${englishAuthorLine(item.authors)} ${item.arxiv_id} ${item.primary_category}`,_arxiv:item,
  }));
}
function generalCards(){return (generalNotificationsDraft?.notifications||[]).filter(x=>x.status==='open').map(x=>({...x,searchText:`${x.payload?.entry_id||''} ${x.payload?.url||''}`}));}
function allNotificationCards(){return [...arxivCards(),...generalCards()].sort((a,b)=>Number(b.starred)-Number(a.starred)||String(b.updated_at||b.created_at).localeCompare(String(a.updated_at||a.created_at)));}

function cardHtml(item){
  const star=`<button class="notification-state-button notification-star-button ${item.starred?'starred':''}" type="button" title="${item.starred?'取消星號':'加星號'}" ${item.type==='arxiv'?`data-arxiv-star="${esc(item._arxiv.arxiv_id)}"`:`data-general-star="${esc(item.id)}"`}>${item.starred?'★ 已加星號':'☆ 加星號'}</button>`;
  const read=`<button class="notification-state-button" type="button" title="${item.read?'標記未讀':'標記已讀'}" ${item.type==='arxiv'?`data-arxiv-read="${esc(item._arxiv.arxiv_id)}" data-next="${item.read?'0':'1'}"`:`data-general-read="${esc(item.id)}" data-next="${item.read?'0':'1'}"`}>${item.read?'● 標記未讀':'○ 標記已讀'}</button>`;
  let actions='';
  if(item.type==='arxiv'){const a=item._arxiv;actions=`<button class="button primary" type="button" data-arxiv-add="${esc(a.arxiv_id)}">加入新增草稿</button><button class="button" type="button" data-arxiv-ignore="${esc(a.arxiv_id)}">忽略</button><a class="button" href="${esc(a.arxiv_url)}" target="_blank" rel="noopener">查看 arXiv</a>`;}
  else if(item.type==='publication_status')actions=`<button class="button primary" type="button" data-publish-notification="${esc(item.id)}">轉為 Published</button>${item.source_url?`<a class="button" href="${esc(item.source_url)}" target="_blank" rel="noopener">查看 DOI</a>`:''}`;
  else if(item.type==='broken_link')actions=`<button class="button primary" type="button" data-open-target="${esc(item.id)}">前往修改</button>${item.source_url?`<a class="button" href="${esc(item.source_url)}" target="_blank" rel="noopener">測試連結</a>`:''}`;
  else if(item.type==='contact')actions=`<a class="button primary" href="https://mail.google.com/mail/u/0/#inbox" target="_blank" rel="noopener">開啟 Email 收件匣</a><button class="button" type="button" data-general-resolve="${esc(item.id)}">標記為已處理</button>`;
  else if(item.source_url)actions=`<a class="button" href="${esc(item.source_url)}" target="_blank" rel="noopener">查看來源</a>`;
  if(item.type!=='arxiv')actions+=`<button class="button danger" type="button" data-general-delete="${esc(item.id)}">刪除</button>`;
  const author=item.type==='arxiv'?`<div class="muted">${esc(englishAuthorLine(item._arxiv.authors))}</div>`:'';
  return `<article class="notification-item ${item.read?'notification-read':'notification-unread'}"><div class="notification-item-head"><div><div class="notification-meta"><span class="tag">${notificationEmoji(item.type)} ${esc(notificationTypeLabel(item.type))}</span><span>${esc(notificationDate(item.created_at||item.updated_at))}</span></div><h3>${esc(item.title)}</h3></div><div class="notification-icons">${star}${read}</div></div>${author}${item.message?`<p class="notification-summary">${esc(item.message)}</p>`:''}<div class="notification-actions">${actions}</div></article>`;
}

function ensureNotificationUi(){
  const actions=document.querySelector('.header-actions');if(!actions)return null;
  let button=actions.querySelector('[data-notification-button]');
  if(!button){button=document.createElement('button');button.type='button';button.className='button';button.dataset.notificationButton='';button.innerHTML='通知 <span class="notification-count" data-notification-count>0</span>';const guide=[...actions.querySelectorAll('a')].find(a=>a.getAttribute('href')==='guide.html');guide?actions.insertBefore(button,guide):actions.prepend(button);}
  let panel=document.querySelector('[data-notification-panel]');if(!panel){panel=document.createElement('section');panel.className='notification-panel panel hidden';panel.dataset.notificationPanel='';actions.after(panel);}
  button.onclick=()=>{panel.classList.toggle('hidden');const open=!panel.classList.contains('hidden');button.classList.toggle('primary',open);if(open)startDeploymentPolling();else stopDeploymentPolling();};
  panel.onclick=event=>{const t=event.target.closest('button,a');if(!t)return;
    if(t.dataset.arxivAdd)addArxivSuggestionToDraft(t.dataset.arxivAdd);
    else if(t.dataset.arxivIgnore)ignoreArxivSuggestion(t.dataset.arxivIgnore);
    else if(t.dataset.arxivRestoreIgnored!==undefined)restoreIgnoredArxivSuggestions();
    else if(t.dataset.arxivStar)toggleArxivStar(t.dataset.arxivStar);
    else if(t.dataset.arxivRead)markArxivRead(t.dataset.arxivRead,t.dataset.next==='1');
    else if(t.dataset.generalStar)toggleGeneralStar(t.dataset.generalStar);
    else if(t.dataset.generalRead)markGeneralRead(t.dataset.generalRead,t.dataset.next==='1');
    else if(t.dataset.generalDelete)deleteGeneralNotification(t.dataset.generalDelete);
    else if(t.dataset.generalResolve)resolveGeneralNotification(t.dataset.generalResolve);
    else if(t.dataset.publishNotification)publishFromNotification(t.dataset.publishNotification);
    else if(t.dataset.openTarget)openNotificationTarget(t.dataset.openTarget);
    else if(t.id==='clearReadNotifications')clearReadGeneralNotifications();
    else if(t.id==='resetNotificationDrafts'){clearGeneralNotificationsDraft(false);clearArxivSuggestionsDraft(false);renderNotificationCenter();if(typeof renderPreview==='function')renderPreview(false);}
  };
  panel.oninput=event=>{if(event.target.id==='notificationSearch'){notificationSearch=event.target.value;renderNotificationCenter();}};
  panel.onchange=event=>{if(event.target.id==='notificationUnreadOnly'){notificationUnreadOnly=event.target.checked;renderNotificationCenter();}};
  return {button,panel};
}

function installNotificationStyles(){if(document.querySelector('style[data-notification-style]'))return;const style=document.createElement('style');style.dataset.notificationStyle='';style.textContent=`
.notification-count{display:inline-grid;place-items:center;min-width:1.45rem;height:1.45rem;margin-left:.3rem;padding:0 .36rem;border-radius:999px;background:#8d493d;color:#fff;font-size:.72rem;font-weight:900}[data-notification-button].primary .notification-count{background:#fff;color:#2d2926}
.notification-panel{margin:0 0 18px;padding:16px 18px}.notification-panel-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:14px}.notification-panel-head h2{margin:0;font-size:1.25rem}.notification-toolbar{display:grid;grid-template-columns:minmax(220px,1fr) auto;gap:10px;margin:12px 0}.notification-toolbar input[type=search]{width:100%}.notification-toolbar-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.notification-list{display:grid;gap:10px}.notification-item{padding:14px;border:1px solid #ded3ca;border-radius:13px;background:#fcfaf8}.notification-item.notification-unread{border-left:4px solid #8d493d}.notification-item.notification-read{opacity:.82}.notification-item-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.notification-item h3{margin:2px 0 5px;font-size:1rem}.notification-icons{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.notification-state-button{appearance:none;border:1px solid #d8cbc1;border-radius:999px;background:#fff;padding:6px 9px;font-family:inherit;font-size:.76rem;font-weight:700;line-height:1.1;cursor:pointer;color:#645a54}.notification-state-button:hover,.notification-state-button:focus-visible{border-color:#8d493d;color:#7d3e34;outline:none}.notification-state-button.starred{border-color:#d9a441;background:#fff7df;color:#8c5b00}.notification-meta{display:flex;gap:8px;flex-wrap:wrap;margin:.2rem 0;color:#766c65;font-size:.78rem}.notification-summary{margin:.65rem 0;color:#5f554f;line-height:1.55;white-space:pre-wrap}.notification-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.notification-empty{margin:0;color:#766c65}.notification-credit{margin:12px 0 0;color:#766c65;font-size:.72rem}.notification-panel .button{padding:7px 10px;font-size:.8rem}.deployment-success{border-left:4px solid #247a46}.deployment-running{border-left:4px solid #b26a00}.deployment-failed{border-left:4px solid #a12626}.notification-draft-note{padding:9px 11px;border-radius:9px;background:#fff4df;color:#674a18;margin:10px 0}@media(max-width:720px){.notification-panel-head,.notification-item-head{flex-direction:column}.notification-toolbar{grid-template-columns:1fr}}
`;document.head.append(style);}

function renderNotificationCenter(){
  installNotificationStyles();const ui=ensureNotificationUi();if(!ui)return;
  if(!arxivSuggestionsReady||!generalNotificationsReady){ui.panel.innerHTML='<p class="notification-empty">正在讀取通知……</p>';return;}
  const cards=allNotificationCards();const filtered=cards.filter(matchesNotification);const unread=cards.filter(x=>!x.read).length;const count=ui.button.querySelector('[data-notification-count]');if(count)count.textContent=String(unread);ui.button.setAttribute('aria-label',`通知 ${unread} 筆未讀`);
  const dirty=generalNotificationsDirty()||arxivSuggestionSignature(arxivSuggestionsDraft)!==arxivSuggestionSignature(arxivSuggestionsBase);
  const ignoredDelta=(arxivSuggestionsDraft.ignored_ids||[]).filter(id=>!(arxivSuggestionsBase.ignored_ids||[]).includes(id)).length;
  ui.panel.innerHTML=`<div class="notification-panel-head"><div><div class="eyebrow">Notification center</div><h2>通知中心</h2><p class="muted">整合 arXiv、正式出版、失效連結、聯絡留言與 GitHub Pages 部署狀態。</p></div><div class="notification-toolbar-actions">${ignoredDelta?'<button class="button" type="button" data-arxiv-restore-ignored>復原本次忽略</button>':''}${dirty?'<button class="button" type="button" id="resetNotificationDrafts">放棄通知修改</button>':''}</div></div>${dirty?'<div class="notification-draft-note">星號、已讀、刪除與忽略目前仍是本機草稿，會和其他網站修改一起送出。</div>':''}<div class="notification-toolbar"><input type="search" id="notificationSearch" value="${esc(notificationSearch)}" placeholder="搜尋標題、內容、作者、DOI 或網址"><div class="notification-toolbar-actions"><label class="switch"><input type="checkbox" id="notificationUnreadOnly" ${notificationUnreadOnly?'checked':''}>只看未讀</label><button class="button" type="button" id="clearReadNotifications">清除已讀</button></div></div><div class="notification-list">${deploymentHtml()}${filtered.length?filtered.map(cardHtml).join(''):'<p class="notification-empty">沒有符合條件的通知。</p>'}</div><p class="notification-credit">未加星號的通知會在超過 ${esc(generalNotificationsDraft.retention_days)} 天後由排程清理；arXiv metadata 來自 arXiv，正式出版候選來自 Crossref。</p>`;
}

function notificationsPreviewHtml(operation){const before=normalizeGeneralNotifications(operation?.before),after=normalizeGeneralNotifications(operation?.after);const beforeMap=new Map(before.notifications.map(x=>[x.key,x])),afterMap=new Map(after.notifications.map(x=>[x.key,x]));let changed=0,removed=0;for(const [key,item] of afterMap){if(JSON.stringify(item)!==JSON.stringify(beforeMap.get(key)))changed++;}for(const key of beforeMap.keys())if(!afterMap.has(key))removed++;return `<details class="diff"><summary><strong>通知中心</strong>：變更 ${changed}、刪除 ${removed}</summary><div class="preview-card"><p>星號、已讀狀態與手動刪除會同步到 <code>content/notifications.json</code>。</p></div></details>`;}
function notificationsHistoryPreviewHtml(historyItem){return notificationsPreviewHtml({before:historyItem?.before,after:historyItem?.after});}
function arxivSuggestionsPreviewHtml(operation){const before=normalizeArxivSuggestions(operation?.before),after=normalizeArxivSuggestions(operation?.after);const newlyIgnored=after.ignored_ids.filter(id=>!before.ignored_ids.includes(id));const changed=after.suggestions.filter(item=>{const old=before.suggestions.find(x=>x.arxiv_id===item.arxiv_id);return old&&(Boolean(old.starred)!==Boolean(item.starred)||Boolean(old.read)!==Boolean(item.read));}).length;return `<details class="diff"><summary><strong>arXiv 通知</strong>：狀態 ${changed}、忽略 ${newlyIgnored.length}</summary><div class="preview-card"><p>${newlyIgnored.length?`永久忽略：${newlyIgnored.map(esc).join('、')}`:'沒有新增永久忽略項目。'}</p></div></details>`;}
function arxivSuggestionsHistoryPreviewHtml(historyItem){return arxivSuggestionsPreviewHtml({before:historyItem?.before,after:historyItem?.after});}

async function fetchDeploymentStatus(){
  if(deploymentRequestInFlight)return;
  deploymentRequestInFlight=true;
  deploymentState={loading:!deploymentState.run,error:'',run:deploymentState.run};renderDeploymentCard();
  try{const response=await fetch('https://api.github.com/repos/hctsui/hctsui.github.io/actions/workflows/deploy-cms-pages.yml/runs?branch=cms&per_page=1',{headers:{Accept:'application/vnd.github+json'},cache:'no-store'});if(!response.ok)throw new Error(`GitHub API ${response.status}`);const data=await response.json();deploymentState={loading:false,error:'',run:(data.workflow_runs||[])[0]||null};}
  catch(error){deploymentState={loading:false,error:String(error?.message||error),run:null};}
  finally{deploymentRequestInFlight=false;}
  renderDeploymentCard();
}

function stopDeploymentPolling(){if(deploymentPollTimer){clearInterval(deploymentPollTimer);deploymentPollTimer=null;}}
function startDeploymentPolling(){
  stopDeploymentPolling();
  fetchDeploymentStatus();
  deploymentPollTimer=setInterval(()=>{const panel=document.querySelector('[data-notification-panel]');if(!panel||panel.classList.contains('hidden')){stopDeploymentPolling();return;}fetchDeploymentStatus();},5000);
}

Promise.all([
  fetch('../content/arxiv-suggestions.json',{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})),
  fetch('../content/notifications.json',{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({})),
]).then(([arxivRemote,generalRemote])=>{
  arxivSuggestionsBase=normalizeArxivSuggestions(arxivRemote);arxivSuggestionsDraft=clone(arxivSuggestionsBase);
  generalNotificationsBase=normalizeGeneralNotifications(generalRemote);generalNotificationsDraft=clone(generalNotificationsBase);
  try{const saved=JSON.parse(localStorage.getItem(ARXIV_SUGGESTIONS_DRAFT_KEY)||'null');if(saved?.base_signature===arxivSuggestionSignature(arxivSuggestionsBase)&&saved?.draft)arxivSuggestionsDraft=normalizeArxivSuggestions(saved.draft);else if(saved)localStorage.removeItem(ARXIV_SUGGESTIONS_DRAFT_KEY);}catch{localStorage.removeItem(ARXIV_SUGGESTIONS_DRAFT_KEY);}
  try{const saved=JSON.parse(localStorage.getItem(GENERAL_NOTIFICATIONS_DRAFT_KEY)||'null');if(saved?.base_signature===generalNotificationSignature(generalNotificationsBase)&&saved?.draft)generalNotificationsDraft=normalizeGeneralNotifications(saved.draft);else if(saved)localStorage.removeItem(GENERAL_NOTIFICATIONS_DRAFT_KEY);}catch{localStorage.removeItem(GENERAL_NOTIFICATIONS_DRAFT_KEY);}
  arxivSuggestionsReady=true;generalNotificationsReady=true;renderNotificationCenter();if(typeof renderPreview==='function')renderPreview(false);
});
document.addEventListener('DOMContentLoaded',renderNotificationCenter,{once:true});
