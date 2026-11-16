(() => {
  'use strict';

  const PAGE_SIZE = 50;
  const state = {
    data: null,
    planId: 'az-complete-health',
    term: '',
    category: '',
    subcategory: '',
    coverage: '',
    limit: PAGE_SIZE,
  };

  const el = {};
  const ids = ['asOf', 'planInput', 'planOptions', 'medicationInput', 'medicationOptions',
    'categoryInput', 'categoryOptions', 'subcategoryInput', 'subcategoryOptions', 'coverageInput',
    'clearFilters', 'planStatus', 'planEvidence', 'evidenceList', 'resultCount', 'effectiveDate',
    'loadingState', 'emptyState', 'resultGrid', 'showMore',
    'criteriaLibrary', 'criteriaSearch', 'criteriaCount', 'criteriaResults'];

  const comboState = {
    plan: { activeIndex: -1, showAll: false },
    medication: { activeIndex: -1, showAll: false },
    category: { activeIndex: -1, showAll: false },
    subcategory: { activeIndex: -1, showAll: false },
  };

  const comboIds = {
    plan: ['planInput', 'planOptions'],
    medication: ['medicationInput', 'medicationOptions'],
    category: ['categoryInput', 'categoryOptions'],
    subcategory: ['subcategoryInput', 'subcategoryOptions'],
  };

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[char]);

  const normalize = (value) => String(value ?? '').trim().toLocaleLowerCase();
  const titleCase = (value) => String(value ?? '').toLocaleLowerCase().replace(/\b\w/g, (c) => c.toLocaleUpperCase());

  function sourceHref(record) {
    if (!record.sourceUrl) return '';
    const page = Number(record.sourcePage);
    return page > 0 ? `${record.sourceUrl}#page=${page}` : record.sourceUrl;
  }

  const planLoads = new Map();
  const loadedPlans = new Set();

  async function ensurePlanData(planId) {
    const file = state.data.planDataFiles?.[planId];
    if (!file || loadedPlans.has(planId)) return;
    if (!planLoads.has(planId)) {
      const request = (async () => {
        const response = await fetch(file);
        if (!response.ok) throw new Error('Plan data could not be loaded.');
        const bytes = new Uint8Array(await response.arrayBuffer());
        let datasetText;
        if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
          const decoded = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
          datasetText = await new Response(decoded).text();
        } else {
          datasetText = new TextDecoder().decode(bytes);
        }
        const records = JSON.parse(datasetText);
        if (!Array.isArray(records) || records.some((record) => record.planId !== planId)) {
          throw new Error('Plan data does not match the selected formulary.');
        }
        state.data.medications.push(...records);
        loadedPlans.add(planId);
      })();
      planLoads.set(planId, request);
      request.catch(() => planLoads.delete(planId));
    }
    await planLoads.get(planId);
  }

  // Keep one immutable statewide source, projected into the chosen plan for lookup.
  // This never turns an FFS policy index into plan-specific coverage evidence.
  const statewideProjectionCache = new Map();
  function inheritedStatewideRows() {
    if (!state.data.statewideDrugList?.length) return [];
    if (!statewideProjectionCache.has(state.planId)) {
      statewideProjectionCache.set(state.planId, state.data.statewideDrugList.map(record => ({
        ...record, id: `${state.planId}:statewide:${record.id}`,
        planId: state.planId, isStatewideReference: true
      })));
    }
    return statewideProjectionCache.get(state.planId);
  }

  function recordsForPlan() {
    return state.data.medications
      .filter((record) => record.planId === state.planId && record.recordType === 'formulary')
      .concat(inheritedStatewideRows());
  }

  // Presentation only: do not alter the original payer text or its coverage record.
  function readableMedicationName(value) {
    const keepUpper = new Set(['ER', 'XR', 'SR', 'IR', 'DR', 'ODT', 'HFA', 'DPI', 'NDC', 'IV', 'IM', 'SC', 'SQ', 'LA', 'XL', 'EC', 'CR', 'CD', 'U', 'NPH', 'GLP', 'DPP', 'SGLT2', 'HIV', 'ADHD', 'HCTZ', 'MDI', 'ICS', 'LABA', 'LAMA', 'PFS', 'USP', 'OTC']);
    const unitCase = {MG: 'mg', MCG: 'mcg', ML: 'mL', MEQ: 'mEq', GM: 'g', HCL: 'HCl', NACL: 'NaCl', HBR: 'HBr', KWIKPEN: 'KwikPen', FLEXPEN: 'FlexPen', FLEXTOUCH: 'FlexTouch', SOLOSTAR: 'SoloStar', PENFILL: 'PenFill', REDIHALER: 'RediHaler'};
    return String(value ?? '').trim().replace(/\s+/g, ' ')
      .replace(/\b[A-Z][A-Z0-9]*\b/g, (word) => unitCase[word] || (keepUpper.has(word) ? word : word[0] + word.slice(1).toLowerCase()))
      .replace(/\b(\d+(?:\.\d+)?)(MG|MCG|ML|MEQ|GM)\b/g, (_, amount, unit) => amount + ' ' + unitCase[unit]);
  }

  // Group only when the generic, formulation, route, release and strength text
  // match exactly. All source records and individual restrictions stay separate.
  function medicationIdentity(record) {
    const name = (record.name || '').trim();
    const genericFor = name.match(/^(.*?)\s*\(generic for ([^)]+)\)\s*$/i);
    const brandFor = name.match(/^(.*?)\s*\(brand for ([^)]+)\)\s*$/i);
    const generic = genericFor ? genericFor[1].trim() : brandFor ? brandFor[2].trim() : name;
    const brand = genericFor ? genericFor[2].trim() : brandFor ? brandFor[1].trim() : record.brand;
    const brands = brand && normalize(brand) !== 'various' && normalize(brand) !== normalize(generic) ? [brand.trim()] : [];
    // A source may omit insulin concentration from the generic description but
    // identify it in the trade name (e.g., U-100 vs U-500). Those are distinct
    // clinical products and must never share a single medication card.
    const concentration = [generic, ...brands].join(' ').match(/\bU[- ]?(100|500)\b/i);
    const variant = concentration ? `:u${concentration[1]}` : '';
    // Device-specific supplies remain distinct despite a shared generic class.
    const device = /\bblood glucose (?:test|monitor system)\b|\binsulin syringe\b|\bpen needles?\b|\blancets?\b/i.test(generic);
    const deviceBrand = device && brands.length ? ':device:' + normalize(brands[0]) : '';
    return {key: `${record.planId}:${normalize(generic)}${variant}${deviceBrand}`, generic, brands};
  }

  // Exact duplicate bracketed brand names are presentation artifacts.
  // Preserve the underlying payer product name, source links and PA records.
  function medicationDisplayLabel(name, brands) {
    let displayName = name;
    // Remove only exact repeated brand suffixes, whether [Brand] or (Brand).
    // Leave other bracketed text such as [OTC] or (USP) untouched.
    for (let i = 0; i < 3; i++) {
      const suffix = displayName.match(/^(.*?)\s+\[([^\[\]]+)\]\s*$/)
        || displayName.match(/^(.*?)\s+\(([^()]+)\)\s*$/);
      if (!suffix || !brands.some(brand => normalize(brand) === normalize(suffix[2]))) break;
      displayName = suffix[1].trim();
    }
    return readableMedicationName(displayName) + (brands.length
      ? ` (${brands.map(readableMedicationName).join(' / ')})` : '');
  }

  function medicationGroups(records) {
    const groups = new Map();
    for (const record of records) {
      const identity = medicationIdentity(record);
      if (!groups.has(identity.key)) groups.set(identity.key, {key: identity.key, name: identity.generic, brands: [], records: []});
      const group = groups.get(identity.key);
      group.records.push(record);
      for (const brand of identity.brands) if (!group.brands.some(b => normalize(b) === normalize(brand))) group.brands.push(brand);
    }
    return [...groups.values()].map(group => ({...group,
      label: medicationDisplayLabel(group.name, group.brands),
      search: [group.name, ...group.brands, ...group.records.flatMap(r => [r.name, ...(r.searchAliases || [])])].join(' ')
    }));
  }

  function medicationRoute(name) {
    const text = normalize(name);
    if (/\b(intravenous|\biv\b)\b/.test(text)) return 'iv';
    if (/\bintramuscular\b|\bim\b/.test(text)) return 'im';
    if (/subcut|sub-q|\bsc\b|inject|auto.inj|pref.?syr|\bpen.inj\b|\bvial\b/.test(text)) return 'injection';
    if (/nasal|nostril/.test(text)) return 'nasal';
    if (/inhal|nebuliz/.test(text)) return 'inhalation';
    if (/transdermal|patch/.test(text)) return 'patch';
    if (/topical|cream|ointment|\bgel\b/.test(text)) return 'topical';
    if (/tablet|capsule|oral|mouthwash|troche|syrup|elixir/.test(text)) return 'oral';
    return '';
  }

  function medicationForm(name) {
    const n = normalize(name);
    if (/auto.?inj/.test(n)) return 'auto-injector';
    if (/pref.?syr/.test(n)) return 'syringe';
    if (/\bvial\b/.test(n)) return 'vial';
    if (/\bpen.inj|\bpen injection/.test(n)) return 'pen';
    if (/mouthwash/.test(n)) return 'mouthwash';
    if (/troche|lozenge/.test(n)) return 'troche';
    if (/disintegrat|\bodt\b/.test(n)) return 'odt';
    if (/tablet|\btab\b/.test(n)) return 'tablet';
    if (/capsule|\bcap\b/.test(n)) return 'capsule';
    if (/suspension|solution|liquid|syrup|elixir/.test(n)) return 'liquid';
    return '';
  }

  function releaseKind(name) {
    return /\b(er|xr|sr|cr|dr|xl|extended|delayed|controlled|24.hour|12.hour)\b/i.test(name) ? 'modified' : 'ordinary';
  }

  function strengthTokens(name) {
    return [...normalize(name).matchAll(/\b\d+(?:\.\d+)?\s*(?:mcg|mg|meq|g|units)\b/g)]
      .map(match => match[0].replace(/\s+/g, '')).sort();
  }

  function explicitInsulinConcentration(group) {
    const names = [group.name, ...group.brands];
    const values = new Set(names.flatMap(name => [...String(name).matchAll(/\bU[- ]?(100|500)\b/gi)].map(match => match[1])));
    return values.size === 1 ? [...values][0] : values.size ? 'mixed' : '';
  }

  // The same labeled Natroba topical suspension has two official naming
  // conventions: the statewide drug list calls it "spinosad suspension",
  // while RxNorm calls the 9 mg/mL presentation "medicated shampoo".
  // DailyMed maps both descriptions to brand Natroba (RxCUI 1085820).
  // Only join these exact names WITH explicit Natroba identity. Do not infer
  // equivalence for other strengths, routes, brands or spinosad products.
  function verifiedNatrobaSpinosadAlias(group) {
    const name = normalize(group.name);
    const hasBrand = group.brands.some(brand => normalize(brand) === 'natroba')
      || /\s*(?:\(|\[)natroba(?:\)|\])\s*$/i.test(name);
    if (!hasBrand) return false;
    const generic = name.replace(/\s*(?:\(|\[)natroba(?:\)|\])\s*$/i, '').trim();
    return new Set([
      'spinosad suspension',
      'spinosad 9 mg/ml medicated shampoo',
      'spinosad 0.9% topical suspension',
      'spinosad 0.9 % topical suspension'
    ]).has(generic);
  }

  function sameProductGroup(planGroup, sharedGroup) {
    if (verifiedNatrobaSpinosadAlias(planGroup) && verifiedNatrobaSpinosadAlias(sharedGroup)) return true;
    const concentrationA = explicitInsulinConcentration(planGroup);
    const concentrationB = explicitInsulinConcentration(sharedGroup);
    if (concentrationA !== concentrationB || concentrationA === 'mixed') return false;
    const sameName = normalize(planGroup.name) === normalize(sharedGroup.name);
    const sharedBrand = planGroup.brands.some(brand => sharedGroup.brands.some(b => normalize(b) === normalize(brand)));
    // Verified plan notices may identify a trade name with a route suffix,
    // without populating the separate brand field (e.g. MOUNJARO (SUBCUTANEOUS)).
    const routeSuffix = planGroup.name.match(/^(.*?)\s*\((subcutaneous|oral|topical|nasal|inhalation|intravenous|intramuscular)\)\s*$/i);
    const routeBrand = routeSuffix && sharedGroup.brands.some(b => normalize(b) === normalize(routeSuffix[1]));
    if (!sameName && !sharedBrand && !routeBrand) return false;
    const a = medicationRoute(planGroup.name), b = medicationRoute(sharedGroup.name);
    if (!a || !b || a !== b) return sameName && a === b;
    const formA = medicationForm(planGroup.name), formB = medicationForm(sharedGroup.name);
    // A broad source description may omit the device, but explicit conflicting
    // forms and release mechanisms must never be merged.
    if (formA && formB && formA !== formB) {
      const injectionPackage = new Set(['auto-injector', 'syringe', 'vial', 'pen']);
      if (!(a === 'injection' && (!injectionPackage.has(formA) || !injectionPackage.has(formB)))) return false;
    }
    if (releaseKind(planGroup.name) !== releaseKind(sharedGroup.name)) return false;
    const strengthA = strengthTokens(planGroup.name), strengthB = strengthTokens(sharedGroup.name);
    if (strengthA.length && strengthB.length && !strengthA.every(token => strengthB.includes(token))) return false;
    return true;
  }

  // Preserve unmatched products as the selected plan's supplement. Attach only
  // unambiguous equivalent products to the statewide entry; never blend rules.
  const groupCache = new Map();
  function planMedicationGroups() {
    const key = state.planId + ':' + state.data.medications.length;
    if (groupCache.has(key)) return groupCache.get(key);
    const planGroups = medicationGroups(state.data.medications.filter(r => r.planId === state.planId && r.recordType === 'formulary'));
    const sharedGroups = medicationGroups(inheritedStatewideRows())
      .map(group => ({...group, isStatewide: true, statewideRecord: group.records[0]}));
    const brandIndex = new Map(), nameIndex = new Map();
    for (const group of sharedGroups) {
      nameIndex.set(normalize(group.name), [...(nameIndex.get(normalize(group.name)) || []), group]);
      for (const brand of group.brands) {
        const key = normalize(brand);
        brandIndex.set(key, [...(brandIndex.get(key) || []), group]);
      }
    }
    const supplements = [];
    for (const group of planGroups) {
      const candidates = new Set(nameIndex.get(normalize(group.name)) || []);
      const routeSuffix = group.name.match(/^(.*?)\s*\((subcutaneous|oral|topical|nasal|inhalation|intravenous|intramuscular)\)\s*$/i);
      if (routeSuffix) for (const match of brandIndex.get(normalize(routeSuffix[1])) || []) candidates.add(match);
      for (const brand of group.brands) {
        for (const match of brandIndex.get(normalize(brand)) || []) candidates.add(match);
      }
      if (verifiedNatrobaSpinosadAlias(group)) {
        for (const shared of sharedGroups) {
          if (verifiedNatrobaSpinosadAlias(shared)) candidates.add(shared);
        }
      }
      const compatible = [...candidates].filter(shared => sameProductGroup(group, shared));
      // An exact name/formulation match outranks broader candidates sharing a
      // reference brand. Otherwise multiple brand variants create duplicate
      // cards even when the exact source product is already present.
      const exact = compatible.filter(shared => normalize(shared.name) === normalize(group.name));
      const matches = exact.length ? exact : compatible;
      if (matches.length === 1) {
        const shared = matches[0];
        shared.records.push(...group.records);
        shared.search += ' ' + group.search;
      } else supplements.push(group);
    }
    const result = [...sharedGroups, ...supplements];
    groupCache.set(key, result);
    return result;
  }

  function uniqueMedicationNames() {
    return [...new Set(planMedicationGroups().map(group => group.label))]
      .sort((a, b) => a.localeCompare(b));
  }

  function categoryOptions() {
    return [...new Set(recordsForPlan().map((record) => record.category).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b));
  }

  function subcategoryOptions() {
    const category = normalize(state.category);
    return [...new Set(recordsForPlan()
      .filter((record) => !category || normalize(record.category).includes(category))
      .map((record) => record.subcategory)
      .filter(Boolean))]
      .sort((a, b) => a.localeCompare(b));
  }

  function planGroup(plan) {
    const priority = ['az-complete-health', 'banner-ufc', 'uhc-community-az'].indexOf(plan.id);
    if (priority >= 0) return priority - 3;
    if (plan.marketGroup === 'ahcccs' || /ahcccs|medicaid/i.test(plan.market || '') || plan.id === 'ahcccs-statewide') return 0;
    if (plan.marketGroup === 'medicare' || /medicare/i.test(plan.market || '')) return 1;
    return 2;
  }

  function valuesForCombo(name) {
    if (name === 'plan') return [...state.data.plans]
      .sort((a, b) => planGroup(a) - planGroup(b) || a.name.localeCompare(b.name))
      .map((plan) => plan.name);
    if (name === 'medication') return uniqueMedicationNames();
    if (name === 'category') return categoryOptions();
    return subcategoryOptions();
  }

  function populateControls() {
    el.planInput.value = state.data.plans.find((p) => p.id === state.planId)?.name || '';
  }

  function updateSubcategoryOptions() {
    if (!el.subcategoryOptions.hidden) renderComboboxOptions('subcategory', comboState.subcategory.showAll);
  }

  function resolveExact(values, input) {
    const target = normalize(input);
    return values.find((value) => normalize(value) === target) || '';
  }

  function resolvePlan(input) {
    const target = normalize(input);
    return state.data.plans.find((plan) => normalize(plan.name) === target || normalize(plan.id) === target);
  }

  function closeCombobox(name) {
    const [inputId, optionsId] = comboIds[name];
    const input = el[inputId];
    const options = el[optionsId];
    const wrapper = input.closest('.combobox');
    options.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    wrapper.setAttribute('aria-expanded', 'false');
    comboState[name].activeIndex = -1;
  }

  function closeAllComboboxes(except = '') {
    Object.keys(comboIds).forEach((name) => {
      if (name !== except) closeCombobox(name);
    });
  }

  function rankedValues(values, query, name) {
    if (!query) return values;
    const medicationSearch = name === 'medication' ? new Map(planMedicationGroups().map(g => [g.label, normalize(g.search)])) : new Map();
    return values
      .filter((value) => normalize(value).includes(query) || medicationSearch.get(value)?.includes(query))
      .sort((a, b) => {
        const aStarts = normalize(a).startsWith(query) ? 0 : 1;
        const bStarts = normalize(b).startsWith(query) ? 0 : 1;
        const priority = name === 'plan' ? planGroup(resolvePlan(a) || {}) - planGroup(resolvePlan(b) || {}) : 0;
        return priority || aStarts - bStarts || a.localeCompare(b);
      });
  }

  function renderComboboxOptions(name, showAll = false) {
    const [inputId, optionsId] = comboIds[name];
    const input = el[inputId];
    const options = el[optionsId];
    const wrapper = input.closest('.combobox');
    // Medication lists can contain thousands of machine-formatted package descriptions.
    // Never browse them indiscriminately: suggest only matches to typed text.
    const query = name === 'medication' ? normalize(input.value) : (showAll ? '' : normalize(input.value));
    const values = name === 'medication' && !query ? [] : rankedValues(valuesForCombo(name), query, name);
    const visibleValues = showAll && name !== 'medication' ? values : values.slice(0, 30);

    options.innerHTML = visibleValues.length
      ? visibleValues.map((value, index) => `<button type="button" class="combobox-option" role="option" id="${name}-option-${index}" data-combo-value="${escapeHtml(value)}" aria-selected="false">${escapeHtml(value)}</button>`).join('')
      : name === 'medication' && !query
        ? '<div class="combobox-empty">Type a brand or generic name to search</div>'
        : '<div class="combobox-empty">No matching options</div>';
    options.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    wrapper.setAttribute('aria-expanded', 'true');
    comboState[name].activeIndex = -1;
    comboState[name].showAll = showAll;
    closeAllComboboxes(name);
  }

  function updateActiveOption(name, nextIndex) {
    const [inputId, optionsId] = comboIds[name];
    const options = [...el[optionsId].querySelectorAll('.combobox-option')];
    if (!options.length) return;
    const index = Math.max(0, Math.min(nextIndex, options.length - 1));
    options.forEach((option, optionIndex) => {
      const active = optionIndex === index;
      option.classList.toggle('active', active);
      option.setAttribute('aria-selected', String(active));
    });
    comboState[name].activeIndex = index;
    el[inputId].setAttribute('aria-activedescendant', options[index].id);
    options[index].scrollIntoView({ block: 'nearest' });
  }

  function applyComboValue(name, value) {
    const [inputId] = comboIds[name];
    el[inputId].value = value;
    if (name === 'plan') {
      const plan = resolvePlan(value);
      if (plan) state.planId = plan.id;
    } else if (name === 'medication') {
      state.term = value;
    } else if (name === 'category') {
      state.category = value;
      state.subcategory = '';
      el.subcategoryInput.value = '';
    } else {
      state.subcategory = value;
    }
    closeCombobox(name);
    resetLimitAndRender();
  }

  function setupCombobox(name) {
    const [inputId, optionsId] = comboIds[name];
    const input = el[inputId];
    const options = el[optionsId];
    const toggle = document.querySelector(`[data-combo-toggle="${name}"]`);

    input.addEventListener('input', () => {
      if (name === 'plan') {
        const plan = resolvePlan(input.value);
        if (plan) state.planId = plan.id;
      } else if (name === 'medication') {
        state.term = input.value;
      } else if (name === 'category') {
        state.category = input.value;
        state.subcategory = '';
        el.subcategoryInput.value = '';
      } else {
        state.subcategory = input.value;
      }
      renderComboboxOptions(name, false);
      updateSubcategoryOptions();
      resetLimitAndRender();
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (options.hidden) renderComboboxOptions(name, !normalize(input.value));
        const delta = event.key === 'ArrowDown' ? 1 : -1;
        const start = comboState[name].activeIndex < 0 && delta < 0
          ? options.querySelectorAll('.combobox-option').length
          : comboState[name].activeIndex;
        updateActiveOption(name, start + delta);
      } else if (event.key === 'Enter' && comboState[name].activeIndex >= 0) {
        event.preventDefault();
        const option = options.querySelectorAll('.combobox-option')[comboState[name].activeIndex];
        if (option) applyComboValue(name, option.dataset.comboValue);
      } else if (event.key === 'Escape') {
        closeCombobox(name);
      }
    });

    input.addEventListener('blur', () => {
      window.setTimeout(() => {
        if (name === 'plan' && !resolvePlan(input.value)) {
          input.value = state.data.plans.find((plan) => plan.id === state.planId)?.name || '';
        }
        if (!input.closest('.combobox').contains(document.activeElement)) closeCombobox(name);
      }, 120);
    });

    toggle.addEventListener('click', () => {
      const opening = options.hidden;
      if (opening) renderComboboxOptions(name, name !== 'medication');
      else closeCombobox(name);
      input.focus();
    });

    options.addEventListener('mousedown', (event) => event.preventDefault());
    options.addEventListener('click', (event) => {
      const option = event.target.closest('.combobox-option');
      if (option) applyComboValue(name, option.dataset.comboValue);
    });
  }

  function setupComboboxes() {
    Object.keys(comboIds).forEach(setupCombobox);
    document.addEventListener('pointerdown', (event) => {
      if (!event.target.closest('.combobox')) closeAllComboboxes();
    });
  }

  function matchesCoverage(record) {
    if (!state.coverage) return true;
    if (state.coverage === 'listed') return record.recordType === 'formulary' && record.coverage !== 'explicit_not_covered';
    if (state.coverage === 'preferred') return record.preferred === 'preferred';
    if (state.coverage === 'non_preferred') return record.preferred === 'non_preferred';
    if (state.coverage === 'pa_required') return record.pa === 'required';
    if (state.coverage === 'pa_conditional') return record.pa === 'conditional';
    return record.coverage === state.coverage;
  }

  function filteredRecords() {
    const category = normalize(state.category);
    const subcategory = normalize(state.subcategory);
    const selectedGroup = planMedicationGroups().find(g => normalize(g.label) === normalize(state.term));
    const terms = normalize(state.term).split(/\s+/).filter(Boolean);
    return recordsForPlan()
      .filter((record) => !category || normalize(record.category).includes(category))
      .filter((record) => !subcategory || normalize(record.subcategory).includes(subcategory))
      .filter(matchesCoverage)
      .filter((record) => {
        if (selectedGroup) return selectedGroup.records.some(r => r.id === record.id);
        const haystack = normalize([
          record.name, record.brand, record.searchAliases?.join(' ')
        ].join(' '));
        return terms.every((term) => haystack.includes(term));
      })
      .sort((a, b) => {
        if (a.recordType !== b.recordType) return a.recordType === 'formulary' ? -1 : 1;
        return String(a.name).localeCompare(String(b.name));
      });
  }

  function planStatus() {
    const plan = state.data.plans.find((p) => p.id === state.planId) || state.data.plans[0];
    const labels = {
      loaded: 'Loaded reference',
      full_formulary_with_held_rows: 'Full formulary processed · identity exceptions held',
      partial: 'Partial plan evidence only',
      partial_notice_import: 'Named products imported · partial update notice',
      commercial_guide_import: 'Formulary guide imported · match exact pharmacy plan',
      reference_guide_import: 'PDL reference imported · benefit coverage unverified',
      verified_published_source: 'Current published sources verified',
      baseline_plus_updates: 'JSON baseline + subsequent updates',
      mandated_minimum_incomplete: 'Verified mandated minimum · additional plan data needed',
      policy_sources_indexed: 'Plan policy sources indexed',
      selected_records_loaded: 'Selected exact-plan records loaded',
      historical_snapshot: 'Historical July 2026 records · current formulary pending',
      mixed_current_historical: 'Selected October 2026 rows checked · July rows under review',
      source_identified: 'Official sources identified',
      not_loaded: 'Plan data not loaded'
    };
    el.planStatus.className = `plan-status ${plan.status}`;
    const statewideDate = new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' })
      .format(new Date(`${state.data.meta.drugListEffective}T00:00:00Z`));
    const shared = state.data.statewideSourceInfo || {};
    el.planStatus.innerHTML = `<strong>${escapeHtml(plan.name)} · ${labels[plan.status]}</strong>
      <p>Primary statewide references: <a href="${escapeHtml(shared.drugListOfficialUrl || '')}" target="_blank" rel="noopener">AHCCCS Drug List · ${escapeHtml(shared.drugListEffective || '')}</a> and
      <a href="${escapeHtml(shared.paCriteriaOfficialUrl || '')}" target="_blank" rel="noopener">AHCCCS clinical PA criteria · ${escapeHtml(shared.paCriteriaEffective || '')}</a>.
      This plan's additional sources supplement those references.</p>
      <p>${escapeHtml(plan.detail)}</p>`;

    const evidence = state.data.planEvidence.filter((item) => item.planId === plan.id);
    el.planEvidence.hidden = evidence.length === 0;
    el.evidenceList.innerHTML = evidence.map((item) => `
      <article class="evidence-item">
        <p><strong>${escapeHtml(item.topic)}</strong></p>
        <p>${escapeHtml(item.evidence)}</p>
        <a class="source-link" href="${escapeHtml(sourceHref(item))}" target="_blank" rel="noopener">${item.sourceUrl?.startsWith('/sources/') ? 'Open archived source' : 'Open official source'}${item.sourcePage ? ` · page ${item.sourcePage}` : ''}${item.sourceEffective ? ` · effective ${escapeHtml(item.sourceEffective)}` : ''}</a>
      </article>`).join('');
  }

  function hasVerifiedMandatedCoverage(record) {
    return record.recordType === 'formulary' && record.coverage === 'listed'
      && record.validation === 'mandated_statewide_minimum_with_plan_adoption_evidence';
  }

  function statusChips(record) {
    const chips = [];
    if (record.descriptionCorrection) chips.push(['Clinician-corrected description', 'neutral']);
    if (record.planId === 'uhc-community-az' && record.sourceEffective === '2026-07-01') {
      chips.push(['Historical July 2026 · current status unverified', 'negative']);
    }
    if (record.suppressCoverageAndPaBadges) return `<span class="chip negative">${escapeHtml(record.sourceIssue || 'Source identity needs review')}</span>`;
    if (record.recordType === 'policy') chips.push([record.guide ? 'PA guide · clinical review pending' : 'Policy criteria', 'warning']);
    else if (record.recordType === 'policy_index') chips.push(['Policy source indexed', 'warning']);
    else if (record.coverage !== 'explicit_not_covered') {
      const listingLabel = record.isStatewideReference || record.planId === 'ahcccs-statewide' ? 'On statewide drug list'
        : record.planId === 'uhc-community-az' && record.sourceEffective === '2026-07-01' ? 'On archived formulary' : 'On formulary';
      const verifiedCoverage = hasVerifiedMandatedCoverage(record);
      chips.push([verifiedCoverage ? 'Covered' : (/exact.plan preference notice/i.test(record.listingLabel || '') ? 'On formulary' : record.listingLabel) || listingLabel, verifiedCoverage || !record.listingLabel ? 'positive' : 'neutral', 'Appears in this source. Listed restrictions still apply.']);
    }
    if (record.guide?.ambiguity) chips.push(['Source clarification needed', 'negative']);
    if (record.coverage === 'explicit_not_covered') chips.push(['Explicitly not covered', 'negative']);
    if (record.coverageCaveat) chips.push([record.coverageCaveat, 'warning']);
    if (record.preferred === 'preferred') chips.push(['Preferred', 'positive']);
    if (record.preferred === 'non_preferred') chips.push(['Nonpreferred', 'warning']);
    if (record.recordType === 'formulary' && record.coverage !== 'explicit_not_covered' && record.preferred === 'not_specified') chips.push(['Preference not specified', 'neutral']);
    if (/\bbrand\s*only\b/i.test(record.brandGenericNotes || record.notes || '')) chips.push(['Brand only', 'warning']);
    if (/\bauthorized\s+generic\s+only\b/i.test([record.brandGenericNotes, record.notes].join(' '))) chips.push(['Authorized generic only', 'warning']);
    if (record.tier) chips.push([`Tier ${record.tier}`, 'neutral']);
    if (record.pa === 'required') chips.push(['PA required', 'warning']);
    else if (record.pa === 'conditional') chips.push(['Conditional PA', 'warning']);
    if (record.step === 'specified') chips.push(['Step therapy', 'warning']);
    if (record.quantityLimited || record.qlAmount || record.qlDays) chips.push(['Quantity limit', 'warning']);
    if (record.ageLimited) chips.push(['Age limit', 'warning']);
    if (record.specialty) chips.push(['Specialty', 'warning']);
    if (record.diagnosisRequired) chips.push(['Diagnosis required', 'warning']);
    return chips.filter(([text]) => !/conflicting source listings\s*=\s*conservative status|PA not addressed by notice|exact.plan preference notice/i.test(text)).map(([text, kind, help]) => `<span class="chip ${kind}"${help ? ` title="${escapeHtml(help)}"` : ''}>${escapeHtml(text)}</span>`).join('');
  }

  function resolvedPolicyGuide(record) {
    if (!record.sharedPolicyRef) return record;
    const ref = record.sharedPolicyRef;
    const policy = state.data.sharedPolicies?.find(p => p.id === ref.policyId && p.planId === record.planId && p.version === ref.version);
    const branch = policy?.branches[ref.branchId];
    if (!branch) return {...record, guide: null};
    return {...record, policyEffective: policy.effective, guide: {...branch,
      requirements: [...policy.guide.requirements, ...branch.requirements]}};
  }

  function medicationPolicyDropdown(record) {
    return (record.paPolicyAssignments || []).map(ref => {
      const raw = state.data.policies.find(p => p.id === ref.branchId && p.planId === record.planId);
      if (!raw) return '';
      const guide = resolvedPolicyGuide(raw);
      if (!guide.guide) return '';
      return `<details class="approval-guide"><summary>PA criteria · ${escapeHtml(guide.indication)}</summary>${approvalGuideContent(guide)}</details>`;
    }).join('');
  }

  function approvalGuideContent(record) {
    record = resolvedPolicyGuide(record);
    const guide = record.guide;
    if (!guide) return '';
    const list = (items) => `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
    return `<div class="approval-guide-content">
      <p><strong>${escapeHtml(record.indication)}</strong> · ${escapeHtml(record.approvalDuration)} · policy effective ${escapeHtml(record.policyEffective || record.sourceEffective)} · source snapshot ${escapeHtml(record.sourceEffective)}</p>
      <p>${escapeHtml(guide.scope)}</p>
      ${guide.ambiguity ? `<p class="guide-ambiguity"><strong>Source clarification needed:</strong> ${escapeHtml(guide.ambiguity)}</p>` : ''}
      <p><strong>${escapeHtml(record.stage)}</strong></p>
      ${guide.requirements.length ? '<p><strong>All requirements:</strong></p>' + list(guide.requirements) : ''}
      ${guide.branches.map((branch) => `<p><strong>${escapeHtml(branch.label)}:</strong></p>${list(branch.options)}`).join('')}
      <p><strong>Renewal:</strong></p>
      ${guide.renewal ? list(guide.renewal) : '<p>Separate renewal criteria are not stated in this section. No automatic renewal rule is inferred.</p>'}
      ${guide.notes.length ? '<p><strong>Product-specific notes:</strong></p>' + list(guide.notes) : ''}
      <p><a class="source-link" href="${escapeHtml(record.sourceUrl)}#page=${Number(record.sourcePage)}" target="_blank" rel="noopener">${escapeHtml(record.policyCode)} · PDF pages ${Number(record.sourcePage)}–${Number(record.sourceLastPage)}</a> · <a href="${escapeHtml(record.sourceTextUrl)}" target="_blank" rel="noopener">Full source text</a></p>
      <p class="guide-review-status">Source-reviewed summary; clinician approval pending.</p>
    </div>`;
  }

  function recordDetails(record) {
    const details = [];
    if (record.baselineSource) details.push(`<p><strong>Baseline source:</strong> JSON row ${Number(record.sourceRow)} · RxNorm ${escapeHtml(record.rxnormId)} · declared plan year ${escapeHtml(record.baselineSource.declaredPlanYears.join(', '))}</p>`);
    if (record.sourceUpdates?.length) details.push('<p><strong>Later source updates (applied in date order):</strong></p>' + record.sourceUpdates.map((item) => `<p><a href="${escapeHtml(sourceHref(item))}" target="_blank" rel="noopener">${escapeHtml(item.name)} · ${escapeHtml(item.sourceEffective)}</a>${item.paText ? ' · ' + escapeHtml(item.paText) : ''}</p>`).join(''));
    if (record.quantityLimited && !record.qlAmount && !record.qlDays) details.push('<p><strong>Quantity limit:</strong> Required by the JSON source; amount and interval are not supplied.</p>');
    if (hasVerifiedMandatedCoverage(record)) details.push('<p><strong>Coverage source:</strong> AHCCCS-mandated minimum</p>');
    if (record.policyEffective) details.push(`<p><strong>Policy effective:</strong> ${escapeHtml(record.policyEffective)} · source document snapshot ${escapeHtml(record.sourceEffective)}</p>`);
    if (record.individualEffectiveMissing) details.push('<p><strong>Policy effective date:</strong> not stated in this source section. The document snapshot date is shown separately.</p>');
    if (record.statewideReference) {
      const ref = record.statewideReference;
      const limits = [ref.stepText, ref.qlAmount && `Quantity ${ref.qlAmount}`, ref.qlDays && `per ${ref.qlDays} days`].filter(Boolean).join(' · ');
      if (limits) details.push(`<p><strong>Separate statewide reference limits:</strong> ${escapeHtml(limits)}. Exact-plan adoption of these limits is not verified. <a href="${escapeHtml(ref.sourceUrl)}#page=${Number(ref.sourcePage)}" target="_blank" rel="noopener">Statewide source</a></p>`);
    }
    if (record.recordType === 'policy') {
      details.push(record.guide ? '<p><strong>PA approval guide:</strong> requirements for the named product and indication; coverage and PA status remain separate.</p>' : '<p><strong>Policy-only record:</strong> a current drug-list row was not linked here. This does not establish coverage or noncoverage.</p>');
      if (record.guide) details.push(approvalGuideContent(record));
      if (record.indication && !record.guide) details.push(`<p><strong>Indication:</strong> ${escapeHtml(record.indication)}</p>`);
      if (record.paText) details.push(`<p><strong>Criteria:</strong> ${escapeHtml(record.paText)}</p>`);
      if (record.approvalDuration && !record.guide) details.push(`<p><strong>Duration:</strong> ${escapeHtml(record.approvalDuration)}</p>`);
    } else if (record.recordType === 'policy_index') {
      details.push('<p><strong>Policy index only:</strong> this confirms an exact-plan source section exists. It does not establish coverage, approval, or denial criteria.</p>');
    } else {
      if (record.planId === 'uhc-community-az' && record.sourceEffective === '2026-07-01') {
        details.push('<p><strong>Superseded source:</strong> UHC now publishes an October 1, 2026 PDL. This July entry is retained for historical comparison; its coverage and restrictions have not been checked against the October edition.</p>');
      }
      if (record.sourceConflict) details.push(`<p><strong>Source conflict:</strong> ${escapeHtml(record.sourceConflict)}</p>`);
      if (record.sourceRows?.length) {
        const rowLinks = record.sourceRows.map((item) => {
          const parts = [`Page ${Number(item.page)}`];
          if (item.table !== undefined) parts.push(`table ${item.table}`);
          if (item.row !== undefined) parts.push(`row ${item.row}`);
          for (const key of ['preference', 'pa', 'step', 'quantity']) if (item[key]) parts.push(item[key]);
          if (Array.isArray(item.cells)) parts.push(item.cells.filter(Boolean).join(' | '));
          return `<a class="source-link" href="${escapeHtml(record.sourceUrl)}#page=${Number(item.page)}" target="_blank" rel="noopener">${escapeHtml(parts.join(' · '))}</a>`;
        }).join(' · ');
        details.push(`<p><strong>${record.sourceConflict ? 'Every differing listing' : 'Printed source row'}:</strong> ${rowLinks}</p>`);
      } else if (record.sourcePages?.length > 1) {
        details.push(`<p><strong>Repeated source pages:</strong> ${record.sourcePages.map((page) =>
          `<a class="source-link" href="${escapeHtml(record.sourceUrl)}#page=${Number(page)}" target="_blank" rel="noopener">${Number(page)}</a>`
        ).join(' · ')}</p>`);
      }
      if (record.conflictSources?.length) {
        details.push(`<p><strong>Both printed listings:</strong> ${record.conflictSources.map((item) =>
          `<a class="source-link" href="${escapeHtml(record.sourceUrl)}#page=${Number(item.page)}" target="_blank" rel="noopener">${escapeHtml(item.column === 'non_preferred' ? 'Nonpreferred' : 'Preferred')} · page ${Number(item.page)} · ${escapeHtml(item.codes)}</a>`
        ).join(' · ')}</p>`);
      }
      if (record.paText && ['required', 'conditional'].includes(record.pa)) details.push(`<p><strong>PA:</strong> ${escapeHtml(record.paText)}</p>`);
      if (record.paExceptionText) details.push(`<p><strong>PA exception stated by source:</strong> ${escapeHtml(record.paExceptionText)}</p>`);
      if (record.ageRestrictionText) details.push(`<p><strong>Age restriction:</strong> ${escapeHtml(record.ageRestrictionText)}</p>`);
      if (record.coverageText) details.push(`<p><strong>Coverage restriction:</strong> ${escapeHtml(record.coverageText)}</p>`);
      if (record.stepText) details.push(`<p><strong>Step:</strong> ${escapeHtml(record.stepText)}</p>`);
      if (record.qlAmount || record.qlDays) {
        const interval = record.qlDays && `per ${record.qlDays}${/^\d+(?:\.\d+)?$/.test(String(record.qlDays)) ? ' days' : ''}`;
        details.push(`<p><strong>Quantity limit:</strong> ${escapeHtml([record.qlAmount, interval].filter(Boolean).join(' '))}</p>`);
      }
      if (record.notes) details.push(`<p><strong>Notes:</strong> ${escapeHtml(record.notes)}</p>`);
      if (record.rawRestrictions) details.push(`<p><strong>Source restrictions:</strong> ${escapeHtml(record.rawRestrictions)}</p>`);
      if (record.policySource) {
        const policy = record.policySource;
        details.push(`<p><strong>Exact-plan PA policy source:</strong> <a class="source-link" href="${escapeHtml(policy.url)}#page=${policy.firstPage}" target="_blank" rel="noopener">${escapeHtml(policy.title)} · ${escapeHtml(policy.policyCode)} · PDF pages ${policy.firstPage}–${policy.lastPage} · effective ${escapeHtml(policy.effective)}</a><br>Detailed criteria are indexed for review, not yet structured or clinician-approved here.</p>`);
      }
    }
    if (record.approvalGuideIds?.length && !record.paPolicyAssignments?.length) {
      for (const id of record.approvalGuideIds) {
        const guide = state.data.policies.find((item) => item.id === id && item.planId === record.planId && item.guide);
        if (guide) details.push(`<details class="approval-guide"><summary>PA approval guide: ${escapeHtml(guide.name)}</summary>${approvalGuideContent(guide)}</details>`);
      }
    }
    if (record.policySources?.length) {
      details.push('<p><strong>Related PA and internal policy sources:</strong></p>' + record.policySources.map((policy) =>
        `<p><a class="source-link" href="${escapeHtml(policy.url)}#page=${Number(policy.firstPage)}" target="_blank" rel="noopener">${escapeHtml(policy.title)} · pages ${Number(policy.firstPage)}–${Number(policy.lastPage)} ${policy.effective ? `· effective ${escapeHtml(policy.effective)}` : ''}</a> · <a href="${escapeHtml(policy.textUrl)}" target="_blank" rel="noopener">Read full source text</a></p>`
      ).join('') + '<p>Check the full indication, initial/renewal criteria and exceptions. Related-source links do not establish eligibility or approval.</p>');
    }
    if (record.sourceTextUrl && !record.guide) details.push(`<p><a class="source-link" href="${escapeHtml(record.sourceTextUrl)}" target="_blank" rel="noopener">Read full source text · PDF pages ${Number(record.sourcePage)}–${Number(record.sourceLastPage)}</a></p>`);
    const sourceLabel = [record.sourceTitle, record.sourceEffective && `effective ${record.sourceEffective}`, record.sourcePage && `page ${record.sourcePage}`].filter(Boolean).join(' · ');
    if (!record.guide) details.push(`<a class="source-link" href="${escapeHtml(sourceHref(record))}" target="_blank" rel="noopener">${escapeHtml(sourceLabel || 'Open source')}</a>`);
    return details.join('');
  }

  function recordCard(record) {
    record = resolvedPolicyGuide(record);
    const classes = ['result-card'];
    if (record.recordType === 'policy' || record.recordType === 'policy_index') classes.push('policy');
    if (record.coverage === 'explicit_not_covered') classes.push('not-covered');
    return `<article class="${classes.join(' ')}">
      <div>
        <h3>${escapeHtml(record.name || record.subcategory)}</h3>
        ${record.brand ? `<p class="brand">Brand: ${escapeHtml(record.brand)}</p>` : ''}
      </div>
      <div class="chips" aria-label="Coverage attributes">${statusChips(record)}</div>
      ${medicationPolicyDropdown(record)}
      <details class="record-detail result-disclosure">
        <summary>${record.guide || record.approvalGuideIds?.length ? 'PA guide, details and sources' : 'Details, restrictions and sources'}</summary>
        <div class="result-disclosure-body">
          <p class="classification"><strong>${escapeHtml(record.category)}</strong><br>${escapeHtml(titleCase(record.subcategory))}</p>
          ${recordDetails(record)}
        </div>
      </details>
    </article>`;
  }

  // Link only clearly named AHCCCS criteria sections. An indexed guideline
  // may cover particular indications; the link does not promise approval.
  // Clinical requirements are displayed only for a verified product-specific
  // guideline. Exact brand matching prevents accidental class-level transfers.
  // The index is a searchable table of contents, not an approval algorithm.
  // Each result links to the complete, source-extracted verbatim section.
  function searchIndexedCriteria(query, sections) {
    const terms = normalize(query).split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    return sections.filter(section => {
      const haystack = normalize([section.name, section.notes, section.policyCode].join(' '));
      return terms.every(term => haystack.includes(term));
    }).sort((a, b) => {
      const titleA = normalize(a.name), titleB = normalize(b.name);
      const q = normalize(query).trim();
      const scoreA = titleA === q ? 0 : titleA.startsWith(q) ? 1 : titleA.includes(q) ? 2 : 3;
      const scoreB = titleB === q ? 0 : titleB.startsWith(q) ? 1 : titleB.includes(q) ? 2 : 3;
      return scoreA - scoreB || a.name.localeCompare(b.name);
    });
  }

  function renderCriteriaLibrary() {
    const policies = criteriaSources();
    const query = el.criteriaSearch.value;
    const matches = searchIndexedCriteria(query, policies);
    const guides = clinicalPolicyOnlyGroups(query, []);
    const count = matches.length;
    el.criteriaCount.textContent = !normalize(query)
      ? `${policies.length} indexed guideline sections · Type a medication or policy name`
      : `${guides.length} structured clinical guide${guides.length === 1 ? '' : 's'} · ${count} matching source section${count === 1 ? '' : 's'}${count > 25 ? ' · Showing first 25 source sections' : ''}`;
    el.criteriaResults.innerHTML = guides.map(group => `<article class="criteria-source">
        <h3>${escapeHtml(group.label)} · ${escapeHtml(group.guide.policyCode)}</h3>
        <details class="result-disclosure"><summary>${escapeHtml(group.guide.heading)}</summary>
          <div class="result-disclosure-body">${clinicalGuidanceContent(group.guide)}</div>
        </details>
      </article>`).join('') + matches.slice(0, 25).map(policy => `
      <article class="criteria-source">
        <h3>${escapeHtml(policy.name)}</h3>
        <p>${escapeHtml(policy.planId === 'ahcccs-ffs-aihp' ? 'AHCCCS statewide source' : state.data.plans.find(p => p.id === policy.planId)?.name || policy.sourceTitle)}
          · ${escapeHtml(policy.policyCode || '')} · source effective ${escapeHtml(policy.sourceEffective)}
          · PDF pages ${Number(policy.sourcePage)}–${Number(policy.sourceLastPage)}</p>
        ${policy.notes ? `<p>${escapeHtml(policy.notes)}</p>` : ''}
        ${policy.guide ? `<details class="approval-guide"><summary>PA criteria · ${escapeHtml(policy.indication || policy.name)}</summary>${approvalGuideContent(policy)}</details>` : ''}
        <p><a class="source-link" href="${escapeHtml(sourceHref(policy))}" target="_blank" rel="noopener">Open original guideline PDF at this section</a></p>
        ${policy.sourceTextUrl ? `<button type="button" class="text-button criteria-load" data-read-guideline="${escapeHtml(policy.id)}">Read full guideline text</button>` : ''}
        <pre class="guideline-verbatim" hidden></pre>
      </article>
    `).join('') || (normalize(query) ? '<p>No matching indexed sections. This does not prove a drug has no authorization requirements.</p>' : '');
  }

  function criteriaSources() {
    return [...(state.data.statewidePaCriteria || []),
      ...(state.data.policies || []).filter(policy => policy.planId === state.planId)];
  }

  // Slice, never summarize: reconstructing these parts yields the exact source.
  // Product headings label source branches; they do not assert applicability.
  function policySourceBranches(text) {
    const markers = [...text.matchAll(/^[\t ]*Product\s*Name\s*:[\t ]*([^\r\n]*)/gmi)];
    if (!markers.length) return {intro: text, branches: []};
    return {intro: text.slice(0, markers[0].index), branches: markers.map((marker, i) => {
      const content = text.slice(marker.index, markers[i + 1]?.index ?? text.length);
      const headerEnd = content.search(/^\s*(?:Approval\s+Length|Guideline\s+Type|Therapy\s+Stage|Approval\s+Criteria)\b/im);
      const product = (headerEnd >= 0 ? content.slice(0, headerEnd) : marker[0])
        .replace(/^[\t ]*Product\s*Name\s*:[\t ]*/i, '')
        .split(/\r?\n/).filter(line => !/^\s*(?:--- PDF page \d+ ---|=== PDF PAGE \d+ ===|Page \d+)\s*$/i.test(line))
        .join(' ').replace(/\s+/g, ' ').trim();
      const stage = content.match(/Therapy\s+Stage[\t ]*[\r\n]+\s*(Initial Authorization|Reauthorization)/i)?.[1] || '';
      const duration = content.match(/Approval\s+Length[\t ]*[\r\n]+\s*(\d+\s+(?:month|week|day)\(s\))/i)?.[1] || '';
      return {product: product || 'Product branch (see source text)', stage, duration, text: content};
    })};
  }

  function policySourceBranchMarkup(text) {
    const parsed = policySourceBranches(text);
    if (!parsed.branches.length) return '';
    return '<p>Original source branches — select the applicable product and treatment stage. All source wording and logical connectors are preserved; these are not clinician-approved summaries.</p>'
      + parsed.branches.map((branch, index) => `<details class="source-branch result-disclosure">
          <summary>${escapeHtml(branch.product)}${branch.stage ? ' · ' + escapeHtml(branch.stage) : ''}${branch.duration ? ' · ' + escapeHtml(branch.duration) : ''}</summary>
          <pre class="guideline-verbatim">${escapeHtml(branch.text)}</pre>
        </details>`).join('')
      + `<details class="result-disclosure"><summary>Complete unformatted source, including document notes</summary><pre class="guideline-verbatim">${escapeHtml(text)}</pre></details>`;
  }

  function bindCriteriaLibrary() {
    el.criteriaSearch.addEventListener('input', renderCriteriaLibrary);
    document.addEventListener('click', event => {
      const shortcut = event.target.closest('[data-criteria-query]');
      if (!shortcut) return;
      el.criteriaLibrary.open = true;
      el.criteriaSearch.value = shortcut.dataset.criteriaQuery;
      renderCriteriaLibrary();
      el.criteriaLibrary.scrollIntoView({behavior:'smooth',block:'start'});
      el.criteriaSearch.focus();
    });

    document.addEventListener('click', async event => {
      const button = event.target.closest('[data-read-guideline]');
      if (!button) return;
      const policy = criteriaSources().find(p => p.id === button.dataset.readGuideline)
        || inlinePolicySources.get(button.dataset.readGuideline);
      if (policy?.planId && policy.planId !== 'ahcccs-ffs-aihp' && policy.planId !== state.planId) return;
      if (!policy || !policy.sourceTextUrl) return;
      const pre = button.closest('.criteria-source').querySelector('.guideline-verbatim');
      let branchView = button.closest('.criteria-source').querySelector('.source-branch-view');
      if (button.dataset.loaded === 'true') {
        const view = branchView || pre;
        view.hidden = !view.hidden;
        button.textContent = view.hidden ? 'Read full guideline text' : 'Hide full guideline text';
        return;
      }
      button.disabled = true;
      button.textContent = 'Loading original text…';
      try {
        const response = await fetch(policy.sourceTextUrl);
        if (!response.ok) throw new Error('Source text unavailable');
        pre.textContent = await response.text();
        const markup = policySourceBranchMarkup(pre.textContent);
        if (markup) {
          branchView = document.createElement('div');
          branchView.className = 'source-branch-view';
          branchView.innerHTML = markup;
          pre.after(branchView);
          pre.hidden = true;
        } else pre.hidden = false;
        button.dataset.loaded = 'true';
        button.textContent = 'Hide full guideline text';
      } catch (error) {
        pre.textContent = 'Could not load the source section. Open the PDF link above instead.';
        pre.hidden = false;
        button.textContent = 'Retry reading original text';
      } finally {
        button.disabled = false;
      }
    });
    renderCriteriaLibrary();
  }

  function clinicalGuidanceFor(group) {
    const brands = new Set(group.brands.map(normalize));
    const generic = normalize(group.name);
    return (state.data.statewideClinicalGuidance || []).find(guide => {
      // Strength-specific policies must not attach to a brand/generic group
      // representing another tablet strength, or to an unspecified strength.
      // A group with mixed/ambiguous record strengths fails closed.
      // A dosage-form-specific policy must never be applied to a different
      // route or formulation (e.g. tacrolimus ointment vs oral/injection).
      if (Array.isArray(guide.matchFormulationWords) && guide.matchFormulationWords.length) {
        const products = group.records?.length ? group.records.map(record => record.name) : [group.name];
        const allowed = new Set(guide.matchFormulationWords.map(normalize));
        if (!products.length || !products.every(name =>
          String(name || '').toLowerCase().match(/[a-z0-9]+/g)?.some(word => allowed.has(word))
        )) return false;
      }
      if (guide.matchStrengthMg != null) {
        const products = group.records?.length ? group.records.map(r => r.name) : [group.name];
        if (!products.length || !products.every(name => {
          const milligrams = [...String(name || '').matchAll(/\b(\d+(?:\.\d+)?)\s*mg\b/gi)]
            .map(match => Number(match[1]));
          return milligrams.length > 0 &&
            milligrams.every(value => value === guide.matchStrengthMg);
        })) return false;
      }
      const allowedBrands = new Set((guide.matchBrands || []).map(normalize));
      const matchedBrand = [...brands].some(brand => allowedBrands.has(brand));
      // Do not put product-specific clinical criteria on a group that also
      // contains a different branded product.
      if (matchedBrand) return [...brands].every(brand => allowedBrands.has(brand));
      // A generic-name-only guide must never be the fallback on a branded
      // medication group. The product-specific branded rule can differ.
      if (brands.size > 0) return false;
      return (guide.matchNames || []).some(name => generic === normalize(name));
    }) || null;
  }

  // A clinical guideline may name a drug absent from this plan's visible
  // formulary products. Keep its source accessible, but never infer coverage.
  function clinicalPolicyOnlyGroups(query, visibleGroups) {
    const terms = normalize(query).split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    const linked = new Set(visibleGroups.map(clinicalGuidanceFor)
      .filter(Boolean).map(guide => guide.id));
    return (state.data.statewideClinicalGuidance || [])
      .filter(guide => !linked.has(guide.id))
      .filter(guide => {
        const names = [...(guide.matchBrands || []), ...(guide.matchNames || []), guide.product || '', guide.policyCode || ''];
        return names.some(name => terms.every(term => normalize(name).includes(term)));
      })
      .map(guide => ({
        key: 'clinical-policy-only:' + guide.id,
        label: readableMedicationName((guide.matchBrands || [])[0] || (guide.matchNames || [])[0] || guide.product),
        name: guide.product, brands: guide.matchBrands || [],
        records: [], policyOnly: true, guide
      }));
  }

  function clinicalRequirementItem(requirement) {
    if (typeof requirement === 'string') return `<li>${escapeHtml(requirement)}</li>`;
    if (requirement && Array.isArray(requirement.any)) {
      return `<li><strong>ONE of the following:</strong><ul>${requirement.any.map(clinicalRequirementItem).join('')}</ul></li>`;
    }
    if (requirement && Array.isArray(requirement.all)) {
      return `<li><strong>ALL of the following:</strong><ul>${requirement.all.map(clinicalRequirementItem).join('')}</ul></li>`;
    }
    throw new Error('Unsupported clinical requirement structure');
  }

  function clinicalGuidanceContent(guide) {
    const pathways = (guide.pathways || []).map((pathway, index) => `
      <div class="criteria-pathway">
        <h4>Pathway ${index + 1}: ${escapeHtml(pathway.title)}</h4>
        ${pathway.approvalDuration ? `<p><strong>Approval duration for this pathway:</strong> ${escapeHtml(pathway.approvalDuration)}</p>` : ''}
        <p><strong>All of the following:</strong></p>
        <ul>${pathway.all.map(clinicalRequirementItem).join('')}</ul>
      </div>`).join('<p><strong>OR</strong></p>');
    const stages = (guide.stages || []).map(stage => `
      <section class="criteria-stage">
        <h4>${escapeHtml(stage.title)}</h4>
        ${stage.approvalDuration ? `<p><strong>Approval duration for this stage:</strong> ${escapeHtml(stage.approvalDuration)}</p>` : ''}
        <p><strong>ALL of the following:</strong></p>
        <ul>${stage.all.map(clinicalRequirementItem).join('')}</ul>
      </section>`).join('');
    return `
      <p>${escapeHtml(guide.summary)}</p>
      ${stages ? `<p><strong>Requirements by treatment stage:</strong></p>${stages}` : `<p><strong>Qualifying pathways — any ONE:</strong></p>${pathways}`}
      ${(guide.pathways || guide.stages || []).some(x => x.approvalDuration) ? '' : `<p><strong>Approval duration:</strong> ${escapeHtml(guide.approvalDuration)}</p>`}
      <p><strong>Suggested documentation to include:</strong></p>
      <ul>${guide.documentationSuggestions.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
      <p class="guide-review-status">Documentation suggestions are not a separate insurer-prescribed checklist.</p>
      <p>${escapeHtml(guide.guidelineCaution)}</p>
      <p class="guide-review-status">Source-reviewed summary; clinician approval pending. The guideline does not independently establish plan coverage or PA status.</p>
      <p><a class="source-link" href="${escapeHtml(sourceHref(guide))}" target="_blank" rel="noopener">Source: ${escapeHtml(guide.policyCode)} · PDF page ${Number(guide.sourcePage)}${guide.sourceLastPage !== guide.sourcePage ? '–' + Number(guide.sourceLastPage) : ''}</a> · <a href="${escapeHtml(guide.sourceTextUrl)}" target="_blank" rel="noopener">Full guideline text</a></p>`;
  }

  function criteriaLibraryShortcut(group) {
    const query = group.brands[0] || group.name;
    return `<button type="button" class="text-button criteria-shortcut" data-criteria-query="${escapeHtml(query)}">Find clinical criteria source for this medication</button>`;
  }

  const inlinePolicySources = new Map();
  const namedPolicyCache = new Map();
  function namedPlanPolicies(group, statewide = false) {
    const scope = statewide ? 'ahcccs-ffs-aihp' : state.planId;
    const identities = [...new Set([...group.brands, group.name].map(normalize).filter(name => name.length >= 4 && name !== 'various'))];
    const matches = new Map();
    for (const identity of identities) {
      const key = `${scope}:${identity}`;
      if (!namedPolicyCache.has(key)) {
        const policies = (statewide ? state.data.statewidePaCriteria || [] : state.data.policies || []).filter(policy => {
          if (policy.planId !== scope || policy.recordType !== 'policy_index' || !policy.sourceTextUrl) return false;
          if ((policy.searchAliases || []).some(alias => normalize(alias) === identity)) return true;
          // This field contains the extracted original Product Name headings,
          // not medications mentioned as prior trials in clinical prose.
          const fields = policy.notes?.match(/Named Product Name fields:\s*(.*?)\s*Policy product-field matches/s)?.[1];
          const named = (fields || '').split(/[,;]/).map(value => normalize(value)
            .replace(/^(?:(?:non[- ]?)?preferred(?: drugs?| agents?)?\s*:\s*)/i, '')
            .replace(/^(?:brand|generic)\s+/i, '').trim());
          return named.includes(identity);
        });
        namedPolicyCache.set(key, policies);
      }
      for (const policy of namedPolicyCache.get(key)) matches.set(policy.id, policy);
    }
    return [...matches.values()];
  }

  function linkedPolicyPanels(group) {
    const links = new Map();
    const add = policy => {
      const signature = [policy.planId, policy.sourceUrl?.split('#')[0], policy.sourcePage, policy.sourceLastPage].join(':');
      if (links.has(signature)) return;
      links.set(signature, policy);
      inlinePolicySources.set(policy.id, policy);
    };
    for (const record of group.records || []) {
      if (record.planId !== state.planId || record.isStatewideReference) continue;
      for (const link of [...(record.policySources || []), ...(record.policySource ? [record.policySource] : [])]) {
        if (!link.textUrl) continue;
        const id = `linked:${record.planId}:${link.textUrl}`;
        const policy = {
          id, planId: record.planId, name: link.title, policyCode: link.policyCode,
          sourceUrl: link.url, sourceTextUrl: link.textUrl,
          sourcePage: link.firstPage, sourceLastPage: link.lastPage,
          sourceEffective: link.effective
        };
        add(policy);
      }
    }
    // Navigation only: a named source is not an assertion that its criteria
    // apply to every formulation or that this medication requires PA.
    for (const policy of [...namedPlanPolicies(group), ...namedPlanPolicies(group, true)]) add(policy);
    const plan = state.data.plans.find(p => p.id === state.planId);
    return [...links.values()].map(policy => `<details class="record-detail result-disclosure">
      <summary>${policy.planId === 'ahcccs-ffs-aihp' ? 'AHCCCS reference policy' : 'Selected-plan policy'} · ${escapeHtml(policy.name)}</summary>
      <article class="criteria-source result-disclosure-body">
        <p><strong>${escapeHtml(policy.planId === 'ahcccs-ffs-aihp' ? 'AHCCCS statewide clinical reference' : plan?.name)}</strong>${policy.sourceEffective ? ' · source ' + escapeHtml(policy.sourceEffective) : ''}</p>
        <p>Review the named product, formulation, indication, initial and renewal branches, and exceptions. This related policy link does not independently establish coverage or PA status.</p>
        <p><a class="source-link" href="${escapeHtml(sourceHref(policy))}" target="_blank" rel="noopener">Original policy PDF · pages ${Number(policy.sourcePage)}–${Number(policy.sourceLastPage)}</a></p>
        <button type="button" class="text-button criteria-load" data-read-guideline="${escapeHtml(policy.id)}">Read full guideline text</button>
        <pre class="guideline-verbatim" hidden></pre>
      </article>
    </details>`).join('');
  }

  function medicationGroupCard(group) {
    if (group.policyOnly) return `<article class="result-card policy">
      <div>
        <h3>${escapeHtml(group.label)}</h3>
        <p class="brand"><strong>Clinical criteria only — coverage not established</strong></p>
        <p>The AHCCCS clinical criteria document names this medication. No matching drug-list or formulary product card is established in this selected view. Do not infer coverage, PA status, or eligibility.</p>
      </div>
      <details class="record-detail result-disclosure" open>
        <summary>${escapeHtml(group.guide.heading)}</summary>
        <div class="result-disclosure-body">${clinicalGuidanceContent(group.guide)}</div>
      </details>
    </article>`;
    const policyPanels = linkedPolicyPanels(group);
    if (group.isStatewide) {
      const statewide = group.statewideRecord;
      const planRows = group.records.filter(record => !record.isStatewideReference);
      const needsPa = statewide.pa === 'required' || statewide.pa === 'conditional';
      const hasStep = statewide.step === 'specified' || Boolean(statewide.stepText);
      const sourceInfo = state.data.statewideSourceInfo || {};
      const guidance = clinicalGuidanceFor(group);
      const hasClinicalDetails = needsPa || hasStep || guidance;
      const differs = planRows.some(record =>
        (record.preferred === 'preferred' && statewide.preferred !== 'preferred')
        || (record.pa === 'not_required' && needsPa));
      return `<article class="result-card">
        <div>
          <h3>${escapeHtml(group.label)}</h3>
          <p class="brand">AHCCCS statewide drug list · ${escapeHtml(sourceInfo.drugListEffective || statewide.sourceEffective)}</p>
        </div>
        <div class="chips" aria-label="Statewide coverage attributes">${statusChips(statewide)}</div>
        ${needsPa && statewide.paText ? `<p class="pa-condition"><strong>${statewide.pa === 'conditional' ? 'PA condition' : 'PA requirement'}:</strong> ${escapeHtml(statewide.paText)}</p>` : ''}
        ${statewide.paExceptionText ? `<p><strong>PA exception stated by source:</strong> ${escapeHtml(statewide.paExceptionText)}</p>` : ''}
        ${statewide.ageRestrictionText ? `<p><strong>Age restriction:</strong> ${escapeHtml(statewide.ageRestrictionText)}</p>` : ''}
        ${statewide.coverageText ? `<p><strong>Coverage restriction:</strong> ${escapeHtml(statewide.coverageText)}</p>` : ''}
        ${criteriaLibraryShortcut(group)}
        ${hasStep && statewide.stepText ? `<p><strong>Step therapy:</strong> ${escapeHtml(statewide.stepText)}</p>` : ''}
        ${policyPanels}
        ${hasClinicalDetails && (guidance || !policyPanels) ? `<details class="record-detail result-disclosure" ${guidance ? 'open' : ''}>
          <summary>${guidance ? escapeHtml(guidance.heading) : 'Clinical authorization source'}</summary>
          <div class="result-disclosure-body">
            ${guidance ? clinicalGuidanceContent(guidance) : `
              ${hasStep ? `<p><strong>Statewide step rule:</strong> ${escapeHtml(statewide.stepText || 'Step therapy specified')}</p>` : ''}
              ${needsPa && !statewide.paText ? `<p><strong>${statewide.pa === 'conditional' ? 'PA applies only under the source conditions; review the original drug-list row.' : 'PA is required by the statewide drug list.'}</strong></p>` : ''}
              <p>Review the full clinical guideline for the applicable indication, treatment trials, duration, exceptions and renewal requirements.</p>
              <p><a class="source-link" href="${escapeHtml(sourceInfo.paCriteriaOfficialUrl || '')}" target="_blank" rel="noopener">Search the AHCCCS statewide PA criteria document</a></p>
            `}
          </div>
        </details>` : ''}
        <details class="record-detail result-disclosure">
          <summary>Details and source records${planRows.length ? ` · ${planRows.length} plan supplement${planRows.length === 1 ? '' : 's'}` : ''}</summary>
          <div class="result-disclosure-body">
            <p><strong>AHCCCS statewide designation</strong></p>
            ${recordDetails(statewide)}
            ${differs ? '<p><strong>Source discrepancy:</strong> An additional plan record differs from the statewide preference or PA designation. The statewide status is shown above; compare the dated original sources.</p>' : ''}
            ${planRows.map(record => `<details class="result-disclosure"><summary>Plan source: ${escapeHtml(record.sourceTitle || record.name)}${record.sourceEffective ? ' · ' + escapeHtml(record.sourceEffective) : ''}</summary>
              <div class="result-disclosure-body">
                <p>${escapeHtml(record.name)}</p>
                ${recordDetails(record)}
              </div>
            </details>`).join('')}
          </div>
        </details>
      </article>`;
    }
    const onlyOne = group.records.length === 1;
    const planGuidance = clinicalGuidanceFor(group);
    return `<article class="result-card">
      <h3>${escapeHtml(group.label)}</h3>
      ${criteriaLibraryShortcut(group)}
      ${policyPanels}
      ${planGuidance ? `<details class="record-detail result-disclosure" open>
        <summary>AHCCCS clinical criteria · ${escapeHtml(planGuidance.policyCode)}</summary>
        <div class="result-disclosure-body">
          <p><strong>Clinical criteria only:</strong> this guideline does not independently establish plan coverage, PA requirement, or approval.</p>
          ${clinicalGuidanceContent(planGuidance)}
        </div>
      </details>` : ''}
      ${group.records.map(record => `<section class="medication-product-row">
        ${onlyOne ? '' : `<h4>${escapeHtml(readableMedicationName(record.name))}</h4>`}
        <div class="chips" aria-label="Coverage attributes">${statusChips(record)}</div>
        ${medicationPolicyDropdown(record)}
        <details class="record-detail result-disclosure"><summary>Details, restrictions and sources</summary>
          <div class="result-disclosure-body">${recordDetails(record)}</div>
        </details>
      </section>`).join('')}
    </article>`;
  }

  function render() {
    const selectedPlan = state.planId;
    if (state.data.planDataFiles?.[selectedPlan] && !loadedPlans.has(selectedPlan)) {
      planStatus();
      el.loadingState.hidden = false;
      el.loadingState.textContent = 'Loading the selected formulary…';
      el.resultCount.textContent = '…';
      el.resultGrid.innerHTML = '';
      el.emptyState.hidden = true;
      el.showMore.hidden = true;
      ensurePlanData(selectedPlan).then(() => {
        if (state.planId === selectedPlan) render();
      }).catch(() => {
        if (state.planId === selectedPlan) {
          el.loadingState.textContent = 'This formulary could not be loaded. Select the plan again to retry.';
        }
      });
      return [];
    }
    const matchingRecords = filteredRecords();
    const medicationRows = matchingRecords.filter(r => r.recordType === 'formulary');
    // Include the other confirmed products in a matching medication group,
    // while preserving explicit coverage/category filters.
    const allGroups = planMedicationGroups();
    const matchedIds = new Set(medicationRows.map(r => r.id));
    const groups = allGroups.filter(g => {
      if (!g.records.some(r => matchedIds.has(r.id))) return false;
      if (!g.isStatewide) return true;
      const r = g.statewideRecord;
      return matchesCoverage(r)
        && (!state.category || normalize(r.category).includes(normalize(state.category)))
        && (!state.subcategory || normalize(r.subcategory).includes(normalize(state.subcategory)));
    }).map(g => {
      if (g.isStatewide) return g;
      return {...g, records: g.records.filter(r =>
        matchesCoverage(r)
        && (!state.category || normalize(r.category).includes(normalize(state.category)))
        && (!state.subcategory || normalize(r.subcategory).includes(normalize(state.subcategory)))
      )};
    });
    const records = groups;
    // Keep matching clinical information accessible in its own panel. Policy,
    // administrative and source records never enter the medication results.
    el.criteriaSearch.value = state.term;
    renderCriteriaLibrary();
    if (!records.length && normalize(state.term) && el.criteriaResults.innerHTML.trimStart().startsWith('<article')) {
      el.criteriaLibrary.open = true;
    }
    planStatus();
    el.loadingState.hidden = true;
    el.resultCount.textContent = records.length.toLocaleString();
    const plan = state.data.plans.find((p) => p.id === state.planId);
    el.effectiveDate.textContent = plan?.effective || (state.planId === 'ahcccs-statewide'
      ? `Drug list effective ${state.data.meta.drugListEffective}` : '');
    el.emptyState.hidden = records.length !== 0;
    el.resultGrid.innerHTML = records.slice(0, state.limit).map(record => record.records ? medicationGroupCard(record) : recordCard(record)).join('');
    el.showMore.hidden = records.length <= state.limit;
    el.showMore.textContent = `Show ${Math.min(PAGE_SIZE, records.length - state.limit)} more`;
    document.querySelectorAll('[data-category]').forEach((button) => {
      button.setAttribute('aria-pressed', String(normalize(button.dataset.category) === normalize(state.category)));
    });
    return records;
  }

  function resetLimitAndRender() {
    state.limit = PAGE_SIZE;
    render();
  }

  function bindEvents() {
    setupComboboxes();
    el.coverageInput.addEventListener('change', () => { state.coverage = el.coverageInput.value; resetLimitAndRender(); });
    el.planStatus.addEventListener('click', (event) => {
      if (!event.target.closest('[data-open-state-reference]')) return;
      state.planId = 'ahcccs-statewide';
      el.planInput.value = state.data.plans.find((plan) => plan.id === state.planId).name;
      if (state.coverage === 'policy_index') {
        state.coverage = '';
        el.coverageInput.value = '';
      }
      closeAllComboboxes();
      resetLimitAndRender();
    });
    el.clearFilters.addEventListener('click', () => {
      Object.assign(state, { planId: 'az-complete-health', term: '', category: '', subcategory: '', coverage: '', limit: PAGE_SIZE });
      el.planInput.value = state.data.plans.find((plan) => plan.id === state.planId).name;
      el.medicationInput.value = '';
      el.categoryInput.value = '';
      el.subcategoryInput.value = '';
      el.coverageInput.value = '';
      updateSubcategoryOptions();
      closeAllComboboxes();
      render();
    });
    document.querySelectorAll('[data-category]').forEach((button) => {
      button.addEventListener('click', () => {
        const selected = button.dataset.category;
        state.category = normalize(state.category) === normalize(selected) ? '' : selected;
        state.subcategory = '';
        el.categoryInput.value = state.category;
        el.subcategoryInput.value = '';
        updateSubcategoryOptions();
        closeAllComboboxes();
        resetLimitAndRender();
      });
    });
    el.showMore.addEventListener('click', () => { state.limit += PAGE_SIZE; render(); });
  }

  function registerModelTools() {
    if (!document.modelContext?.registerTool) return;
    document.modelContext.registerTool({
      name: 'search_medication_coverage',
      description: 'Search the visible medication coverage reference by plan, medication name, category, subcategory, or coverage status.',
      inputSchema: {
        type: 'object',
        properties: {
          plan: { type: 'string' }, medication: { type: 'string' }, category: { type: 'string' },
          subcategory: { type: 'string' }, coverage_status: { type: 'string' }
        },
        additionalProperties: false
      },
      annotations: { readOnlyHint: true },
      execute: async (args) => {
        const plan = args.plan ? resolvePlan(args.plan) : null;
        if (args.plan && !plan) return { error: 'Plan not found. Use list_medication_categories or an exact visible plan name.' };
        if (plan) { state.planId = plan.id; el.planInput.value = plan.name; }
        if (args.medication !== undefined) { state.term = args.medication; el.medicationInput.value = args.medication; }
        if (args.category !== undefined) { state.category = args.category; el.categoryInput.value = args.category; }
        if (args.subcategory !== undefined) { state.subcategory = args.subcategory; el.subcategoryInput.value = args.subcategory; }
        if (args.coverage_status !== undefined) { state.coverage = args.coverage_status; el.coverageInput.value = args.coverage_status; }
        await ensurePlanData(state.planId);
        updateSubcategoryOptions();
        const matches = render();
        return { count: matches.length, plan: state.planId, results: matches.slice(0, 25).map((r) => ({
          name: r.name, brand: r.brand, category: r.category, subcategory: r.subcategory,
          coverage: r.coverage, pa: r.pa, source: sourceHref(r)
        })) };
      }
    });
    document.modelContext.registerTool({
      name: 'list_medication_categories',
      description: 'List available insurance plans, medication categories, and their subcategories.',
      inputSchema: { type: 'object', properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: true },
      execute: async () => ({ plans: state.data.plans, categories: state.data.subcategories })
    });
  }

  async function init() {
    ids.forEach((id) => { el[id] = document.getElementById(id); });
    try {
      const response = await fetch('./data.json.gz');
      if (!response.ok) throw new Error(`Data request failed: ${response.status}`);
      const bytes = new Uint8Array(await response.arrayBuffer());
      const text = bytes[0] === 0x1f && bytes[1] === 0x8b
        ? await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text()
        : new TextDecoder().decode(bytes);
      state.data = JSON.parse(text);
      const providerPlans = new Set(['az-complete-health', 'banner-ufc', 'uhc-community-az']);
      state.data.plans = state.data.plans.filter((plan) => providerPlans.has(plan.id));
      state.data.medications = state.data.medications.filter((record) => providerPlans.has(record.planId));
      state.data.policies = state.data.policies.filter((record) => providerPlans.has(record.planId));
      state.data.planEvidence = state.data.planEvidence.filter((record) => providerPlans.has(record.planId));
      state.data.planDataFiles = Object.fromEntries(Object.entries(state.data.planDataFiles || {}).filter(([id]) => providerPlans.has(id)));
      el.asOf.textContent = state.data.meta.asOf;
      // Preserve searches entered while the clinical dataset was loading.
      state.term = el.medicationInput.value;
      state.category = el.categoryInput.value;
      state.subcategory = el.subcategoryInput.value;
      state.coverage = el.coverageInput.value;
      state.planId = resolvePlan(el.planInput.value)?.id || state.planId;
      populateControls();
      bindEvents();
      bindCriteriaLibrary();
      render();
      registerModelTools();
    } catch (error) {
      el.loadingState.textContent = 'Coverage data could not be loaded. Please refresh or try again later.';
      console.error(error);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
