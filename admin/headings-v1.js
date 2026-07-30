'use strict';

const HEADING_DRAFT_KEY = 'hctsui-headings-draft-v1';
const MANAGED_HEADING_DEFAULTS = {
  "home_publications": {
    "label": {
      "en": "Recent work",
      "zh": "近期成果"
    },
    "title": {
      "en": "Selected Publications",
      "zh": "精選論文"
    }
  },
  "home_upcoming": {
    "label": {
      "en": "Calendar",
      "zh": "行程"
    },
    "title": {
      "en": "Upcoming",
      "zh": "近期活動"
    }
  },
  "home_contact": {
    "label": {
      "en": "Contact",
      "zh": "聯絡資訊"
    },
    "title": {
      "en": "Get in touch",
      "zh": "聯絡"
    }
  },
  "cv_page": {
    "label": {
      "en": "Academic profile",
      "zh": "學術資料"
    },
    "title": {
      "en": "Curriculum Vitae",
      "zh": "履歷"
    },
    "intro": {
      "en": "Education, research interests, and honors.",
      "zh": "學歷、研究領域與獎項"
    }
  },
  "cv_research": {
    "label": {
      "en": "Fields",
      "zh": "研究方向"
    },
    "title": {
      "en": "Research Interests",
      "zh": "研究領域"
    }
  },
  "cv_education": {
    "label": {
      "en": "Degrees",
      "zh": "學位"
    },
    "title": {
      "en": "Education",
      "zh": "學歷"
    }
  },
  "cv_honors": {
    "label": {
      "en": "Recognition",
      "zh": "獎助紀錄"
    },
    "title": {
      "en": "Honors and Awards",
      "zh": "獎項與榮譽"
    }
  },
  "cv_personal": {
    "title": {
      "en": "Personal Information",
      "zh": "個人資訊"
    }
  },
  "publications_page": {
    "label": {
      "en": "Research record",
      "zh": "研究紀錄"
    },
    "title": {
      "en": "Publications and Preprints",
      "zh": "論文與預印本"
    },
    "intro": {
      "en": "A complete list of current papers and preprints.",
      "zh": "論文與預印本的完整列表"
    }
  },
  "publication_groups": {
    "label": {
      "en": "Manuscript type",
      "zh": "稿件類型"
    }
  },
  "activities_page": {
    "label": {
      "en": "Academic record",
      "zh": "學術紀錄"
    },
    "title": {
      "en": "Activities",
      "zh": "學術活動"
    },
    "intro": {
      "en": "Academic visits, presentations, conferences and workshops.",
      "zh": "學術訪問、學術報告、會議與工作坊"
    }
  },
  "activity_visit": {
    "label": {
      "en": "Visit",
      "zh": "訪問經歷"
    },
    "title": {
      "en": "Academic Visits",
      "zh": "學術訪問"
    }
  },
  "activity_talk": {
    "label": {
      "en": "Talks",
      "zh": "演講紀錄"
    },
    "title": {
      "en": "Presentations",
      "zh": "學術報告"
    }
  },
  "activity_organization": {
    "label": {
      "en": "Organizing Experience",
      "zh": "籌辦經歷"
    },
    "title": {
      "en": "Organization",
      "zh": "學術活動籌辦"
    }
  },
  "activity_conference": {
    "label": {
      "en": "Participation",
      "zh": "參與紀錄"
    },
    "title": {
      "en": "Conferences and Workshops",
      "zh": "會議與工作坊"
    }
  },
  "teaching_page": {
    "label": {
      "en": "Teaching record",
      "zh": "教學紀錄"
    },
    "title": {
      "en": "Teaching Experience",
      "zh": "教學經歷"
    },
    "intro": {
      "en": "Teaching and course-assistant experience.",
      "zh": "教學與課程助教經歷"
    }
  },
  "teaching_groups": {
    "label": {
      "en": "Institution",
      "zh": "機構"
    }
  }
};

const HEADING_LAYOUT = [
  {title:'首頁 Home', items:[
    ['home_publications','精選論文區'],
    ['home_upcoming','近期活動區'],
    ['home_contact','聯絡區']
  ]},
  {title:'CV 網頁與 PDF CV', items:[
    ['cv_page','CV 頁首'],
    ['cv_research','研究領域'],
    ['cv_education','學歷'],
    ['cv_honors','獎項與榮譽'],
    ['cv_personal','PDF CV 個人資訊']
  ]},
  {title:'Publications', items:[
    ['publications_page','Publications 頁首'],
    ['publication_groups','作品分類左上小字']
  ], dynamicKind:'publication', dynamicTitle:'論文分類大標題'},
  {title:'Activities', items:[
    ['activities_page','Activities 頁首'],
    ['activity_visit','學術訪問'],
    ['activity_talk','學術報告'],
    ['activity_organization','Organization'],
    ['activity_conference','會議與工作坊']
  ]},
  {title:'Teaching', items:[
    ['teaching_page','Teaching 頁首'],
    ['teaching_groups','機構分類左上小字']
  ], dynamicKind:'teaching', dynamicTitle:'教學機構大標題'}
];

let originalHeadingBundle = null;
let headingDraft = null;
let headingGroupDraft = null;
let headingRemoteSignature = '';

function normalizeManagedHeadings(value) {
  const result = clone(MANAGED_HEADING_DEFAULTS);
  if (!value || typeof value !== 'object') return result;
  for (const [key, defaults] of Object.entries(MANAGED_HEADING_DEFAULTS)) {
    const source = value[key];
    if (!source || typeof source !== 'object') continue;
    for (const part of Object.keys(defaults)) {
      const pair = source[part];
      if (!pair || typeof pair !== 'object') continue;
      for (const lang of ['en','zh']) {
        const text = typeof pair[lang] === 'string' ? pair[lang].trim() : '';
        if (text) result[key][part][lang] = text;
      }
    }
  }
  return result;
}

function currentManagedGroupLabels() {
  const result = {publication:{},teaching:{}};
  for (const kind of ['publication','teaching']) {
    for (const group of site?.settings?.content_groups?.[kind] || []) {
      if (!group?.id) continue;
      result[kind][group.id] = {
        en:String(group.label?.en || '').trim(),
        zh:String(group.label?.zh || '').trim()
      };
    }
  }
  return result;
}

function normalizeGroupLabels(value, fallback) {
  const result = clone(fallback || {publication:{},teaching:{}});
  if (!value || typeof value !== 'object') return result;
  for (const kind of ['publication','teaching']) {
    if (!value[kind] || typeof value[kind] !== 'object') continue;
    for (const id of Object.keys(result[kind] || {})) {
      const pair = value[kind][id];
      if (!pair || typeof pair !== 'object') continue;
      for (const lang of ['en','zh']) {
        if (typeof pair[lang] === 'string') result[kind][id][lang] = pair[lang];
      }
    }
  }
  return result;
}

function normalizeHeadingBundle(value) {
  const fallbackGroups = currentManagedGroupLabels();
  if (value && value.headings) {
    return {
      headings:normalizeManagedHeadings(value.headings),
      group_labels:normalizeGroupLabels(value.group_labels, fallbackGroups)
    };
  }
  return {headings:normalizeManagedHeadings(value || {}),group_labels:fallbackGroups};
}

function currentHeadingBundle() {
  return {
    headings:normalizeManagedHeadings(site?.settings?.headings || {}),
    group_labels:currentManagedGroupLabels()
  };
}

function ensureHeadingState() {
  if (!site || !site.settings) return false;
  const remote = currentHeadingBundle();
  const signature = JSON.stringify(remote);
  if (headingDraft && headingGroupDraft && headingRemoteSignature === signature) return true;
  headingRemoteSignature = signature;
  originalHeadingBundle = clone(remote);
  headingDraft = clone(remote.headings);
  headingGroupDraft = clone(remote.group_labels);
  try {
    const saved = JSON.parse(localStorage.getItem(HEADING_DRAFT_KEY) || 'null');
    const savedBase = saved?.base ? normalizeHeadingBundle(saved.base) : null;
    if (savedBase && saved?.data && JSON.stringify(savedBase) === signature) {
      const restored = normalizeHeadingBundle(saved.data);
      headingDraft = restored.headings;
      headingGroupDraft = restored.group_labels;
    } else if (saved) {
      localStorage.removeItem(HEADING_DRAFT_KEY);
    }
  } catch {
    localStorage.removeItem(HEADING_DRAFT_KEY);
  }
  return true;
}

function currentHeadingDraftBundle() {
  ensureHeadingState();
  return {headings:clone(headingDraft),group_labels:clone(headingGroupDraft)};
}

function headingsDirty() {
  return ensureHeadingState() && JSON.stringify(originalHeadingBundle) !== JSON.stringify(currentHeadingDraftBundle());
}

function headingOperation() {
  ensureHeadingState();
  return {op:'headings', before:clone(originalHeadingBundle), after:currentHeadingDraftBundle()};
}

function saveHeadingsLocal() {
  if (!ensureHeadingState()) return;
  if (headingsDirty()) localStorage.setItem(HEADING_DRAFT_KEY, JSON.stringify({base:originalHeadingBundle,data:currentHeadingDraftBundle()}));
  else localStorage.removeItem(HEADING_DRAFT_KEY);
}

function validateHeadingsDraft() {
  if (!ensureHeadingState()) return [];
  const errors = [];
  for (const [key, parts] of Object.entries(MANAGED_HEADING_DEFAULTS)) {
    for (const part of Object.keys(parts)) {
      for (const lang of ['en','zh']) {
        if (!String(headingDraft?.[key]?.[part]?.[lang] || '').trim()) errors.push(`${key}.${part}.${lang} 不能空白`);
      }
    }
  }
  for (const kind of ['publication','teaching']) {
    for (const [id,pair] of Object.entries(headingGroupDraft?.[kind] || {})) {
      for (const lang of ['en','zh']) if (!String(pair?.[lang] || '').trim()) errors.push(`${kind}.${id}.${lang} 不能空白`);
    }
  }
  return errors;
}

function headingPartName(part) {
  return part === 'label' ? '左上小字' : part === 'intro' ? '頁面簡介' : '大標題';
}

function renderHeadingStatus() {
  const box = document.getElementById('headingsStatus');
  if (!box || !ensureHeadingState()) return;
  const errors = validateHeadingsDraft();
  box.className = 'notice ' + (errors.length ? 'error' : headingsDirty() ? 'success' : '');
  box.innerHTML = errors.length
    ? `<strong>不能送出：</strong>${errors.map(esc).join('；')}`
    : headingsDirty()
      ? '標題已有修改，會和本次批次一起送出；網站與 PDF CV 會使用同一份設定。'
      : '尚未修改標題；目前顯示值與網站現況相同。';
}

function renderStaticHeadingItem(key,label) {
  const parts = MANAGED_HEADING_DEFAULTS[key];
  return `<details class="diff heading-admin-item" open>
    <summary><strong>${esc(label)}</strong><span class="muted"> · ${esc(key)}</span></summary>
    ${Object.keys(parts).map(part => `<div class="pair-grid">
      <div class="field"><label>${headingPartName(part)}（英文）</label>
        <input data-heading-key="${esc(key)}" data-heading-part="${esc(part)}" data-heading-lang="en" value="${esc(headingDraft[key][part].en)}">
      </div>
      <div class="field"><label>${headingPartName(part)}（中文）</label>
        <input data-heading-key="${esc(key)}" data-heading-part="${esc(part)}" data-heading-lang="zh" value="${esc(headingDraft[key][part].zh)}">
      </div>
    </div>`).join('')}
  </details>`;
}

function renderDynamicGroupLabels(kind,titleText) {
  const groups = site?.settings?.content_groups?.[kind] || [];
  if (!groups.length) return '';
  return `<details class="diff heading-admin-item" open>
    <summary><strong>${esc(titleText)}</strong><span class="muted"> · 網站與 PDF CV 共用</span></summary>
    ${groups.map(group => {
      const pair = headingGroupDraft[kind][group.id] || {en:'',zh:''};
      return `<div class="pair-grid">
        <div class="field"><label>${esc(group.id)}（英文）</label>
          <input data-heading-group-kind="${esc(kind)}" data-heading-group-id="${esc(group.id)}" data-heading-group-lang="en" value="${esc(pair.en)}">
        </div>
        <div class="field"><label>${esc(group.id)}（中文）</label>
          <input data-heading-group-kind="${esc(kind)}" data-heading-group-id="${esc(group.id)}" data-heading-group-lang="zh" value="${esc(pair.zh)}">
        </div>
      </div>`;
    }).join('')}
  </details>`;
}

function renderHeadings() {
  const root = document.getElementById('headingsEditor');
  if (!root || !ensureHeadingState()) return;
  root.innerHTML = HEADING_LAYOUT.map(group => `
    <section class="preview-card heading-admin-group">
      <h3>${esc(group.title)}</h3>
      ${group.items.map(([key,label]) => renderStaticHeadingItem(key,label)).join('')}
      ${group.dynamicKind ? renderDynamicGroupLabels(group.dynamicKind,group.dynamicTitle) : ''}
    </section>
  `).join('');
  renderHeadingStatus();
}

function headingDiffRows(beforeBundle, afterBundle) {
  const before = normalizeHeadingBundle(beforeBundle);
  const after = normalizeHeadingBundle(afterBundle);
  const rows = [];
  for (const group of HEADING_LAYOUT) {
    for (const [key,label] of group.items) {
      for (const part of Object.keys(MANAGED_HEADING_DEFAULTS[key])) {
        for (const lang of ['en','zh']) {
          const oldValue = String(before.headings?.[key]?.[part]?.[lang] || '');
          const newValue = String(after.headings?.[key]?.[part]?.[lang] || '');
          if (oldValue !== newValue) rows.push({group:group.title,label,part,lang,oldValue,newValue});
        }
      }
    }
  }
  for (const kind of ['publication','teaching']) {
    const ids = new Set([...Object.keys(before.group_labels?.[kind] || {}),...Object.keys(after.group_labels?.[kind] || {})]);
    for (const id of ids) for (const lang of ['en','zh']) {
      const oldValue=String(before.group_labels?.[kind]?.[id]?.[lang] || '');
      const newValue=String(after.group_labels?.[kind]?.[id]?.[lang] || '');
      if(oldValue!==newValue) rows.push({group:kind==='publication'?'Publications':'Teaching',label:id,part:'group',lang,oldValue,newValue});
    }
  }
  return rows;
}

function headingPreviewHtml(operation) {
  const rows = headingDiffRows(operation?.before || {}, operation?.after || {});
  if (!rows.length) return '<details class="diff"><summary><strong>網站標題</strong>：沒有實際差異</summary></details>';
  return `<details class="diff" open><summary><strong>網站標題</strong>：修改 ${rows.length} 個中英文欄位</summary>
    <div class="order-diff-list">
      ${rows.map(row => `<div class="order-diff-row changed">
        <strong>${esc(row.group)} · ${esc(row.label)} · ${esc(row.part==='group'?'群組大標題':headingPartName(row.part))}（${row.lang==='en'?'英文':'中文'}）</strong>
        <div class="preview-columns" style="width:100%">
          <div><span class="muted">修改前</span><div class="preview-value">${esc(row.oldValue || '—')}</div></div>
          <div><span class="muted">修改後</span><div class="preview-value">${esc(row.newValue || '—')}</div></div>
        </div>
      </div>`).join('')}
    </div>
  </details>`;
}

function headingsHistoryPreviewHtml(historyItem) {
  return headingPreviewHtml({before:historyItem?.before || {},after:historyItem?.after || {}});
}

document.getElementById('headingsEditor')?.addEventListener('input', event => {
  const input = event.target.closest('[data-heading-key],[data-heading-group-id]');
  if (!input || !ensureHeadingState()) return;
  if (input.dataset.headingKey) {
    const key=input.dataset.headingKey,part=input.dataset.headingPart,lang=input.dataset.headingLang;
    if (headingDraft[key]?.[part] && ['en','zh'].includes(lang)) headingDraft[key][part][lang]=input.value;
  } else {
    const kind=input.dataset.headingGroupKind,id=input.dataset.headingGroupId,lang=input.dataset.headingGroupLang;
    if (headingGroupDraft?.[kind]?.[id] && ['en','zh'].includes(lang)) headingGroupDraft[kind][id][lang]=input.value;
  }
  saveHeadingsLocal();
  renderHeadingStatus();
  renderPreview(false);
});

document.getElementById('resetHeadings')?.addEventListener('click', () => {
  if (!ensureHeadingState()) return;
  if (!headingsDirty() || confirm('放棄尚未送出的標題修改？')) {
    headingDraft = clone(originalHeadingBundle.headings);
    headingGroupDraft = clone(originalHeadingBundle.group_labels);
    saveHeadingsLocal();
    renderHeadings();
    renderPreview(false);
  }
});
