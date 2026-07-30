/* Multi-tag translation dictionary UI and site consistency audit. */
(() => {
  const TAG_AUDIT_IGNORE_KEY = 'hctsui-translation-audit-ignore-v1';
  const tagSelectedFilters = new Set();
  let tagAuditItems = [];

  function loadIgnoredAudits() {
    try {
      const value = JSON.parse(localStorage.getItem(TAG_AUDIT_IGNORE_KEY) || '[]');
      return new Set(Array.isArray(value) ? value : []);
    } catch {
      localStorage.removeItem(TAG_AUDIT_IGNORE_KEY);
      return new Set();
    }
  }

  const ignoredAudits = loadIgnoredAudits();
  const saveIgnoredAudits = () => {
    localStorage.setItem(TAG_AUDIT_IGNORE_KEY, JSON.stringify([...ignoredAudits]));
  };

  const tagDefinitions = () => Array.isArray(translations?.tags) ? translations.tags : [];
  const fallbackTagId = () => tagDefinitions().find((item) => item.id === 'other')?.id || tagDefinitions()[0]?.id || '';
  function normalizePairTags(pair) {
    if (!pair || typeof pair !== 'object') return;
    const valid = new Set(tagDefinitions().map((item) => item.id));
    let tags = [...new Set((Array.isArray(pair.tags) ? pair.tags : []).filter((id) => valid.has(id)))];
    if (tags.length > 1 && tags.includes('other')) tags = tags.filter((id) => id !== 'other');
    if (!tags.length && fallbackTagId()) tags = [fallbackTagId()];
    pair.tags = tags;
  }
  function normalizeAllPairTags() {
    for (const pair of translations.pairs || []) normalizePairTags(pair);
  }
  const tagMap = () => new Map(tagDefinitions().map((item) => [item.id, item]));
  const tagLabel = (id) => {
    const item = tagMap().get(id);
    return item?.label?.zh || item?.label?.en || id;
  };
  const orderedTags = (pair) => {
    normalizePairTags(pair);
    const selected = new Set(Array.isArray(pair?.tags) ? pair.tags : []);
    return tagDefinitions().map((item) => item.id).filter((id) => selected.has(id));
  };
  const makeTagId = (value) => {
    const base = norm(value)
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') || `tag-${Date.now().toString(36)}`;
    const used = new Set(tagDefinitions().map((item) => item.id));
    let id = base;
    let suffix = 2;
    while (used.has(id)) id = `${base}-${suffix++}`;
    return id;
  };

  // Keep exact dictionary lookup behavior, but also retain canonical spellings
  // for the consistency audit.
  dictionaryIndex = function dictionaryIndexWithCanonicalValues() {
    const en = new Map();
    const zh = new Map();
    const enRaw = new Map();
    const zhRaw = new Map();
    for (const pair of translations.pairs || []) {
      if (!pair.en || !pair.zh) continue;
      const enKey = dictNorm(pair.en);
      const zhKey = dictNorm(pair.zh);
      en.set(enKey, pair.zh);
      zh.set(zhKey, pair.en);
      enRaw.set(enKey, pair.en);
      zhRaw.set(zhKey, pair.zh);
    }
    return { en, zh, enRaw, zhRaw };
  };

  validateDictionary = function validateTaggedDictionary() {
    normalizeAllPairTags();
    const errors = [];
    const tagIds = new Set();
    const tagEn = new Set();
    const tagZh = new Set();

    for (let i = 0; i < tagDefinitions().length; i += 1) {
      const item = tagDefinitions()[i];
      const id = String(item?.id || '').trim();
      const enKey = dictNorm(item?.label?.en);
      const zhKey = dictNorm(item?.label?.zh);
      if (!/^[a-z0-9][a-z0-9_-]*$/.test(id)) {
        errors.push(`標籤 ${i + 1} 的 ID 不合法：${id || '空白'}`);
      }
      if (tagIds.has(id)) errors.push(`標籤 ID 重複：${id}`);
      tagIds.add(id);
      if (!enKey || !zhKey) errors.push(`標籤 ${id || i + 1} 的中英文名稱不能空白`);
      if (tagEn.has(enKey)) errors.push(`標籤英文名稱重複：${item?.label?.en || ''}`);
      if (tagZh.has(zhKey)) errors.push(`標籤中文名稱重複：${item?.label?.zh || ''}`);
      tagEn.add(enKey);
      tagZh.add(zhKey);
    }

    const en = new Map();
    const zh = new Map();
    const exact = new Map();
    for (let i = 0; i < (translations.pairs || []).length; i += 1) {
      const pair = translations.pairs[i];
      const enKey = dictNorm(pair.en);
      const zhKey = dictNorm(pair.zh);
      const exactKey = `${enKey}\u0000${zhKey}`;
      const rowTags = Array.isArray(pair.tags) ? pair.tags : [];
      if (!rowTags.length) errors.push(`第 ${i + 1} 列至少需要一個標籤`);
      for (const id of rowTags) {
        if (!tagIds.has(id)) errors.push(`第 ${i + 1} 列使用不存在的標籤：${id}`);
      }
      if (new Set(rowTags).size !== rowTags.length) errors.push(`第 ${i + 1} 列有重複標籤`);
      if (!enKey || !zhKey) {
        errors.push(`第 ${i + 1} 列有空白`);
        continue;
      }
      if (exact.has(exactKey)) {
        errors.push(`第 ${i + 1} 列與第 ${exact.get(exactKey) + 1} 列完全重複`);
      } else exact.set(exactKey, i);
      if (en.has(enKey) && en.get(enKey) !== zhKey) errors.push(`英文重複衝突：${pair.en}`);
      if (zh.has(zhKey) && zh.get(zhKey) !== enKey) errors.push(`中文重複衝突：${pair.zh}`);
      if (!en.has(enKey)) en.set(enKey, zhKey);
      if (!zh.has(zhKey)) zh.set(zhKey, enKey);
    }
    return errors;
  };

  function tagCheckboxes(pair, index) {
    const current = new Set(Array.isArray(pair.tags) ? pair.tags : []);
    return tagDefinitions().map((item) => `
      <label class="tag-check">
        <input type="checkbox" data-pair-tag="${esc(item.id)}" data-i="${index}" ${current.has(item.id) ? 'checked' : ''}>
        ${esc(tagLabel(item.id))}
      </label>`).join('');
  }

  function renderTagFilters() {
    const counts = new Map();
    for (const pair of translations.pairs || []) {
      for (const id of orderedTags(pair)) counts.set(id, (counts.get(id) || 0) + 1);
    }
    $('#dictionaryTagFilters').innerHTML = tagDefinitions().map((item) => `
      <button class="tag-filter-chip ${tagSelectedFilters.has(item.id) ? 'active' : ''}" data-filter-tag="${esc(item.id)}">
        ${esc(tagLabel(item.id))} <span class="count">${counts.get(item.id) || 0}</span>
      </button>`).join('') + (tagSelectedFilters.size
      ? '<button class="button" data-clear-tag-filters>清除篩選</button>'
      : '');
  }

  function renderTagManager() {
    const definitions = tagDefinitions();
    const counts = new Map();
    for (const pair of translations.pairs || []) {
      for (const id of pair.tags || []) counts.set(id, (counts.get(id) || 0) + 1);
    }
    $('#tagManagerRows').innerHTML = definitions.map((item, index) => {
      const targets = definitions
        .filter((target) => target.id !== item.id)
        .map((target) => `<option value="${esc(target.id)}">${esc(tagLabel(target.id))}</option>`)
        .join('');
      return `<div class="tag-manager-row">
        <button class="button" data-tag-up="${index}" ${index === 0 ? 'disabled' : ''}>↑</button>
        <button class="button" data-tag-down="${index}" ${index === definitions.length - 1 ? 'disabled' : ''}>↓</button>
        <div><input data-tag-label="zh" data-tag-index="${index}" value="${esc(item.label?.zh || '')}" aria-label="標籤中文名稱"><div class="tag-id">${esc(item.id)}</div></div>
        <input data-tag-label="en" data-tag-index="${index}" value="${esc(item.label?.en || '')}" aria-label="標籤英文名稱">
        <span class="tag">${counts.get(item.id) || 0} 筆</span>
        <select data-merge-target="${esc(item.id)}"><option value="">合併到…</option>${targets}</select>
        <button class="button" data-merge-tag="${esc(item.id)}">合併</button>
        <button class="button danger" data-delete-tag="${esc(item.id)}">刪除</button>
      </div>`;
    }).join('') || '<p class="muted">尚無標籤。</p>';
  }

  function prescribedPair(pair, index = dictionaryIndex()) {
    const enValue = String(pair?.en || '').trim();
    const zhValue = String(pair?.zh || '').trim();
    const enKey = dictNorm(enValue);
    const zhKey = dictNorm(zhValue);
    if (enKey && index.en.has(enKey)) {
      return { en: index.enRaw.get(enKey) || enValue, zh: index.en.get(enKey) };
    }
    if (zhKey && index.zh.has(zhKey)) {
      return { en: index.zh.get(zhKey), zh: index.zhRaw.get(zhKey) || zhValue };
    }
    return null;
  }

  const AUDIT_FIELDS = {
    conference: [['title', '名稱'], ['venue', '場地／機構'], ['city', '城市'], ['country', '國家']],
    talk: [['title', '題目'], ['event', '活動／研討會'], ['venue', '機構／場地'], ['city', '城市'], ['country', '國家']],
    visit: [['title', '訪問機構'], ['city', '城市'], ['country', '國家'], ['visit_description', '其他說明'], ['funding', 'Funding（機構或計畫）']],
    honor: [['title', '名稱'], ['organization', '頒發機構']],
    publication: [['title', '題目'], ['venue', '期刊／狀態']],
    teaching: [['term', '學期'], ['institution', '機構'], ['role', '角色／身分']],
  };

  const auditSignature = (record, field, current, expected) => [
    record.id, field, current.en, current.zh, expected.en, expected.zh,
  ].map((value) => String(value || '')).join('\u0001');

  function pushAuditItem(items, record, field, label, current, expected, apply) {
    if (!expected) return;
    if (String(current.en || '').trim() === String(expected.en || '').trim()
      && String(current.zh || '').trim() === String(expected.zh || '').trim()) return;
    items.push({
      recordId: record.id,
      type: record.type,
      recordTitle: title(record),
      field,
      label,
      current: { en: String(current.en || ''), zh: String(current.zh || '') },
      expected,
      apply,
      signature: auditSignature(record, field, current, expected),
    });
  }

  function buildTranslationAudit() {
    const items = [];
    const index = dictionaryIndex();
    const data = effectiveSite();
    for (const record of allRecords(data)) {
      for (const [field, label] of AUDIT_FIELDS[record.type] || []) {
        const current = record[field];
        if (!current || typeof current !== 'object') continue;
        const expected = prescribedPair(current, index);
        pushAuditItem(items, record, field, label, current, expected, (target) => {
          target[field] = clone(expected);
        });
      }

      if (record.type === 'teaching') {
        const parts = teachingCourseParts(record);
        const expected = prescribedPair(parts.title, index);
        pushAuditItem(items, record, 'course', '課名', parts.title, expected, (target) => {
          const targetParts = teachingCourseParts(target);
          target.course = {
            en: joinCourseValue(targetParts.code, expected.en),
            zh: joinCourseValue(targetParts.code, expected.zh),
          };
        });
      }

      if (record.type === 'publication') {
        authorPairs(record.authors).forEach((current, authorIndex) => {
          const expected = prescribedPair(current, index);
          pushAuditItem(
            items,
            record,
            `authors.${authorIndex}`,
            `作者 ${authorIndex + 1}`,
            current,
            expected,
            (target) => {
              const rows = authorPairs(target.authors);
              while (rows.length <= authorIndex) rows.push({ en: '', zh: '' });
              rows[authorIndex] = clone(expected);
              target.authors = {
                en: formatEnglishAuthors(rows.map((item) => item.en)),
                zh: formatChineseAuthors(rows.map((item) => item.zh)),
              };
            },
          );
        });
      }
    }
    tagAuditItems = items;
    return items;
  }

  function finalizeAuditedRecord(record) {
    if (['conference', 'talk', 'visit'].includes(record.type)) {
      record.description = composeDescription(record.type, record);
      record.description_html = htmlPair(record.description);
      record.title_html = htmlPair(record.title);
    } else if (record.type === 'honor') {
      record.title_html = htmlPair(record.title);
      record.organization_html = htmlPair(record.organization);
    } else if (record.type === 'publication') {
      record.title_html = htmlPair(record.title);
      record.authors_html = htmlPair(record.authors);
      record.venue_html = htmlPair(record.venue);
    }
    return record;
  }

  function applyAuditItems(items) {
    const grouped = new Map();
    for (const item of items) {
      if (!grouped.has(item.recordId)) grouped.set(item.recordId, []);
      grouped.get(item.recordId).push(item);
    }
    for (const [recordId, group] of grouped) {
      const current = allRecords(effectiveSite()).find((record) => record.id === recordId);
      if (!current) continue;
      const after = clone(current);
      for (const item of group) item.apply(after);
      finalizeAuditedRecord(after);
      queueOperation({
        op: 'update',
        type: after.type,
        id: after.id,
        before: current,
        after,
        notes: [`依中英對照表修正 ${group.map((item) => item.label).join('、')}`],
      });
      for (const item of group) ignoredAudits.delete(item.signature);
    }
    saveIgnoredAudits();
    renderDictionary();
    flash(`已將 ${items.length} 個欄位加入修改草稿`);
  }

  function renderAudit() {
    const all = buildTranslationAudit();
    const active = all.filter((item) => !ignoredAudits.has(item.signature));
    const ignoredCount = all.length - active.length;
    if (!all.length) {
      $('#translationAudit').innerHTML = '<div class="notice success"><strong>一致性檢查完成：</strong>目前所有可檢查的項目欄位都符合中英對照表。</div>';
      return;
    }
    const visibleRows = active.slice(0, 80).map((item, index) => `
      <div class="audit-item">
        <div><span class="audit-badge">${esc(LABEL[item.type] || item.type)}</span> <strong>${esc(item.recordTitle)}</strong></div>
        <div class="muted">${esc(item.label)} · ${esc(item.recordId)}</div>
        <div class="audit-values">
          <div><strong>目前</strong><br><code>${esc(item.current.en)} ↔ ${esc(item.current.zh)}</code></div>
          <div><strong>對照表規定</strong><br><code>${esc(item.expected.en)} ↔ ${esc(item.expected.zh)}</code></div>
        </div>
        <div class="actions"><button class="button primary" data-audit-apply="${index}">單筆更改</button><button class="button" data-audit-ignore="${index}">忽略</button></div>
      </div>`).join('');
    $('#translationAudit').innerHTML = `
      <div class="notice ${active.length ? 'error' : 'success'}">
        <div class="audit-toolbar"><strong>項目一致性檢查：${active.length} 個待處理${ignoredCount ? `，${ignoredCount} 個已忽略` : ''}</strong>
          ${active.length ? '<button class="button primary" data-audit-apply-all>一鍵全部更改</button><button class="button" data-audit-ignore-all>全部忽略</button>' : ''}
          ${ignoredCount ? '<button class="button" data-audit-clear-ignore>清除忽略</button>' : ''}
        </div>
        <p class="field-hint">只檢查目前字典能精確命中的可編輯雙語欄位。更改會加入一般修改草稿，送出前仍可預覽或移除。</p>
      </div>
      ${active.length ? `<div class="audit-list">${visibleRows}${active.length > 80 ? `<p class="muted">另有 ${active.length - 80} 個待處理欄位未展開；「一鍵全部更改」仍會全部處理。</p>` : ''}</div>` : ''}`;
  }

  renderDictionary = function renderTaggedDictionary() {
    renderTagFilters();
    renderTagManager();
    const query = norm($('#dictionarySearch').value);
    const rows = (translations.pairs || [])
      .map((pair, index) => ({ pair, index, tags: orderedTags(pair) }))
      .filter((row) => [...tagSelectedFilters].every((id) => row.tags.includes(id)))
      .filter((row) => !query || norm(`${row.pair.en} ${row.pair.zh} ${row.tags.map(tagLabel).join(' ')}`).includes(query));

    $('#dictionaryRows').innerHTML = rows.map(({ pair, index, tags }) => `
      <div class="translation-row tag-mode">
        <input data-dict="en" data-i="${index}" value="${esc(pair.en)}" aria-label="英文">
        <input data-dict="zh" data-i="${index}" value="${esc(pair.zh)}" aria-label="中文">
        <button class="button danger" data-remove-pair="${index}">刪除</button>
        <div class="translation-tags">
          <div>${tags.map((id) => `<span class="tag-pill">${esc(tagLabel(id))}</span>`).join(' ') || '<span class="muted">尚無標籤</span>'}</div>
          <button class="button" data-edit-pair-tags="${index}">編輯標籤</button>
          <div class="tag-check-list" data-tag-editor="${index}" hidden></div>
        </div>
      </div>`).join('') || '<p class="muted">這個搜尋與標籤條件下沒有對照。</p>';

    const errors = validateDictionary();
    const total = (translations.pairs || []).length;
    const scope = tagSelectedFilters.size
      ? `同時符合 ${[...tagSelectedFilters].map(tagLabel).join('＋')}：${rows.length} 組`
      : `顯示 ${rows.length}／${total} 組`;
    $('#dictionaryStatus').className = `notice ${errors.length ? 'error' : dictionaryDirty() ? 'success' : ''}`;
    $('#dictionaryStatus').innerHTML = errors.length
      ? `<strong>不能送出：</strong>${errors.slice(0, 20).map(esc).join('；')}${errors.length > 20 ? `；另有 ${errors.length - 20} 個錯誤` : ''}`
      : dictionaryDirty()
        ? `已修改 ${total} 組與 ${tagDefinitions().length} 個標籤；${scope}；會和本次批次一起送出。`
        : `共 ${total} 組、${tagDefinitions().length} 個標籤；${scope}；尚未修改。`;
    renderAudit();
  };

  // Make translation history readable even when only tag assignments changed.
  translationHistoryPreviewHtml = function translationTagHistoryPreview(h) {
    const before = h?.before?.pairs || [];
    const after = h?.after?.pairs || [];
    const key = (pair) => `${dictNorm(pair.en)}\u0000${dictNorm(pair.zh)}`;
    const beforeMap = new Map(before.map((pair) => [key(pair), pair]));
    const afterMap = new Map(after.map((pair) => [key(pair), pair]));
    const removed = [...beforeMap].filter(([pairKey]) => !afterMap.has(pairKey)).map(([, pair]) => pair);
    const added = [...afterMap].filter(([pairKey]) => !beforeMap.has(pairKey)).map(([, pair]) => pair);
    const changed = [...afterMap]
      .filter(([pairKey, pair]) => beforeMap.has(pairKey)
        && JSON.stringify(beforeMap.get(pairKey).tags || []) !== JSON.stringify(pair.tags || []))
      .map(([, pair]) => pair);
    const rows = (items, empty) => items.length
      ? `<div class="order-diff-list">${items.slice(0, 40).map((pair) => `<div class="order-diff-row changed"><span class="order-diff-name">${esc(pair.en)} ↔ ${esc(pair.zh)}</span>${(pair.tags || []).length ? `<span class="muted">${(pair.tags || []).map(tagLabel).map(esc).join(' · ')}</span>` : ''}</div>`).join('')}${items.length > 40 ? `<div class="muted">另有 ${items.length - 40} 組未展開</div>` : ''}</div>`
      : `<p class="muted">${empty}</p>`;
    return `<div class="preview-card"><div class="order-diff-summary"><strong>中英對照表變更</strong><span class="tag">${before.length} → ${after.length} 組</span><span class="tag">標籤 ${(h?.before?.tags || []).length} → ${(h?.after?.tags || []).length}</span></div><div class="preview-columns"><div><h4>移除／修改前</h4>${rows(removed, '沒有移除的對照')}</div><div><h4>新增／標籤異動後</h4>${rows([...added, ...changed], '沒有新增或標籤異動')}</div></div></div>`;
  };

  // Replace the legacy category handlers with the tag UI handlers.
  $('#dictionarySearch').oninput = renderDictionary;
  $('#dictionaryCategory').onchange = () => {};
  $('#dictionaryTagFilters').onclick = (event) => {
    const button = event.target.closest('[data-filter-tag],[data-clear-tag-filters]');
    if (!button) return;
    if (button.dataset.clearTagFilters !== undefined) tagSelectedFilters.clear();
    else {
      const id = button.dataset.filterTag;
      if (tagSelectedFilters.has(id)) tagSelectedFilters.delete(id);
      else tagSelectedFilters.add(id);
    }
    renderDictionary();
  };
  $('#toggleTagManager').onclick = () => {
    $('#tagManager').hidden = !$('#tagManager').hidden;
  };
  $('#addPair').onclick = () => {
    let initialTags = [...tagSelectedFilters].filter((id) => tagMap().has(id));
    if (!initialTags.length) {
      initialTags = tagMap().has('other') ? ['other'] : [tagDefinitions()[0]?.id].filter(Boolean);
    }
    translations.pairs.unshift({ tags: initialTags, en: '', zh: '' });
    saveDictionaryLocal();
    renderAll();
    switchTab('dictionary');
  };
  $('#resetDictionary').onclick = () => {
    if (!confirm('放棄尚未送出的對照表與標籤修改？')) return;
    translations = clone(originalTranslations);
    tagSelectedFilters.clear();
    ignoredAudits.clear();
    saveIgnoredAudits();
    saveDictionaryLocal();
    renderAll();
  };
  $('#addTag').onclick = () => {
    const zhValue = $('#newTagZh').value.trim();
    const enValue = $('#newTagEn').value.trim();
    if (!zhValue || !enValue) return flash('請填寫標籤的中英文名稱');
    const id = makeTagId(enValue);
    translations.tags.push({ id, label: { en: enValue, zh: zhValue } });
    $('#newTagZh').value = '';
    $('#newTagEn').value = '';
    saveDictionaryLocal();
    renderDictionary();
    return flash('已新增標籤');
  };

  $('#tagManagerRows').oninput = (event) => {
    const index = Number(event.target.dataset.tagIndex);
    const language = event.target.dataset.tagLabel;
    if (Number.isInteger(index) && language && translations.tags[index]) {
      translations.tags[index].label[language] = event.target.value;
      saveDictionaryLocal();
      renderPreview(false);
    }
  };
  $('#tagManagerRows').onchange = (event) => {
    if (event.target.dataset.tagLabel) renderDictionary();
  };
  $('#tagManagerRows').onclick = (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.tagUp !== undefined || button.dataset.tagDown !== undefined) {
      const index = Number(button.dataset.tagUp ?? button.dataset.tagDown);
      const next = index + (button.dataset.tagUp !== undefined ? -1 : 1);
      if (translations.tags[index] && translations.tags[next]) {
        [translations.tags[index], translations.tags[next]] = [translations.tags[next], translations.tags[index]];
        saveDictionaryLocal();
        renderDictionary();
      }
      return;
    }
    if (button.dataset.mergeTag) {
      const source = button.dataset.mergeTag;
      const select = document.querySelector(`[data-merge-target="${source}"]`);
      const target = select?.value;
      if (!target) return flash('請先選擇要合併到哪個標籤');
      if (!confirm(`將「${tagLabel(source)}」合併到「${tagLabel(target)}」？`)) return;
      for (const pair of translations.pairs || []) {
        if ((pair.tags || []).includes(source)) {
          pair.tags = [...new Set(pair.tags.map((id) => id === source ? target : id))];
          normalizePairTags(pair);
        }
      }
      translations.tags = translations.tags.filter((item) => item.id !== source);
      tagSelectedFilters.delete(source);
      saveDictionaryLocal();
      renderDictionary();
      return flash('標籤已合併');
    }
    if (button.dataset.deleteTag) {
      const id = button.dataset.deleteTag;
      const count = (translations.pairs || []).filter((pair) => (pair.tags || []).includes(id)).length;
      if (!confirm(`刪除標籤「${tagLabel(id)}」？${count ? `\n${count} 筆詞條會移除此標籤。` : ''}`)) return;
      translations.tags = translations.tags.filter((item) => item.id !== id);
      const fallback = translations.tags.find((item) => item.id === 'other')?.id || translations.tags[0]?.id;
      for (const pair of translations.pairs || []) {
        pair.tags = (pair.tags || []).filter((tag) => tag !== id);
        if (!pair.tags.length && fallback) pair.tags = [fallback];
      }
      tagSelectedFilters.delete(id);
      saveDictionaryLocal();
      renderDictionary();
      return flash('標籤已刪除');
    }
  };

  $('#dictionaryRows').oninput = (event) => {
    const index = Number(event.target.dataset.i);
    const key = event.target.dataset.dict;
    if (Number.isInteger(index) && key && translations.pairs[index]) {
      translations.pairs[index][key] = event.target.value;
      saveDictionaryLocal();
    }
    renderPreview(false);
  };
  $('#dictionaryRows').onchange = (event) => {
    const index = Number(event.target.dataset.i);
    const id = event.target.dataset.pairTag;
    if (Number.isInteger(index) && id && translations.pairs[index]) {
      const tags = new Set(translations.pairs[index].tags || []);
      if (event.target.checked) {
        if (id === 'other') {
          tags.clear();
          tags.add('other');
        } else {
          tags.delete('other');
          tags.add(id);
        }
      } else tags.delete(id);
      translations.pairs[index].tags = [...tags];
      normalizePairTags(translations.pairs[index]);
      saveDictionaryLocal();
    }
    renderDictionary();
    renderPreview(false);
  };
  $('#dictionaryRows').onclick = (event) => {
    const edit = event.target.closest('[data-edit-pair-tags]');
    if (edit) {
      const index = Number(edit.dataset.editPairTags);
      const editor = document.querySelector(`[data-tag-editor="${index}"]`);
      if (!editor || !translations.pairs[index]) return;
      editor.hidden = !editor.hidden;
      if (!editor.hidden) editor.innerHTML = tagCheckboxes(translations.pairs[index], index);
      return;
    }
    const button = event.target.closest('[data-remove-pair]');
    if (!button) return;
    translations.pairs.splice(Number(button.dataset.removePair), 1);
    saveDictionaryLocal();
    renderAll();
  };

  $('#translationAudit').onclick = (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    const active = tagAuditItems.filter((item) => !ignoredAudits.has(item.signature));
    if (button.dataset.auditApply !== undefined) {
      const item = active[Number(button.dataset.auditApply)];
      if (item) applyAuditItems([item]);
    } else if (button.dataset.auditIgnore !== undefined) {
      const item = active[Number(button.dataset.auditIgnore)];
      if (item) {
        ignoredAudits.add(item.signature);
        saveIgnoredAudits();
        renderDictionary();
      }
    } else if (button.dataset.auditApplyAll !== undefined) {
      applyAuditItems(active);
    } else if (button.dataset.auditIgnoreAll !== undefined) {
      active.forEach((item) => ignoredAudits.add(item.signature));
      saveIgnoredAudits();
      renderDictionary();
    } else if (button.dataset.auditClearIgnore !== undefined) {
      ignoredAudits.clear();
      saveIgnoredAudits();
      renderDictionary();
    }
  };

  async function encodeBatchForGitHub(batch) {
    const jsonText = JSON.stringify(batch);
    if (jsonText.length < 48000) return { text: jsonText, compressed: false, rawLength: jsonText.length };
    if (typeof CompressionStream !== 'function') {
      throw new Error('目前瀏覽器不支援大型批次壓縮；請改用最新版 Chrome、Edge 或 Safari。');
    }
    const source = new Blob([jsonText]).stream();
    const compressed = source.pipeThrough(new CompressionStream('gzip'));
    const bytes = new Uint8Array(await new Response(compressed).arrayBuffer());
    let binary = '';
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
    }
    const text = `gzip-base64:${btoa(binary)}`;
    if (text.length > 64000) {
      throw new Error(`壓縮後仍有 ${text.length.toLocaleString()} 字元，超過 GitHub 欄位限制。請把內容分成兩次送出。`);
    }
    return { text, compressed: true, rawLength: jsonText.length };
  }

  async function copyBatchPayload() {
    try {
      const encoded = await encodeBatchForGitHub(payload());
      const ok = await copyText(encoded.text);
      if (ok && encoded.compressed) flash(`已複製壓縮批次（${encoded.rawLength.toLocaleString()} → ${encoded.text.length.toLocaleString()} 字元）`);
    } catch (error) {
      flash(error.message || String(error));
    }
  }

  async function submitBatchWithCompression() {
    const errors = validateDictionary();
    const batch = payload();
    if (errors.length) return flash('請先修正中英對照表衝突');
    if (!batch.operations.length) return flash('尚無變更');
    const raw = JSON.stringify(batch);
    const body = `### Batch payload / 批次資料\n\n\`\`\`json\n${raw}\n\`\`\``;
    const url = `${REPO}/issues/new?title=${encodeURIComponent(`[Website: Batch] ${new Date().toLocaleString('zh-TW')}`)}&body=${encodeURIComponent(body)}`;
    if (batch.operations.length <= 3 && url.length < 5500) return openIssue(url);
    try {
      const encoded = await encodeBatchForGitHub(batch);
      if (!await copyText(encoded.text)) return;
      if (openIssue(`${REPO}/issues/new?template=batch-changes.yml`)) {
        flash(encoded.compressed
          ? `批次已壓縮至 ${encoded.text.length.toLocaleString()} 字元；請貼入唯一欄位`
          : '批次較大：已複製 JSON，請貼入唯一欄位');
      }
    } catch (error) {
      flash(error.message || String(error));
    }
  }

  normalizeAllPairTags();
  $('#copyPayload').onclick = copyBatchPayload;
  $('#submitBatch').onclick = submitBatchWithCompression;

})();
