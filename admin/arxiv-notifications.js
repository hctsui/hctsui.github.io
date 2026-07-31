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
  renderArxivNotifications();
  if (typeof renderPreview === 'function') renderPreview(false);
}

function clearArxivSuggestionsDraft(refresh = true) {
  localStorage.removeItem(ARXIV_SUGGESTIONS_DRAFT_KEY);
  if (arxivSuggestionsBase) arxivSuggestionsDraft = clone(arxivSuggestionsBase);
  if (refresh) {
    renderArxivNotifications();
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

function addArxivSuggestionToDraft(id) {
  const item = pendingArxivSuggestions().find(x => x.arxiv_id === id);
  if (!item) return flash('找不到這筆 arXiv 通知，請重新整理');
  const record = arxivSuggestionPublication(item);
  queueOperation({
    op: 'add',
    type: 'publication',
    after: record,
    notes: ['由 arXiv 通知建立；請確認中文題目、中文作者與 PDF 連結'],
  });
  const operation = contentOps().find(op => op.op === 'add' && op.after?.id === record.id);
  const index = draft.indexOf(operation);
  if (operation && index >= 0) {
    openEditor('publication', operation.after, { draftIndex: index, draftOp: 'add' });
    switchTab('add');
  }
  renderArxivNotifications();
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

function restoreIgnoredArxivSuggestions() {
  clearArxivSuggestionsDraft(true);
  flash('已復原本次 arXiv 忽略草稿');
}

function arxivDateLabel(value) {
  const text = String(value || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return text || '日期不明';
  const [year, month, day] = text.split('-');
  return `${year}/${Number(month)}/${Number(day)}`;
}

function ensureArxivNotificationUi() {
  const actions = document.querySelector('.header-actions');
  if (!actions) return null;
  let button = actions.querySelector('[data-arxiv-notification-button]');
  if (!button) {
    button = document.createElement('button');
    button.type = 'button';
    button.className = 'button';
    button.dataset.arxivNotificationButton = '';
    button.innerHTML = '通知 <span class="notification-count" data-arxiv-notification-count>0</span>';
    const guide = [...actions.querySelectorAll('a')].find(a => a.getAttribute('href') === 'guide.html');
    guide ? actions.insertBefore(button, guide) : actions.prepend(button);
  }
  let panel = document.querySelector('[data-arxiv-notification-panel]');
  if (!panel) {
    panel = document.createElement('section');
    panel.className = 'notification-panel panel hidden';
    panel.dataset.arxivNotificationPanel = '';
    actions.after(panel);
  }
  if (!document.querySelector('style[data-arxiv-notification-style]')) {
    const style = document.createElement('style');
    style.dataset.arxivNotificationStyle = '';
    style.textContent = `
      .notification-count{display:inline-grid;place-items:center;min-width:1.45rem;height:1.45rem;margin-left:.3rem;padding:0 .36rem;border-radius:999px;background:#8d493d;color:#fff;font-size:.72rem;font-weight:900}
      [data-arxiv-notification-button].primary .notification-count{background:#fff;color:#2d2926}
      .notification-panel{margin:0 0 18px;padding:16px 18px}.notification-panel-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}.notification-panel-head h2{margin:0;font-size:1.2rem}.notification-list{display:grid;gap:10px}.notification-item{padding:13px;border:1px solid #ded3ca;border-radius:12px;background:#fcfaf8}.notification-item h3{margin:0 0 5px;font-size:1rem}.notification-meta{display:flex;gap:8px;flex-wrap:wrap;margin:.3rem 0;color:#766c65;font-size:.78rem}.notification-summary{margin:.6rem 0;color:#5f554f;line-height:1.55}.notification-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.notification-empty{margin:0;color:#766c65}.notification-credit{margin:12px 0 0;color:#766c65;font-size:.72rem}.notification-panel .button{padding:7px 10px;font-size:.8rem}
    `;
    document.head.append(style);
  }
  button.onclick = () => {
    panel.classList.toggle('hidden');
    button.classList.toggle('primary', !panel.classList.contains('hidden'));
  };
  panel.onclick = event => {
    const target = event.target.closest('button,a');
    if (!target) return;
    if (target.dataset.arxivAdd) addArxivSuggestionToDraft(target.dataset.arxivAdd);
    if (target.dataset.arxivIgnore) ignoreArxivSuggestion(target.dataset.arxivIgnore);
    if (target.dataset.arxivRestoreIgnored !== undefined) restoreIgnoredArxivSuggestions();
  };
  return { button, panel };
}

function renderArxivNotifications() {
  const ui = ensureArxivNotificationUi();
  if (!ui) return;
  const pending = pendingArxivSuggestions();
  const count = ui.button.querySelector('[data-arxiv-notification-count]');
  if (count) count.textContent = String(pending.length);
  ui.button.setAttribute('aria-label', `arXiv 論文通知 ${pending.length} 筆`);
  const ignoredDelta = arxivSuggestionsReady
    ? (arxivSuggestionsDraft.ignored_ids || []).filter(id => !(arxivSuggestionsBase.ignored_ids || []).includes(id)).length
    : 0;
  if (!arxivSuggestionsReady) {
    ui.panel.innerHTML = '<p class="notification-empty">正在讀取 arXiv 通知……</p>';
    return;
  }
  ui.panel.innerHTML = `
    <div class="notification-panel-head"><div><div class="eyebrow">arXiv publication suggestions</div><h2>論文通知</h2><p class="muted">每週檢查作者 ${esc(arxivSuggestionsDraft.search.author_query)}；只有你點選後才會加入草稿，不會自動公開。</p></div>${ignoredDelta ? '<button class="button" type="button" data-arxiv-restore-ignored>復原本次忽略</button>' : ''}</div>
    <div class="notification-list">${pending.length ? pending.map(item => `
      <article class="notification-item">
        <h3>${esc(item.title || item.arxiv_id)}</h3>
        <div class="notification-meta"><span class="tag">${esc(item.arxiv_id)}</span><span>${esc(arxivDateLabel(item.published))}</span>${item.primary_category ? `<span>${esc(item.primary_category)}</span>` : ''}</div>
        <div class="muted">${esc(englishAuthorLine(item.authors))}</div>
        ${item.summary ? `<details><summary>摘要</summary><p class="notification-summary">${esc(item.summary)}</p></details>` : ''}
        <div class="notification-actions"><button class="button primary" type="button" data-arxiv-add="${esc(item.arxiv_id)}">加入新增草稿</button><button class="button" type="button" data-arxiv-ignore="${esc(item.arxiv_id)}">忽略</button><a class="button" href="${esc(item.arxiv_url)}" target="_blank" rel="noopener">查看 arXiv</a></div>
      </article>`).join('') : '<p class="notification-empty">目前沒有新的 arXiv 論文通知。</p>'}</div>
    <p class="notification-credit">Thank you to arXiv for use of its open access interoperability.</p>`;
}

function arxivSuggestionsPreviewHtml(operation) {
  const before = normalizeArxivSuggestions(operation?.before);
  const after = normalizeArxivSuggestions(operation?.after);
  const newlyIgnored = after.ignored_ids.filter(id => !before.ignored_ids.includes(id));
  return `<details class="diff"><summary><strong>arXiv 通知</strong>：忽略 ${newlyIgnored.length} 筆</summary><div class="preview-card"><div class="order-diff-summary"><strong>永久忽略的 arXiv ID</strong><span class="tag">${newlyIgnored.length}</span></div>${newlyIgnored.length ? `<div class="order-diff-list">${newlyIgnored.map(id => `<div class="order-diff-row changed"><span class="order-diff-name">${esc(id)}</span></div>`).join('')}</div>` : '<p class="muted">沒有變更。</p>'}</div></details>`;
}

function arxivSuggestionsHistoryPreviewHtml(historyItem) {
  return arxivSuggestionsPreviewHtml({ before: historyItem?.before, after: historyItem?.after });
}

fetch('../content/arxiv-suggestions.json', { cache: 'no-store' })
  .then(response => response.ok ? response.json() : normalizeArxivSuggestions({}))
  .catch(() => normalizeArxivSuggestions({}))
  .then(remote => {
    arxivSuggestionsBase = normalizeArxivSuggestions(remote);
    arxivSuggestionsDraft = clone(arxivSuggestionsBase);
    try {
      const saved = JSON.parse(localStorage.getItem(ARXIV_SUGGESTIONS_DRAFT_KEY) || 'null');
      if (saved?.base_signature === arxivSuggestionSignature(arxivSuggestionsBase) && saved?.draft) {
        arxivSuggestionsDraft = normalizeArxivSuggestions(saved.draft);
      } else if (saved) localStorage.removeItem(ARXIV_SUGGESTIONS_DRAFT_KEY);
    } catch {
      localStorage.removeItem(ARXIV_SUGGESTIONS_DRAFT_KEY);
    }
    arxivSuggestionsReady = true;
    renderArxivNotifications();
    if (typeof renderPreview === 'function') renderPreview(false);
  });

document.addEventListener('DOMContentLoaded', renderArxivNotifications, { once: true });
