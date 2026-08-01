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
    conference: [['title', '名稱'], ['role', '會議身分'], ['venue', '場地／機構'], ['city', '城市'], ['country', '國家']],
    organization: [['title', '活動名稱'], ['organization_kind', '活動類型'], ['role', '籌辦身分'], ['venue', '機構／場地'], ['city', '城市'], ['country', '國家']],
    talk: [['title', '題目'], ['event', '活動／研討會'], ['venue', '機構／場地'], ['city', '城市'], ['country', '國家']],
    visit: [['title', '訪問機構'], ['city', '城市'], ['country', '國家'], ['visit_description', '其他說明'], ['funding_organization', '資助機構'], ['funding_program', '資助計畫']],
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
    if (['conference', 'talk', 'visit', 'organization'].includes(record.type)) {
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

  // Detailed translation and tag diff used by both the current draft preview
  // and the change-history preview.
  function translationDiffTagMap(data) {
    return new Map((Array.isArray(data?.tags) ? data.tags : []).map((item) => [item.id, item]));
  }

  function translationDiffTagLabel(data, id) {
    const item = translationDiffTagMap(data).get(id);
    const zh = String(item?.label?.zh || '').trim();
    const en = String(item?.label?.en || '').trim();
    if (zh && en && dictNorm(zh) !== dictNorm(en)) return `${zh} / ${en}`;
    return zh || en || id;
  }

  function translationDiffPairKey(pair) {
    return `${dictNorm(pair?.en)}\u0000${dictNorm(pair?.zh)}`;
  }

  function translationDiffTagIds(pair) {
    return [...new Set(Array.isArray(pair?.tags) ? pair.tags : [])].sort();
  }

  function translationDiffSameTags(left, right) {
    return JSON.stringify(translationDiffTagIds(left)) === JSON.stringify(translationDiffTagIds(right));
  }

  function translationDiffData(beforeData, afterData) {
    const beforePairs = Array.isArray(beforeData?.pairs) ? beforeData.pairs : [];
    const afterPairs = Array.isArray(afterData?.pairs) ? afterData.pairs : [];
    const matchedBefore = new Set();
    const matchedAfter = new Set();
    const matches = [];
    const afterByKey = new Map(afterPairs.map((pair, index) => [translationDiffPairKey(pair), index]));

    function addMatch(beforeIndex, afterIndex, reason) {
      if (matchedBefore.has(beforeIndex) || matchedAfter.has(afterIndex)) return false;
      matchedBefore.add(beforeIndex);
      matchedAfter.add(afterIndex);
      matches.push({ beforeIndex, afterIndex, reason });
      return true;
    }

    // First match unchanged text exactly.
    beforePairs.forEach((pair, beforeIndex) => {
      const afterIndex = afterByKey.get(translationDiffPairKey(pair));
      if (afterIndex !== undefined) addMatch(beforeIndex, afterIndex, 'exact');
    });

    // Then match rows where either English or Chinese stayed the same. This
    // identifies ordinary one-sided spelling/translation edits.
    const unmatchedAfterByEn = new Map();
    const unmatchedAfterByZh = new Map();
    afterPairs.forEach((pair, afterIndex) => {
      if (matchedAfter.has(afterIndex)) return;
      const enKey = dictNorm(pair.en);
      const zhKey = dictNorm(pair.zh);
      if (enKey) {
        const rows = unmatchedAfterByEn.get(enKey) || [];
        rows.push(afterIndex);
        unmatchedAfterByEn.set(enKey, rows);
      }
      if (zhKey) {
        const rows = unmatchedAfterByZh.get(zhKey) || [];
        rows.push(afterIndex);
        unmatchedAfterByZh.set(zhKey, rows);
      }
    });
    beforePairs.forEach((pair, beforeIndex) => {
      if (matchedBefore.has(beforeIndex)) return;
      const candidates = new Set([
        ...(unmatchedAfterByEn.get(dictNorm(pair.en)) || []),
        ...(unmatchedAfterByZh.get(dictNorm(pair.zh)) || []),
      ].filter((afterIndex) => !matchedAfter.has(afterIndex)));
      if (candidates.size === 1) addMatch(beforeIndex, [...candidates][0], 'one-side');
    });

    // When the number of remaining rows is equal, preserve row order so that
    // editing both languages in one row is still shown as a modification.
    const remainingBefore = beforePairs.map((_, index) => index).filter((index) => !matchedBefore.has(index));
    const remainingAfter = afterPairs.map((_, index) => index).filter((index) => !matchedAfter.has(index));
    if (remainingBefore.length && remainingBefore.length === remainingAfter.length) {
      remainingBefore.forEach((beforeIndex, offset) => {
        const afterIndex = remainingAfter[offset];
        if (translationDiffSameTags(beforePairs[beforeIndex], afterPairs[afterIndex])) {
          addMatch(beforeIndex, afterIndex, 'row-order');
        }
      });
    }

    const textChanges = [];
    const pairTagChanges = [];
    for (const match of matches) {
      const before = beforePairs[match.beforeIndex];
      const after = afterPairs[match.afterIndex];
      const textChanged = translationDiffPairKey(before) !== translationDiffPairKey(after);
      const tagsChanged = !translationDiffSameTags(before, after);
      if (textChanged) textChanges.push({ ...match, before, after, tagsChanged });
      else if (tagsChanged) pairTagChanges.push({ ...match, before, after });
    }

    const removedPairs = beforePairs
      .map((pair, index) => ({ pair, index }))
      .filter(({ index }) => !matchedBefore.has(index));
    const addedPairs = afterPairs
      .map((pair, index) => ({ pair, index }))
      .filter(({ index }) => !matchedAfter.has(index));

    const beforeTags = Array.isArray(beforeData?.tags) ? beforeData.tags : [];
    const afterTags = Array.isArray(afterData?.tags) ? afterData.tags : [];
    const beforeTagMap = new Map(beforeTags.map((item) => [item.id, item]));
    const afterTagMap = new Map(afterTags.map((item) => [item.id, item]));
    const addedTags = afterTags.filter((item) => !beforeTagMap.has(item.id));
    const removedTags = beforeTags.filter((item) => !afterTagMap.has(item.id));
    const renamedTags = afterTags
      .filter((item) => beforeTagMap.has(item.id))
      .filter((item) => {
        const before = beforeTagMap.get(item.id);
        return String(before?.label?.en || '') !== String(item?.label?.en || '')
          || String(before?.label?.zh || '') !== String(item?.label?.zh || '');
      })
      .map((after) => ({ before: beforeTagMap.get(after.id), after }));
    const commonBeforeOrder = beforeTags.map((item) => item.id).filter((id) => afterTagMap.has(id));
    const commonAfterOrder = afterTags.map((item) => item.id).filter((id) => beforeTagMap.has(id));
    const tagOrderChanged = JSON.stringify(commonBeforeOrder) !== JSON.stringify(commonAfterOrder);

    return {
      beforePairs,
      afterPairs,
      beforeTags,
      afterTags,
      textChanges,
      pairTagChanges,
      removedPairs,
      addedPairs,
      addedTags,
      removedTags,
      renamedTags,
      tagOrderChanged,
      commonBeforeOrder,
      commonAfterOrder,
    };
  }

  function translationDiffTagChips(data, pair) {
    const ids = Array.isArray(pair?.tags) ? pair.tags : [];
    return ids.length
      ? `<div class="translation-diff-chips">${ids.map((id) => `<span class="tag-pill">${esc(translationDiffTagLabel(data, id))}</span>`).join('')}</div>`
      : '<span class="muted">沒有標籤</span>';
  }

  function translationDiffPairSide(data, pair, label, otherPair = null) {
    const enChanged = otherPair && String(pair?.en || '') !== String(otherPair?.en || '');
    const zhChanged = otherPair && String(pair?.zh || '') !== String(otherPair?.zh || '');
    const tagsChanged = otherPair && !translationDiffSameTags(pair, otherPair);
    return `<div class="translation-diff-side">
      <div class="translation-diff-side-title">${esc(label)}</div>
      <div class="translation-diff-field ${enChanged ? 'changed' : ''}"><strong>英文</strong><div class="translation-diff-value"><span>${esc(pair?.en || '—')}</span>${enChanged ? '<em class="translation-diff-change-label">已修改</em>' : ''}</div></div>
      <div class="translation-diff-field ${zhChanged ? 'changed' : ''}"><strong>中文</strong><div class="translation-diff-value"><span>${esc(pair?.zh || '—')}</span>${zhChanged ? '<em class="translation-diff-change-label">已修改</em>' : ''}</div></div>
      <div class="translation-diff-field ${tagsChanged ? 'changed' : ''}"><strong>標籤</strong><div class="translation-diff-value">${translationDiffTagChips(data, pair)}${tagsChanged ? '<em class="translation-diff-change-label">已修改</em>' : ''}</div></div>
    </div>`;
  }

  function translationDiffPairComparison(beforeData, afterData, beforePair, afterPair, titleText) {
    return `<div class="translation-diff-item">
      <div class="translation-diff-item-title">${esc(titleText)}</div>
      <div class="translation-diff-grid">
        ${translationDiffPairSide(beforeData, beforePair, '修改前', afterPair)}
        ${translationDiffPairSide(afterData, afterPair, '修改後', beforePair)}
      </div>
    </div>`;
  }

  function translationDiffSinglePair(data, pair, state) {
    return `<div class="translation-diff-item ${state === '新增' ? 'is-added' : 'is-removed'}">
      <div class="translation-diff-item-title">${esc(state)}</div>
      ${translationDiffPairSide(data, pair, state)}
    </div>`;
  }

  function translationDiffSection(titleText, itemsHtml, count, open = true) {
    if (!count) return '';
    return `<details class="translation-diff-section" ${open ? 'open' : ''}>
      <summary><strong>${esc(titleText)}</strong><span class="tag">${count}</span></summary>
      <div class="translation-diff-list">${itemsHtml}</div>
    </details>`;
  }

  function translationDiffTagDefinition(data, item, state) {
    const zh = String(item?.label?.zh || '');
    const en = String(item?.label?.en || '');
    return `<div class="translation-diff-item ${state === '新增' ? 'is-added' : state === '刪除' ? 'is-removed' : ''}">
      <div class="translation-diff-item-title">${esc(state)} · <code>${esc(item?.id || '')}</code></div>
      <div class="translation-diff-field"><strong>中文</strong><span>${esc(zh || '—')}</span></div>
      <div class="translation-diff-field"><strong>英文</strong><span>${esc(en || '—')}</span></div>
    </div>`;
  }

  function translationDetailedDiffHtml(beforeData, afterData) {
    const diff = translationDiffData(beforeData || {}, afterData || {});
    const totalChanges = diff.textChanges.length + diff.pairTagChanges.length
      + diff.removedPairs.length + diff.addedPairs.length + diff.addedTags.length
      + diff.removedTags.length + diff.renamedTags.length + (diff.tagOrderChanged ? 1 : 0);
    const summary = `<div class="order-diff-summary">
      <strong>中英對照與標籤變更</strong>
      <span class="tag">詞條 ${diff.beforePairs.length} → ${diff.afterPairs.length}</span>
      <span class="tag">標籤 ${diff.beforeTags.length} → ${diff.afterTags.length}</span>
      <span class="tag">共 ${totalChanges} 類／筆變更</span>
    </div>`;
    if (!totalChanges) return `<div class="preview-card">${summary}<p class="muted">修改前後內容完全相同。</p></div>`;

    const textChangeHtml = diff.textChanges.map((item, index) => translationDiffPairComparison(
      beforeData, afterData, item.before, item.after, `詞條內容修改 ${index + 1}`,
    )).join('');
    const pairTagChangeHtml = diff.pairTagChanges.map((item, index) => translationDiffPairComparison(
      beforeData, afterData, item.before, item.after, `詞條標籤修改 ${index + 1}`,
    )).join('');
    const addedPairHtml = diff.addedPairs.map(({ pair }) => translationDiffSinglePair(afterData, pair, '新增')).join('');
    const removedPairHtml = diff.removedPairs.map(({ pair }) => translationDiffSinglePair(beforeData, pair, '刪除')).join('');
    const addedTagHtml = diff.addedTags.map((item) => translationDiffTagDefinition(afterData, item, '新增')).join('');
    const removedTagHtml = diff.removedTags.map((item) => translationDiffTagDefinition(beforeData, item, '刪除')).join('');
    const renamedTagHtml = diff.renamedTags.map(({ before, after }) => `<div class="translation-diff-item">
      <div class="translation-diff-item-title">標籤名稱修改 · <code>${esc(after.id)}</code></div>
      <div class="translation-diff-grid">
        ${translationDiffTagDefinition(beforeData, before, '修改前')}
        ${translationDiffTagDefinition(afterData, after, '修改後')}
      </div>
    </div>`).join('');
    const tagOrderHtml = diff.tagOrderChanged ? `<div class="translation-diff-item">
      <div class="translation-diff-item-title">標籤顯示順序修改</div>
      <div class="translation-diff-grid">
        <div class="translation-diff-side"><div class="translation-diff-side-title">修改前</div><ol class="translation-diff-order">${diff.commonBeforeOrder.map((id) => `<li>${esc(translationDiffTagLabel(beforeData, id))} <code>${esc(id)}</code></li>`).join('')}</ol></div>
        <div class="translation-diff-side"><div class="translation-diff-side-title">修改後</div><ol class="translation-diff-order">${diff.commonAfterOrder.map((id) => `<li>${esc(translationDiffTagLabel(afterData, id))} <code>${esc(id)}</code></li>`).join('')}</ol></div>
      </div>
    </div>` : '';

    const openAll = totalChanges <= 30;
    return `<div class="preview-card translation-diff-preview">${summary}<p class="translation-diff-guide">逐欄比較修改前後內容；黃色欄位與「已修改」標記就是實際變動的位置。新增與刪除會分開列出。</p>
      ${translationDiffSection('詞條文字修改', textChangeHtml, diff.textChanges.length, openAll)}
      ${translationDiffSection('詞條標籤修改', pairTagChangeHtml, diff.pairTagChanges.length, openAll)}
      ${translationDiffSection('新增詞條', addedPairHtml, diff.addedPairs.length, openAll)}
      ${translationDiffSection('刪除詞條', removedPairHtml, diff.removedPairs.length, openAll)}
      ${translationDiffSection('新增標籤', addedTagHtml, diff.addedTags.length, openAll)}
      ${translationDiffSection('刪除標籤', removedTagHtml, diff.removedTags.length, openAll)}
      ${translationDiffSection('標籤名稱修改', renamedTagHtml, diff.renamedTags.length, openAll)}
      ${translationDiffSection('標籤順序修改', tagOrderHtml, diff.tagOrderChanged ? 1 : 0, openAll)}
    </div>`;
  }

  function translationDiffSummaryText(beforeData, afterData) {
    const diff = translationDiffData(beforeData || {}, afterData || {});
    const parts = [];
    if (diff.textChanges.length) parts.push(`文字修改 ${diff.textChanges.length}`);
    if (diff.pairTagChanges.length) parts.push(`詞條標籤修改 ${diff.pairTagChanges.length}`);
    if (diff.addedPairs.length) parts.push(`新增詞條 ${diff.addedPairs.length}`);
    if (diff.removedPairs.length) parts.push(`刪除詞條 ${diff.removedPairs.length}`);
    if (diff.addedTags.length) parts.push(`新增標籤 ${diff.addedTags.length}`);
    if (diff.removedTags.length) parts.push(`刪除標籤 ${diff.removedTags.length}`);
    if (diff.renamedTags.length) parts.push(`標籤改名 ${diff.renamedTags.length}`);
    if (diff.tagOrderChanged) parts.push('標籤順序修改');
    return parts.join('、') || '內容相同';
  }

  function installTranslationDiffStyles() {
    if (document.getElementById('translationDetailedDiffStyles')) return;
    const style = document.createElement('style');
    style.id = 'translationDetailedDiffStyles';
    style.textContent = `
      .translation-diff-preview{display:grid;gap:10px}
      .translation-diff-section{border:1px solid #dfd3ca;border-radius:10px;background:#fff;overflow:hidden}
      .translation-diff-section>summary{display:flex;gap:8px;align-items:center;cursor:pointer;padding:10px 12px;background:#f8f3ef}
      .translation-diff-list{display:grid;gap:10px;padding:10px;max-height:620px;overflow:auto}
      .translation-diff-item{border:1px solid #e3d8cf;border-radius:10px;padding:10px;background:#fcfaf8}
      .translation-diff-item.is-added{box-shadow:inset 4px 0 #247a46}
      .translation-diff-item.is-removed{box-shadow:inset 4px 0 #a1342b}
      .translation-diff-item-title{font-weight:800;margin-bottom:8px;overflow-wrap:anywhere}
      .translation-diff-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px}
      .translation-diff-side{border:1px solid #e7ddd5;border-radius:9px;padding:9px;background:#fff;min-width:0}
      .translation-diff-side-title{font-size:.75rem;font-weight:800;color:#6e625a;margin-bottom:6px}
      .translation-diff-field{display:grid;grid-template-columns:54px minmax(0,1fr);gap:8px;padding:5px 0;border-top:1px solid #f0e8e2;min-width:0}
      .translation-diff-field:first-of-type{border-top:0}
      .translation-diff-field.changed{background:#fff7dc;margin:0 -5px;padding:5px;border-radius:6px}
      .translation-diff-field strong{font-size:.75rem;color:#6e625a}
      .translation-diff-value{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;min-width:0}
      .translation-diff-value>span{overflow-wrap:anywhere;min-width:0}
      .translation-diff-change-label{flex:0 0 auto;border-radius:999px;background:#9a6700;color:#fff;padding:2px 7px;font-size:.67rem;font-style:normal;font-weight:900}
      .translation-diff-guide{margin:0;padding:9px 11px;border-radius:8px;background:#fff7dc;color:#654b10;font-size:.78rem}
      .translation-diff-chips{display:flex;gap:4px;flex-wrap:wrap}
      .translation-diff-order{margin:0;padding-left:22px;display:grid;gap:4px}
      .translation-diff-item code,.translation-diff-order code{font-size:.72rem;color:#766c65}
      @media(max-width:700px){.translation-diff-grid{grid-template-columns:1fr}}
    `;
    document.head.append(style);
  }

  installTranslationDiffStyles();

  translationHistoryPreviewHtml = function translationTagHistoryPreview(h) {
    return translationDetailedDiffHtml(h?.before || {}, h?.after || {});
  };

  // The legacy draft preview only showed pair counts. Keep the rest of its
  // rendering intact, then replace the translation operation with the full diff.
  const renderPreviewWithoutDetailedTranslationDiff = renderPreview;
  renderPreview = function renderPreviewWithDetailedTranslationDiff(refreshDictionary = true) {
    renderPreviewWithoutDetailedTranslationDiff(refreshDictionary);
    const operation = payload().operations.find((item) => item.op === 'translations');
    if (!operation) return;
    const details = $('#preview').querySelector('[data-preview-operation="translations"]');
    if (!details) return;
    details.innerHTML = `<summary><strong>中英對照</strong>：${esc(translationDiffSummaryText(operation.before, operation.after))}</summary>${translationDetailedDiffHtml(operation.before, operation.after)}`;
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
    renderPreview();
    return flash('已新增標籤，草稿預覽已更新');
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
        renderPreview();
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
      renderPreview();
      return flash('標籤已合併，草稿預覽已更新');
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
      renderPreview();
      return flash('標籤已刪除，草稿預覽已更新');
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

  // Import/export translation words and tags as a local draft. Nothing is
  // written to GitHub until the ordinary batch submission is confirmed.
  let translationImportCandidate = null;
  let translationImportFilename = '';

  function installTranslationImportStyles() {
    if (document.getElementById('translationImportStyles')) return;
    const style = document.createElement('style');
    style.id = 'translationImportStyles';
    style.textContent = `
      .translation-import-panel{border:1px solid #cfc1b7;border-radius:13px;padding:13px;background:#f8f3ef;margin:12px 0}
      .translation-import-panel h3{margin:0 0 5px}
      .translation-import-grid{display:grid;grid-template-columns:minmax(220px,1.4fr) minmax(210px,1fr);gap:10px;align-items:end}
      .translation-import-actions{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-top:9px}
      .translation-import-file{padding:8px;border:1px dashed #bcaea4;border-radius:9px;background:#fff;width:100%}
      .translation-import-preview{margin-top:11px}
      .translation-import-preview:empty{display:none}
      .translation-import-format{font:11px ui-monospace,monospace;background:#fff;border:1px solid #ded3ca;border-radius:8px;padding:8px;white-space:pre-wrap;word-break:break-word;margin-top:8px}
      @media(max-width:700px){.translation-import-grid{grid-template-columns:1fr}}
    `;
    document.head.append(style);
  }

  function cleanImportLabel(item) {
    const label = item?.label && typeof item.label === 'object' ? item.label : item || {};
    return {
      en: String(label.en || '').trim(),
      zh: String(label.zh || '').trim(),
    };
  }

  function importTagId(value, fallbackLabel = '') {
    const raw = String(value || '').trim().toLowerCase();
    const cleaned = raw.replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
    if (/^[a-z0-9][a-z0-9_-]*$/.test(cleaned)) return cleaned;
    const fromLabel = norm(fallbackLabel).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return fromLabel || `tag-${Date.now().toString(36)}`;
  }

  function uniqueImportTagId(base, used) {
    let id = base;
    let suffix = 2;
    while (used.has(id)) id = `${base}-${suffix++}`;
    used.add(id);
    return id;
  }

  function normalizeImportPayload(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('匯入檔最外層必須是 JSON 物件。');
    const format = String(raw.format || '').trim();
    if (format && format !== 'hctsui-translation-import-v1') {
      throw new Error(`不支援的匯入格式：${format}`);
    }
    const tags = Array.isArray(raw.tags) ? raw.tags : [];
    const pairs = Array.isArray(raw.pairs) ? raw.pairs : [];
    if (!tags.length && !pairs.length && !Array.isArray(raw.remove_pairs) && !Array.isArray(raw.remove_tags)) {
      throw new Error('檔案中找不到 tags、pairs、remove_pairs 或 remove_tags。');
    }
    return {
      format: format || (raw.schema_version === 2 ? 'translations-schema-v2' : 'hctsui-translation-import-v1'),
      schema_version: 2,
      tags,
      pairs,
      remove_pairs: Array.isArray(raw.remove_pairs) ? raw.remove_pairs : [],
      remove_tags: Array.isArray(raw.remove_tags) ? raw.remove_tags : [],
      tag_order: Array.isArray(raw.tag_order) ? raw.tag_order : [],
      note: String(raw.note || '').trim(),
    };
  }

  function pairMatchIndex(pairs, spec) {
    const match = spec?.match && typeof spec.match === 'object' ? spec.match : spec || {};
    const enKey = dictNorm(match.en || match.match_en || '');
    const zhKey = dictNorm(match.zh || match.match_zh || '');
    const enMatches = enKey ? pairs.map((pair, index) => dictNorm(pair.en) === enKey ? index : -1).filter((index) => index >= 0) : [];
    const zhMatches = zhKey ? pairs.map((pair, index) => dictNorm(pair.zh) === zhKey ? index : -1).filter((index) => index >= 0) : [];
    if (enMatches.length > 1 || zhMatches.length > 1) throw new Error('現有對照表有重複詞條，無法安全判定匯入目標。');
    if (enMatches.length && zhMatches.length && enMatches[0] !== zhMatches[0]) {
      throw new Error(`匯入詞條的英文與中文分別命中不同現有詞條：${match.en || ''} ↔ ${match.zh || ''}`);
    }
    return enMatches[0] ?? zhMatches[0] ?? -1;
  }

  function resolveImportedTags(candidate, importedTags, warnings) {
    const used = new Set(candidate.tags.map((item) => item.id));
    const idMap = new Map();
    for (const rawTag of importedTags) {
      const label = cleanImportLabel(rawTag);
      const requestedId = importTagId(rawTag?.id, label.en);
      let existing = candidate.tags.find((item) => item.id === requestedId);
      if (!existing && (label.en || label.zh)) {
        const both = candidate.tags.filter((item) => (
          (!label.en || dictNorm(item.label?.en) === dictNorm(label.en))
          && (!label.zh || dictNorm(item.label?.zh) === dictNorm(label.zh))
        ));
        if (both.length === 1) existing = both[0];
      }
      if (existing) {
        idMap.set(String(rawTag?.id || requestedId), existing.id);
        if (label.en) existing.label.en = label.en;
        if (label.zh) existing.label.zh = label.zh;
      } else {
        const id = uniqueImportTagId(requestedId, used);
        candidate.tags.push({ id, label });
        idMap.set(String(rawTag?.id || requestedId), id);
        if (id !== requestedId) warnings.push(`標籤 ID「${requestedId}」已存在，匯入時改為「${id}」。`);
      }
    }
    for (const item of candidate.tags) idMap.set(item.id, item.id);
    return idMap;
  }

  function mapImportTagIds(ids, idMap, candidate, warnings) {
    const valid = new Set(candidate.tags.map((item) => item.id));
    const result = [];
    for (const raw of Array.isArray(ids) ? ids : []) {
      const source = String(raw || '').trim();
      const mapped = idMap.get(source) || source;
      if (!valid.has(mapped)) {
        warnings.push(`詞條參照不存在的標籤「${source}」，已忽略。`);
        continue;
      }
      if (!result.includes(mapped)) result.push(mapped);
    }
    return result;
  }

  function removeImportedPairs(candidate, rows) {
    for (const row of rows) {
      const index = pairMatchIndex(candidate.pairs, row);
      if (index >= 0) candidate.pairs.splice(index, 1);
    }
  }

  function removeImportedTags(candidate, rows, idMap, warnings) {
    for (const row of rows) {
      const sourceRaw = typeof row === 'string' ? row : row?.id;
      const targetRaw = typeof row === 'object' ? row?.merge_into : '';
      const source = idMap.get(String(sourceRaw || '')) || String(sourceRaw || '');
      const target = idMap.get(String(targetRaw || '')) || String(targetRaw || '');
      if (!candidate.tags.some((item) => item.id === source)) {
        warnings.push(`要刪除的標籤「${sourceRaw || ''}」不存在，已略過。`);
        continue;
      }
      if (target && !candidate.tags.some((item) => item.id === target)) {
        throw new Error(`標籤「${sourceRaw}」指定的合併目標「${targetRaw}」不存在。`);
      }
      for (const pair of candidate.pairs) {
        const next = [];
        for (const id of pair.tags || []) {
          if (id === source) {
            if (target && !next.includes(target)) next.push(target);
          } else if (!next.includes(id)) next.push(id);
        }
        pair.tags = next;
      }
      candidate.tags = candidate.tags.filter((item) => item.id !== source);
    }
  }

  function applyImportedTagOrder(candidate, order, idMap) {
    if (!order.length) return;
    const mapped = order.map((id) => idMap.get(String(id)) || String(id));
    const rank = new Map(mapped.map((id, index) => [id, index]));
    candidate.tags.sort((left, right) => {
      const a = rank.has(left.id) ? rank.get(left.id) : Number.MAX_SAFE_INTEGER;
      const b = rank.has(right.id) ? rank.get(right.id) : Number.MAX_SAFE_INTEGER;
      return a - b;
    });
  }

  function buildTranslationImportCandidate(raw, mode = 'merge') {
    const input = normalizeImportPayload(raw);
    const warnings = [];
    if (mode === 'replace') {
      if (!input.tags.length) throw new Error('完整取代模式必須包含完整 tags 陣列。');
      const candidate = { schema_version: 2, tags: [], pairs: [] };
      const idMap = resolveImportedTags(candidate, input.tags, warnings);
      for (const row of input.pairs) {
        const en = String(row?.en || '').trim();
        const zh = String(row?.zh || '').trim();
        const tags = mapImportTagIds(row?.tags, idMap, candidate, warnings);
        candidate.pairs.push({ en, zh, tags });
      }
      applyImportedTagOrder(candidate, input.tag_order, idMap);
      return { candidate, warnings, input };
    }

    const candidate = clone(translations);
    candidate.schema_version = 2;
    candidate.tags = Array.isArray(candidate.tags) ? candidate.tags : [];
    candidate.pairs = Array.isArray(candidate.pairs) ? candidate.pairs : [];
    const idMap = resolveImportedTags(candidate, input.tags, warnings);
    removeImportedPairs(candidate, input.remove_pairs);

    for (const row of input.pairs) {
      const en = String(row?.en || '').trim();
      const zh = String(row?.zh || '').trim();
      const lookup = row?.match && typeof row.match === 'object' ? row.match : { en, zh };
      const index = pairMatchIndex(candidate.pairs, lookup);
      const importedTagIds = mapImportTagIds(row?.tags, idMap, candidate, warnings);
      if (index >= 0) {
        const current = candidate.pairs[index];
        if (en) current.en = en;
        if (zh) current.zh = zh;
        const tagMode = String(row?.tag_mode || 'merge').toLowerCase();
        current.tags = tagMode === 'replace'
          ? importedTagIds
          : [...new Set([...(current.tags || []), ...importedTagIds])];
      } else {
        candidate.pairs.push({ en, zh, tags: importedTagIds });
      }
    }

    removeImportedTags(candidate, input.remove_tags, idMap, warnings);
    applyImportedTagOrder(candidate, input.tag_order, idMap);
    return { candidate, warnings, input };
  }

  function validateTranslationImportCandidate(candidate) {
    const previous = translations;
    try {
      translations = clone(candidate);
      const errors = validateDictionary();
      return { candidate: clone(translations), errors };
    } finally {
      translations = previous;
    }
  }

  function translationImportStatusHtml(kind, titleText, messages = []) {
    const className = kind === 'error' ? 'notice error' : kind === 'success' ? 'notice success' : 'notice';
    const list = messages.length ? `<ul>${messages.map((item) => `<li>${esc(item)}</li>`).join('')}</ul>` : '';
    return `<div class="${className}"><strong>${esc(titleText)}</strong>${list}</div>`;
  }

  function resetTranslationImportPanel(clearFile = true) {
    translationImportCandidate = null;
    translationImportFilename = '';
    $('#applyTranslationImport').disabled = true;
    $('#translationImportPreview').innerHTML = '';
    $('#translationImportStatus').innerHTML = '';
    if (clearFile) $('#translationImportFile').value = '';
  }

  async function analyzeTranslationImport() {
    const file = $('#translationImportFile').files?.[0];
    if (!file) return flash('請先選擇 JSON 檔案');
    resetTranslationImportPanel(false);
    translationImportFilename = file.name;
    try {
      const raw = JSON.parse(await file.text());
      const mode = $('#translationImportMode').value;
      const built = buildTranslationImportCandidate(raw, mode);
      const checked = validateTranslationImportCandidate(built.candidate);
      if (checked.errors.length) {
        $('#translationImportStatus').innerHTML = translationImportStatusHtml(
          'error',
          `無法匯入 ${file.name}：驗證失敗`,
          checked.errors.slice(0, 30),
        );
        return;
      }
      translationImportCandidate = checked.candidate;
      const diff = translationDiffData(translations, translationImportCandidate);
      const changeCount = diff.textChanges.length + diff.pairTagChanges.length + diff.addedPairs.length
        + diff.removedPairs.length + diff.addedTags.length + diff.removedTags.length
        + diff.renamedTags.length + (diff.tagOrderChanged ? 1 : 0);
      $('#translationImportStatus').innerHTML = translationImportStatusHtml(
        changeCount ? 'success' : '',
        changeCount
          ? `已讀取 ${file.name}；確認下方差異後，可套用為本機草稿。`
          : `已讀取 ${file.name}，但和目前草稿沒有差異。`,
        built.warnings,
      );
      $('#translationImportPreview').innerHTML = translationDetailedDiffHtml(translations, translationImportCandidate);
      $('#applyTranslationImport').disabled = !changeCount;
    } catch (error) {
      $('#translationImportStatus').innerHTML = translationImportStatusHtml('error', error.message || String(error));
    }
  }

  function applyTranslationImportDraft() {
    if (!translationImportCandidate) return flash('請先讀取並預覽匯入檔');
    translations = clone(translationImportCandidate);
    normalizeAllPairTags();
    saveDictionaryLocal();
    tagSelectedFilters.clear();
    renderAll();
    switchTab('dictionary');
    const name = translationImportFilename;
    resetTranslationImportPanel();
    flash(`已將 ${name || '匯入檔'} 套用為本機草稿；尚未送到 GitHub`);
  }

  function downloadTranslationJson(filename, value) {
    const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function translationImportTemplate() {
    return {
      format: 'hctsui-translation-import-v1',
      note: '此檔案在 Admin 選擇「合併」後，只會產生本機草稿。',
      tags: [
        { id: 'research-program', label: { en: 'Research Program', zh: '研究計畫' } },
      ],
      pairs: [
        { en: 'Example Program', zh: '範例計畫', tags: ['research-program'], tag_mode: 'merge' },
        { match: { en: 'Old spelling' }, en: 'New spelling', zh: '新譯名', tags: ['other'], tag_mode: 'replace' },
      ],
      remove_pairs: [
        { en: 'Term to remove' },
      ],
      remove_tags: [
        { id: 'old-tag', merge_into: 'other' },
      ],
      tag_order: ['institution', 'university', 'research-program', 'other'],
    };
  }

  function installTranslationImportHandlers() {
    installTranslationImportStyles();
    $('#toggleTranslationImport').onclick = () => {
      $('#translationImportPanel').hidden = !$('#translationImportPanel').hidden;
    };
    $('#analyzeTranslationImport').onclick = analyzeTranslationImport;
    $('#applyTranslationImport').onclick = applyTranslationImportDraft;
    $('#clearTranslationImport').onclick = () => resetTranslationImportPanel();
    $('#translationImportFile').onchange = () => {
      translationImportCandidate = null;
      $('#applyTranslationImport').disabled = true;
      $('#translationImportPreview').innerHTML = '';
      const file = $('#translationImportFile').files?.[0];
      $('#translationImportStatus').innerHTML = file
        ? translationImportStatusHtml('', `已選擇 ${file.name}；按「讀取並預覽」後才會解析。`)
        : '';
    };
    $('#translationImportMode').onchange = () => {
      if ($('#translationImportFile').files?.[0]) analyzeTranslationImport();
    };
    $('#exportTranslationDraft').onclick = () => downloadTranslationJson('translations-draft.json', translations);
    $('#downloadTranslationImportTemplate').onclick = () => downloadTranslationJson(
      'translation-import-template.json', translationImportTemplate(),
    );
  }

  // Exposed only for lightweight automated tests and for diagnosing malformed
  // import files in the browser console.
  window.__hctsuiTranslationImport = {
    buildCandidate: buildTranslationImportCandidate,
    validateCandidate: validateTranslationImportCandidate,
    template: translationImportTemplate,
  };

  installTranslationImportHandlers();

  normalizeAllPairTags();
  $('#copyPayload').onclick = copyBatchPayload;
  $('#submitBatch').onclick = submitBatchWithCompression;

})();
