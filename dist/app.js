(() => {
  'use strict';

  const PAGE_SIZE = 50;
  const state = {
    data: null,
    planId: 'az-complete-health',
    term: '',
    selectedMedicationKey: null,
    category: '',
    subcategory: '',
    coverage: '',
    sort: 'az',
    limit: PAGE_SIZE,
  };

  const el = {};
  const ids = ['asOf', 'planInput', 'planOptions', 'medicationInput', 'medicationOptions',
    'categoryInput', 'categoryOptions', 'subcategoryInput', 'subcategoryOptions', 'coverageInput',
    'clearFilters', 'planStatus', 'planEvidence', 'evidenceList', 'resultCount', 'effectiveDate',
    'loadingState', 'emptyState', 'resultGrid', 'showMore',
    'criteriaLibrary', 'criteriaSearch', 'criteriaCount', 'criteriaResults', 'sortInput'];

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
    return selectedPlanRecords().concat(inheritedStatewideRows());
  }

  // Presentation only: do not alter the original payer text or its coverage record.
  function readableMedicationName(value) {
    const keepUpper = new Set(['ER', 'XR', 'SR', 'IR', 'DR', 'ODT', 'HFA', 'DPI', 'NDC', 'IV', 'IM', 'SC', 'SQ', 'LA', 'XL', 'EC', 'CR', 'CD', 'U', 'NPH', 'GLP', 'DPP', 'SGLT2', 'HIV', 'ADHD', 'HCTZ', 'MDI', 'ICS', 'LABA', 'LAMA', 'PFS', 'USP', 'OTC']);
    const unitCase = {MG: 'mg', MCG: 'mcg', ML: 'mL', MEQ: 'mEq', GM: 'g', HCL: 'HCl', NACL: 'NaCl', HBR: 'HBr', KWIKPEN: 'KwikPen', FLEXPEN: 'FlexPen', FLEXTOUCH: 'FlexTouch', SOLOSTAR: 'SoloStar', PENFILL: 'PenFill', REDIHALER: 'RediHaler'};
    return String(value ?? '').trim().replace(/\s+/g, ' ')
      .replace(/\b[A-Z][A-Z0-9]*\b/g, (word) => unitCase[word] || (keepUpper.has(word) ? word : word[0] + word.slice(1).toLowerCase()))
      .replace(/\b(\d+(?:\.\d+)?)(MG|MCG|ML|MEQ|GM)\b/g, (_, amount, unit) => amount + ' ' + unitCase[unit]);
  }

  const formWords = /\b(?:tablets?|capsules?|caplets?|solutions?|suspensions?|creams?|ointments?|gels?|lotions?|liquids?|syrups?|elixirs?|emulsions?|aerosols?|powders?|granules?|pellets?|patch(?:es)?|sprays?|drops?|suppositor(?:y|ies)|foams?|films?|lozenges?|troches?|gums?|inserts?|implants?|inhalers?|inhalants?|injections?|injectables?|shampoos?|enemas?|wafers?|wipes?|pastes?|mouthwash|rinse|toothpaste|medicated pads?|pledgets?|soap|tincture|douche|gas|sponge|transdermal system|intrauterine system|vaginal system|ring)\b/i;
  const supplyWords = /\b(?:test strips?|strips?|meters?|readers?|condoms?|diaphragms?|lancets?|needles?|syringe needles?|insulin syringes?|glucose monitor(?:ing)?(?: systems?| kits?)?|receivers?|lancing devices?|insulin pumps?|infusion sets?|transmitters?|sensors?|spacers?|chambers?|masks?|dressings?|bandages?|swabs?|alcohol (?:prep(?: pads?)?|pads?)|ketone tests?|blood glucose tests?|pen caps?|batter(?:y|ies)|control solutions?|sharps containers?)\b/i;
  const formAbbreviations = {tab: 'Tablet', tabs: 'Tablets', caps: 'Capsules', cap: 'Capsule', inj: 'Injection',
    soln: 'Solution', susp: 'Suspension', oint: 'Ointment', pwdr: 'Powder', arsl: 'Aerosol',
    supp: 'Suppository', odt: 'Orally Disintegrating Tablet'};
  function expandFormWords(name) {
    // Expand standalone formulary terms, preserving hyphenated trade names and supply names.
    if (supplyWords.test(name)) return name;
    return name.replace(/(^|\s)(tab|tabs|caps|cap|inj|soln|susp|oint|pwdr|arsl|supp|odt)(?=\s|$|[),])/gi,
      (_, space, word) => space + formAbbreviations[word.toLowerCase()]);
  }

  function compactPresentation(group) {
    const records = group.records || [];
    const first = records.length && reviewedCardPresentation(records[0]);
    return first?.packageLine && records.every(r => reviewedCardPresentation(r)?.heading === first.heading
      && reviewedCardPresentation(r)?.packageLine === first.packageLine) ? first : null;
  }

  function dosageFormHeading(group, label = group.label) {
    const compact = compactPresentation(group);
    if (compact) return compact.heading;
    const title = expandFormWords(label);
    const records = group.records || [];
    const labeledForm = records[0] && reviewedCardPresentation(records[0])?.dosageForm;
    if (labeledForm && records.every(r => reviewedCardPresentation(r)?.dosageForm === labeledForm)
        && !title.toLowerCase().includes(labeledForm.toLowerCase())) return title + ' — ' + labeledForm;
    if (formWords.test(title) || supplyWords.test(title)
        || (records.length && records.every(r => r.subcategory === 'Diabetes - Glucose Monitoring'))
        || /\bform (?:unspecified|unverified|unresolved)\b/i.test(title)) return title;
    // Each counted RxNorm pack component must end in the same explicit dosage form.
    if (records.length && records.every(r => r.rxnormId && r.name.startsWith('{'))) {
      const components = records.flatMap(r => r.name.split('}')[0].split(/\b\d+ \(/).slice(1));
      const forms = components.map(c => c.match(/\b((?:(?:extended release|delayed release|chewable|oral) )*(?:tablet|capsule|solution|suspension))\)\s*(?:\/\s*)?$/i)?.[1].toLowerCase());
      if (forms[0] && forms.every(form => form === forms[0])) return title + ' — ' + forms[0];
    }
    // Some reviewed headings retain the device while the payer also specifies the physical form.
    const printed = records.map(r => {
      const product = expandFormWords(r.name.split(/\s+\((?:brand|generic) for /i)[0]);
      const matches = [...product.matchAll(/\b(solution|suspension|cream|ointment|capsule|tablet)s?\b/gi)];
      // Multi-form descriptions and reconstitution instructions require the complete wording.
      return matches.length === 1 && !/reconst|powder|granul|\bfor\b|\b(?:er|xr|sr|dr)\b|delayed.release|extended.release/i.test(product)
        && !r.sourceConflict && !r.descriptionCorrection ? matches[0][1].toLowerCase() : '';
    });
    if (printed[0] && printed.every(form => form === printed[0])) return title + ' — ' + printed[0];
    const forms = new Set(records.map(r => r.rxTermsForm?.form));
    if (forms.size === 1 && records[0]?.rxTermsForm) {
      const form = records[0].rxTermsForm.form;
      return normalize(title).includes(normalize(form)) ? title : title + ' — ' + form;
    }
    return title + ' — dosage form unverified';
  }

  // These reviewed UHC rows need their printed product names for identity.
  // The parenthetical ingredient aliases omit formulation or strength.
  const distinctUhcPresentations = new Set([
    'uhc-oct-complete-aaa62ffa6b337f44', // Pulmicort suspension
    'uhc-oct-complete-07fe2aebae5a0ba6', // Uceris, form unspecified
    'uhc-oct-complete-dd63d43c87c2ba43', // Xarelto reconstituted oral suspension
    'uhc-oct-complete-90ac41e8f49cde43', // Xarelto oral tablets
    'uhc-oct-complete-466ed897a555d892', // Vyvanse capsules
    'uhc-oct-complete-67b306246b077d76', // Vyvanse chewables, 10–50 mg
    'uhc-oct-complete-77c5b244d4cb7020', // Vyvanse chewables, 60 mg
    'uhc-oct-complete-be91d378ac6cf394', // Tylenol oral suspension
    'uhc-oct-complete-39c4999cab7992c8', // Tylenol chewables
    'uhc-oct-complete-847afe1526008a20', // Tylenol standard tablets
  ]);

  // The October PDL's shared estradiol alias does not convey route or device.
  const uhcEstradiolPresentations = new Map([
    ['uhc-oct-complete-4a1149afa9a553fd', 'Alora Estradiol Twice-Weekly Patch'],
    ['uhc-oct-complete-e47a9b1dca9eed6b', 'Climara Estradiol Weekly Patch'],
    ['uhc-oct-complete-a1fd4a9ce974ca76', null], // Keep the original Divigel strength list.
    ['uhc-oct-complete-9565852ad73b0131', null], // Keep the concentration-only Divigel listing separate.
    ['uhc-oct-complete-928b9ed963c27b15', 'EstroGel Estradiol Transdermal Gel Pump'],
    ['uhc-oct-complete-4fe26eac35258974', 'Minivelle Estradiol Twice-Weekly Patch'],
    ['uhc-oct-complete-962d779bc98c5112', 'Vagifem Estradiol Vaginal Insert'],
    ['uhc-oct-complete-aef4eca1a35449a0', 'Vivelle-Dot Estradiol Twice-Weekly Patch'],
  ]);

  // Preserve the PDL's unspecified concentrations and packaging.
  const uhcTestosteronePresentations = new Map([
    ['uhc-oct-complete-95bdf1191fb6ac5a', 'AndroGel Testosterone Gel Pump (Concentration Unspecified)'],
    ['uhc-oct-complete-48446e194e4aaa49', 'Testim Testosterone Gel'],
    ['uhc-oct-complete-4f5abf9646902163', 'Vogelxo Testosterone Gel'],
    ['uhc-oct-complete-0618ed2eee749f42', 'Depo-Testosterone Cypionate IM (Concentration Unspecified)'],
    ['uhc-oct-complete-95f3abcf725dc69c', 'Testosterone Cypionate 200 mg/mL IM Solution (Brand Listing)'],
  ]);

  const uhcTriptanPresentations = new Map([
    ['uhc-oct-complete-225b27c2efa3ce8d', 'Maxalt (Rizatriptan Tablets)'],
    ['uhc-oct-complete-286fa8dd551d5183', 'Maxalt-MLT (Rizatriptan ODT)'],
    ['uhc-oct-complete-391d5cb4040d560f', 'Generic Rizatriptan (Dosage Form Unspecified)'],
    ['uhc-oct-complete-7a2afaed6fab2683', 'Generic Sumatriptan Oral (Dosage Form Unspecified)'],
  ]);

  const uhcNicotinePresentations = new Map([
    ['uhc-oct-complete-d1c2937b9b38c3e1', 'NicoDerm CQ (Nicotine Patch)'],
    ['uhc-oct-complete-3a0a37a01a0c20cd', 'Nicorette (Nicotine, Dosage Form Unspecified)'],
    ['uhc-oct-complete-634f76b31abaf672', 'Nicorette Mini (Nicotine Lozenge)'],
    ['uhc-oct-complete-d448da71a98f8d4c', 'Nicorette Starter Kit (Nicotine, Kit Contents Unspecified)'],
    ['uhc-oct-complete-190ba800fac4ab36', 'Thrive (Nicotine, Dosage Form Unspecified)'],
  ]);

  const uhcPCPFormLabels = new Map([
    ['uhc-oct-complete-e018bef948c68b97', 'Generic Oseltamivir Oral (Dosage Form Unspecified)'],
    ['uhc-oct-complete-a71cdeaaee7ac819', 'Tamiflu (Oseltamivir, Dosage Form Unspecified)'],
    ['uhc-oct-complete-420688dc751a74bb', 'Montelukast Oral Granules (Singulair Packets)'],
    ['uhc-oct-complete-3ea94beb4ebaf734', 'Diclofenac Epolamine 1.3% Topical Patch (Flector)'],
  ]);

  // Only use a device, concentration, or size if the exact listing supports it.
  const uhcInsulinAndSupplyLabels = new Map([
    ['uhc-oct-complete-96922f638bb987d2', 'Insulin Glargine-yfgn SC Solution (Device Unspecified)'],
    ['uhc-oct-complete-4270f8a1ce19e554', 'Insulin Glargine-yfgn SC Pen Injector'],
    ['uhc-oct-complete-31c74f821a4c856f', 'Semglee (Insulin Glargine-yfgn, Device Unspecified)'],
    ['uhc-oct-complete-c005b426150daab6', 'BD Pen Needle Micro Ultra-Fine'],
    ['uhc-oct-complete-d8778fc0002099ad', 'BD Pen Needle Mini Ultra-Fine'],
    ['uhc-oct-complete-29ba3ba96676a42d', 'BD Ultra-Fine Pen Needles (Size Unspecified)'],
    ['uhc-oct-complete-f4049ada026c8bf2', 'Embecta Nano Pen Needles'],
    ['uhc-oct-complete-81e91bccf7a7db62', 'Embecta Nano 2 Gen Pen Needles'],
    ['uhc-oct-complete-3d04833acbadee64', 'Embecta Ultra-Fine Pen Needles (31G × 5 mm or 8 mm)'],
    ['uhc-oct-complete-a78b03c4eeae093a', 'Embecta Ultra-Fine Pen Needles (32G × 6 mm)'],
    ['uhc-oct-complete-41e85281dfbe85c2', 'Insulin Pen Needles (29G × 12 mm, 31G × 5, 6 or 8 mm, or 33G × 4 mm)'],
    ['uhc-oct-complete-73c972bcaea5b9de', 'Insulin Pen Needles (32G × 4 mm or 6 mm)'],
    ['uhc-oct-complete-d44e6b5c3ba5f44e', 'BD Ultra-Fine Insulin Syringes (PA-Flagged Listing)'],
    ['uhc-oct-complete-72a4f8fa78ad8fa9', 'Embecta Ultra-Fine Insulin Syringes (31G × 15/64-inch, 0.3 mL)'],
    ['uhc-oct-complete-95af09ad92b3e0f1', 'Embecta Ultra-Fine Insulin Syringes (31G × 15/64-inch, 0.5 mL)'],
    ['uhc-oct-complete-6746ad40c619fcaa', 'Embecta Ultra-Fine Insulin Syringes (31G × 15/64-inch, 1 mL)'],
    ['uhc-oct-complete-3b25d168e772f4bb', 'BD AutoShield Duo Pen Needles'],
    ['uhc-oct-complete-c97b122f4df189e3', 'Embecta AutoShield Duo Pen Needles'],
    ['uhc-oct-complete-c4e9ac46f2349955', 'BD Ultra-Fine Insulin Syringes (Size Unspecified)'],
    ['uhc-oct-complete-22070f6565eaddd7', 'BD Ultra-Fine Insulin Syringes (31G × 5/16-inch, 0.3 mL)'],
    ['uhc-oct-complete-8f8bfca30d969dde', 'Embecta Ultra-Fine Insulin Syringes (Half-Unit Markings)'],
    ['uhc-oct-complete-f91198d15b3621e2', 'Embecta Ultra-Fine Insulin Syringes (30G × 1/2-inch, 0.3 mL)'],
    ['uhc-oct-complete-f119ef35ec9d1e98', 'Embecta Ultra-Fine Insulin Syringes (30G × 1/2-inch, 0.5 mL)'],
    ['uhc-oct-complete-1a93bee462473cf9', 'Embecta Ultra-Fine Insulin Syringes (30G × 1/2-inch, 1 mL)'],
    ['uhc-oct-complete-f585b5e77ab99c2b', 'Embecta Ultra-Fine Insulin Syringes (31G × 5/16-inch, 0.3 mL)'],
    ['uhc-oct-complete-3369cc3c10c7bce9', 'Embecta Ultra-Fine Insulin Syringes (31G × 5/16-inch, 0.5 mL)'],
    ['uhc-oct-complete-c13ee393243d1dfe', 'Embecta Ultra-Fine Insulin Syringes (31G × 5/16-inch, 1 mL)'],
    ['uhc-oct-complete-47f6c2b5f18c5f97', 'Embecta Ultra-Fine Pen Needles (29G × 12.7 mm)'],
    ['uhc-oct-complete-8a18c2c65b39a452', 'Insulin Pen Needles (29G × 12.7 mm)'],
    ['uhc-oct-complete-71a7f5b0011ace42', 'Insulin Syringes (29G × 1/2-inch, 1 mL; 30G × 5/16-inch, 0.5 mL; or 31G × 5/16-inch, 1 mL)'],
    ['uhc-oct-complete-982cb3c91791283c', 'Insulin Syringes (31G × 5/16-inch, 0.3 or 0.5 mL)'],
  ]);
  const uhcReviewedProductGroups = new Map([
    ['Dabigatran Oral Capsules (Pradaxa)', [
      ['b6707e516d2355ba', 'Generic dabigatran oral capsules'],
      ['009ca23afd12966f', 'Brand Pradaxa oral capsules'],
    ]],
    ['Dulera Metered-Dose Inhalation Aerosol', [['e27f2cb8dcfa082e']]],
    ['Perforomist Nebulizer Solution', [['0d5d9de3ba6af1f0']]],
    ['Lokelma Powder for Oral Suspension', [['877751e558a7560e']]],
    ['Serevent Diskus Dry Powder Inhaler', [['629099550c0bfd47']]],
    ['Stiolto Respimat Inhalation Spray', [['27e0a28ebfd41f7c']]],
    ['Topamax Oral Tablets', [['8e34212b5a29106f']]],
    ['Topamax Oral Sprinkle Capsules', [['d37573826a734ebb']]],
    ['Risperidone Oral Solution 1 mg/mL (Risperdal)', [
      ['ef1b74ce89ce3609', 'Brand Risperdal oral solution'],
      ['3a61ac9c932595a2', 'Generic risperidone oral solution'],
    ]],
    ['Risperidone Oral Tablets 0.25–3 mg (Risperdal)', [
      ['9218dfef977f1cc2', 'Brand Risperdal tablets 0.5, 1, 2 or 3 mg'],
      ['88dcfe556959a236', 'Generic risperidone tablet 0.25 mg'],
      ['5c298a57a90c3332', 'Generic risperidone tablet 0.5 mg'],
      ['fce9a9e679b436ee', 'Generic risperidone tablet 1 mg'],
      ['ed3c9eb0d5ff5667', 'Generic risperidone tablet 2 mg'],
      ['41d9e57befa93814', 'Generic risperidone tablet 3 mg'],
    ]],
    ['Risperidone Oral Tablets 4 mg (Risperdal)', [
      ['f4378fc22a9c05ca', 'Brand Risperdal tablet 4 mg'],
      ['3b293a6608a5bb5c', 'Generic risperidone tablet 4 mg'],
    ]],
    ['Risperidone Microspheres ER Intramuscular Suspension (Risperdal Consta)', [
      ['8e6412598dc3cc82', 'Brand Risperdal Consta 12.5 mg'],
      ['86a272013762dd71', 'Brand Risperdal Consta 25 mg'],
      ['4a432871483f8345', 'Brand Risperdal Consta 37.5 mg'],
      ['e60cf4ef12c45d4c', 'Brand Risperdal Consta 50 mg'],
      ['286fbac321cc9cd6', 'Generic risperidone microspheres ER (strength unspecified)'],
    ]],
    ['Dexmethylphenidate ER Capsules (Focalin XR)', [
      ['6dff573813c31f0b', 'Generic dexmethylphenidate ER'],
      ['b49b6b0ee990825a', 'Brand Focalin XR'],
    ]],
    ['Acetaminophen / Aspirin / Caffeine (Excedrin, Vanquish)', [
      ['381dc96046cede50', 'Excedrin Extra Strength caplets', '691b754c-bafc-47e2-a322-cf56245c01f6'],
      ['ea6243f0a15464a5', 'Excedrin Migraine caplets', '910d7254-d0f4-4c5c-a26e-7f8acecbe02d'],
      ['8869cd1c155ab813', 'Excedrin Migraine Relief caplets', 'dd85f3a7-f4d2-4ea0-a7b6-18ebc0e993d8'],
      ['7c9120dc84a697eb', 'Vanquish Extra Strength caplets', 'cbf12223-ef44-494b-9d3c-971dce3c5ade'],
    ]],
    ['Acetaminophen / Aspirin / Caffeine (Generic Listing for Excedrin Extra Strength)', [
      ['4df17abd4833e4f1', 'Generic listing for Excedrin Extra Strength'],
    ]],
    ['Nitrofurantoin Macrocrystals Capsules', [['1f745c455ddaac86']]],
    ['Nitrofurantoin Monohydrate / Macrocrystals Capsules (Macrobid)', [['2304475710970aa6']]],
  ].flatMap(([group, records]) => records.map(([id, label, labelId]) => ['uhc-oct-complete-' + id, {group, label, labelId}])));
  const uhcReviewedPaConflicts = new Set([
    '3b25d168e772f4bb', '22070f6565eaddd7', 'c4e9ac46f2349955', '3a61ac9c932595a2',
    '8e6412598dc3cc82', '86a272013762dd71', '4a432871483f8345', 'e60cf4ef12c45d4c',
  ].map(id => 'uhc-oct-complete-' + id));
  const uhcDuplicationPolicies = new Set(['GL-735259', 'GL-733328']);

  const uhcAgeEightRows = new Set([
    'uhc-oct-complete-2468f91090660c63',
    'uhc-oct-complete-90702ce4eec9617a',
    'uhc-oct-complete-c52599e942ff4716',
    'uhc-oct-complete-f24f86de993ce49c'
  ]);
  const uhcBrandTopamaxRows = new Set(['uhc-oct-complete-8e34212b5a29106f', 'uhc-oct-complete-d37573826a734ebb']);
  const genericDabigatranId = 'uhc-oct-complete-b6707e516d2355ba';
  const uhcLowStrengthAlbuterolId = 'uhc-oct-complete-2468f91090660c63';
  const generalNonsolidPolicyId = 'uhc-nov2026-policy-gl-545275';
  const uhcAgePaCardLabels = new Map([
    ['uhc-oct-complete-de1ca42f17826905', 'Asmanex HFA Metered-Dose Inhalation Aerosol'],
    ['uhc-oct-complete-14ba345bf06d2a5e', 'Enalapril Maleate Oral Solution (Generic for Epaned)'],
    ['uhc-oct-complete-9e0eb4cf3a3dfd2b', 'Nitrofurantoin Oral Suspension (25 mg/5 mL)'],
    ['uhc-oct-complete-e29a433265e8ba09', 'Calcitriol Oral Solution']
  ]);
  const uhcStandalonePolicyReferences = new Map([
    ['arnuity_request_reference', {
      label: 'UHC asthma request guideline',
      scope: 'For a request involving preferred brand Arnuity Ellipta, UHC requires a diagnosis of asthma and lists a 12-month approval duration.'
    }],
    ['general_nebulizer_reference', {
      label: 'General nebulizer policy',
      scope: 'General non-solid dosage form guidance. The age-specific albuterol approval criteria are unverified.'
    }],
    ['general_nonsolid_reference', {
      label: 'General non-solid guidance',
      scope: 'General non-solid dosage form guidance. Product-specific approval criteria are unverified.'
    }],
    ['methadose_pain_reference', {
      label: 'Related UHC pain guideline',
      scope: 'The guideline names Methadose for pain. The FDA label is for opioid addiction treatment, not analgesia; OUD authorization criteria are unverified.'
    }],
    ['nucynta_ir_reference', {
      label: 'Related UHC short-acting opioid guideline',
      scope: 'The guideline names generic tapentadol tablets and tapentadol solution; applicability to brand Nucynta tablets is unverified.'
    }],
    ['korlym_reference', {
      label: 'Korlym brand policy reference',
      scope: 'The guideline names Korlym. Applicability to generic mifepristone 300 mg is unverified.'
    }],
    ['psoriasis_ointment_reference', {
      label: 'UHC psoriasis guideline (ointment only)',
      scope: 'The guideline names calcitriol ointment for psoriasis. The payer listing omits dosage form; applicability to the exact listing is unverified. This reference does not establish routine PA.'
    }],
    ['cough_reference', {
      label: 'Related UHC cough and cold guideline',
      scope: 'UHC lists age and quantity limits but does not specify the form or threshold. This related guideline names Hydromet and generic Tussigon. Its age-specific PA and quantity-exception criteria are not verified for this exact listing.'
    }],
    ['epaned_reference', {
      label: 'Epaned policy reference',
      scope: 'This guideline names Epaned. Applicability to generic enalapril oral solution is unverified.'
    }]
  ]);
  const uhcNebulizedAlbuterol = new Map([
    [uhcLowStrengthAlbuterolId, {
      label: 'Albuterol Nebulizer Solution (0.63 mg/3 mL and 1.25 mg/3 mL)'
    }],
    ['uhc-oct-complete-b92ed6e2e4412ed4', {
      label: 'Albuterol Nebulizer Solution (2.5 mg)',
      note: '2.5 mg/3 mL (0.083%) is ready to use. Dilute 2.5 mg/0.5 mL (0.5%) before use per product labeling.'
    }],
    ['uhc-oct-complete-f597c1c77d71c7d1', {
      label: 'Albuterol Nebulizer Concentrate (5 mg/mL, 0.5%)',
      note: 'Dilute before use per product labeling. UHC lists both Tier 1 and Tier 2. The formulary does not identify which package belongs to each tier.'
    }]
  ]);
  const bannerInsulinConflicts = new Map([
    ['banner-source-review-11-1-5', {
      label: 'Humulin N KwikPen (NPH Insulin Suspension Pen, U-100)',
      reason: 'Banner lists this pen as regular insulin solution.'
    }],
    ['banner-source-review-11-1-10', {
      label: 'Lantus SoloStar (Insulin Glargine Solution Pen, U-100)',
      reason: 'Banner lists this pen as a suspension.'
    }]
  ]);

  const uhcAvivaDeviceId = 'uhc-oct-complete-a89f51ba9ac72dbf';
  const uhcReviewedTestStrips = new Map([
    ['uhc-oct-complete-46893ffdc5e59e64', 'Accu-Chek Aviva Plus Test Strips'],
    ['uhc-oct-complete-8e024e8124a5df6a', 'Accu-Chek Guide Test Strips'],
    ['uhc-oct-complete-0a0a7a86b6fe2cd4', 'Accu-Chek SmartView Test Strips']
  ]);
  const uhcTestStripPolicyId = 'uhc-nov2026-policy-gl-369221';
  const twiceDailyStripNote = 'One PDL row allows twice-daily testing for members who do not use insulin. The other prints step therapy without a sequence. The plan does not identify which packages correspond to these rows.';
  const contourMeterNote = 'UHC lists both a nonpreferred Tier 2 row with PA and a preferred Tier 2 row with no PA field. Both print QL. Package-specific preference and PA are unverified.';
  const contourStripNote = 'UHC lists a nonpreferred Tier 2 row with PA and a preferred Tier 2 row with step therapy. Both print QL. Package applicability and the step sequence are unverified.';
  const uhcReviewedGlucoseSupplies = new Map([
    ['uhc-oct-complete-fda008f4a380e9be', {label: 'OneTouch Ultra Blood Glucose Test Strips', note: twiceDailyStripNote, pages: [118], strip: true}],
    ['uhc-oct-complete-b63e51cd8be09d8d', {label: 'OneTouch Verio Blood Glucose Test Strips', note: twiceDailyStripNote, pages: [118], strip: true}],
    ['uhc-oct-complete-fe3ff8d27057990e', {label: 'Contour NEXT EZ Blood Glucose Meter Kit', note: contourMeterNote, pages: [117, 118], meterPolicy: true}],
    ['uhc-oct-complete-5cc8dca197dd0e7c', {label: 'Contour NEXT GEN Blood Glucose Meter Kit', note: contourMeterNote, pages: [117, 118]}],
    ['uhc-oct-complete-b1c1c0d0058a712f', {label: 'Contour NEXT Blood Glucose Test Strips', note: contourStripNote, pages: [117, 118], strip: true}],
    ['uhc-oct-complete-30d30a1af87b546e', {label: 'Contour Blood Glucose Test Strips', note: contourStripNote, pages: [117, 119], strip: true}],
    ['uhc-oct-complete-a2688cb7eea9b098', {label: 'OneTouch Verio Flex Blood Glucose Meter Kit', meterPolicy: true}]
  ]);
  const uhcMeterPolicyId = 'uhc-nov2026-policy-gl-140734';
  function isUhcOctoberRow(record) {
    return record.planId === 'uhc-community-az' && !record.isStatewideReference
      && record.sourceEffective === '2026-10-01';
  }

  function uhcAgeEightPa(record) {
    return record.planId === 'uhc-community-az' && !record.isStatewideReference
      && record.sourceEffective === '2026-10-01' && record.pa === 'conditional'
      && (uhcAgeEightRows.has(record.id) || uhcAgePaCardLabels.has(record.id))
      && record.rawRestrictions?.includes('Members >= 8 years of age will require PA');
  }

  // Group only when the generic, formulation, route, release and strength text
  // match exactly. All source records and individual restrictions stay separate.
  function medicationIdentity(record) {
    const name = (record.displayName || record.name || '').trim();
    const presentation = reviewedCardPresentation(record);
    if (presentation?.label) return {key: record.planId + ':' + normalize(presentation.label), generic: presentation.label, brands: []};
    const reviewedForm = record.planId === 'uhc-community-az' ? uhcNebulizedAlbuterol.get(record.id)
      : record.planId === 'banner-ufc' ? bannerInsulinConflicts.get(record.id) : null;
    if (reviewedForm) return {key: `${record.planId}:${record.id}`, generic: reviewedForm.label, brands: []};
    const agePaLabel = record.planId === 'uhc-community-az' && uhcAgePaCardLabels.get(record.id);
    if (agePaLabel) return {key: `${record.planId}:${record.id}`, generic: agePaLabel, brands: []};
    if (isUhcOctoberRow(record)) {
      const label = record.id === uhcAvivaDeviceId ? 'Accu-Chek Aviva Blood Glucose Meter'
        : uhcReviewedTestStrips.get(record.id) || uhcReviewedGlucoseSupplies.get(record.id)?.label || uhcGvokePresentations.get(record.id)?.label;
      if (label) {
        const sourceBrand = uhcReviewedGlucoseSupplies.has(record.id)
          ? name.match(/^(.*?)\s*\(brand for /i)?.[1] : '';
        return {key: record.planId + ':' + record.id, generic: label, brands: sourceBrand ? [sourceBrand] : []};
      }
    }
    // This October PDL cross-reference spans incompatible control families and a meter.
    // The source name remains available in search and Sources.
    if (isUhcOctoberRow(record)) {
      const control = record.name.match(/^(.+?) \(brand for element compact control 2\)$/i);
      if (control) return {key: record.planId + ':' + record.id, generic: control[1], brands: []};
    }
    const genericFor = name.match(/^(.*?)\s*\(generic for ([^)]+)\)\s*$/i);
    const brandFor = name.match(/^(.*?)\s*\(brand for ([^)]+)\)\s*$/i);
    if (record.planId === 'banner-ufc' || record.planId === 'uhc-community-az') {
      const productId = record.isStatewideReference ? record.id.split(':').pop() : record.id;
      // The payer prints the same aerosol description for two different devices.
      if (['banner-pcp-nov10-039', 'uhc-oct-complete-aadf073c434c4009', 'formulary-9822'].includes(productId)) {
        return {key: record.planId + ':advair-hfa', generic: 'Fluticasone-Salmeterol Metered-Dose Inhalation Aerosol', brands: ['ADVAIR HFA']};
      }
      if (['banner-pcp-nov10-038', 'formulary-9820'].includes(productId)) {
        return {key: record.planId + ':airduo-respiclick', generic: 'Fluticasone-Salmeterol Dry Powder Inhaler', brands: ['AirDuo RespiClick']};
      }
      if (['banner-full-a2a4d1dc0085c78f', 'formulary-9821'].includes(productId)) {
        return {key: record.planId + ':airduo', generic: 'Fluticasone-Salmeterol Breath-Actuated Inhalation Powder', brands: ['AirDuo']};
      }
    }
    if (record.id === 'uhc-oct-complete-c2d62d774fbaa9ab') {
      return {key: `${record.planId}:${record.id}`, generic: 'Sertraline HCl Oral Solution (Concentrate)', brands: ['ZOLOFT']};
    }
    if (record.id === 'uhc-oct-complete-b91029349d6055f8' || record.id === 'uhc-oct-complete-4848e3a8d39fd8d9') {
      return {key: `${record.planId}:pantoprazole-suspension-packets`, generic: 'Pantoprazole Sodium Packets', brands: ['PROTONIX']};
    }
    if (record.id === 'uhc-oct-complete-9e58d3383e72691c' || record.id === 'uhc-oct-complete-136c92bbb186b8d5') {
      const formulation = record.id === 'uhc-oct-complete-9e58d3383e72691c'
        ? 'ER Granules for Oral Suspension' : 'ER Tablets';
      return {key: `${record.planId}:${record.id}`, generic: `Mirabegron ${formulation}`, brands: ['MYRBETRIQ']};
    }
    if (record.planId === 'uhc-community-az' && uhcEstradiolPresentations.has(record.id)) {
      const generic = uhcEstradiolPresentations.get(record.id) || `${brandFor?.[1].trim() || name} (Estradiol)`;
      return {key: `${record.planId}:${record.id}`, generic, brands: []};
    }
    const reviewedProduct = uhcReviewedProductGroups.get(record.id);
    if (reviewedProduct) {
      return {key: `${record.planId}:${reviewedProduct.group}`, generic: reviewedProduct.group, brands: []};
    }
    const reviewedLabel = uhcTestosteronePresentations.get(record.id)
      || uhcTriptanPresentations.get(record.id) || uhcNicotinePresentations.get(record.id)
      || uhcPCPFormLabels.get(record.id) || uhcInsulinAndSupplyLabels.get(record.id);
    if (record.planId === 'uhc-community-az' && reviewedLabel) {
      return {key: `${record.planId}:${record.id}`, generic: reviewedLabel, brands: []};
    }
    if (record.planId === 'uhc-community-az' && record.id === 'uhc-oct-complete-2cf325e856cd66c2') {
      // The PDL states the route but does not identify tablets or suspension.
      return {key: `${record.planId}:${record.id}`, generic: 'Azithromycin Oral (Dosage Form Unspecified)', brands: []};
    }
    if (record.planId === 'uhc-community-az' && distinctUhcPresentations.has(record.id)) {
      return {key: `${record.planId}:${record.id}`, generic: brandFor?.[1].trim() || name, brands: []};
    }
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
    // A payer's parenthetical ingredient alias can hide different presentations.
    // Keep the printed products separate when that alias cannot establish equivalence.
    const pairedBrand = brandFor?.[1] || genericFor?.[2];
    const distinctProduct = pairedBrand && !device && (!formWords.test(expandFormWords(generic))
      || (brandFor && (formWords.test(expandFormWords(pairedBrand)) || /\d/.test(pairedBrand))));
    const productKey = distinctProduct ? ':product:' + normalize(pairedBrand) : '';
    return {key: `${record.planId}:${normalize(generic)}${variant}${deviceBrand}${productKey}`, generic, brands};
  }

  // Exact duplicate bracketed brand names are presentation artifacts.
  // Preserve the underlying payer product name, source links and PA records.
  function medicationDisplayLabel(name, brands, records = []) {
    if (records.length === 1 && uhcReviewedGlucoseSupplies.has(records[0].id)) return name;
    if (records.length === 1 && records[0].planId === 'uhc-community-az'
        && (uhcTriptanPresentations.has(records[0].id) || uhcNicotinePresentations.has(records[0].id)
          || uhcPCPFormLabels.has(records[0].id) || uhcInsulinAndSupplyLabels.has(records[0].id))) return name;
    if (records.some(record => uhcReviewedProductGroups.has(record.id) || reviewedCardPresentation(record)?.label)) return name;
    // Display names come from NLM by the existing RxCUI, not from parsing
    // package syntax. A group spanning different IDs keeps its source label.
    if (records.length && records.every(record => record.standardName
        && record.rxnormId === records[0].rxnormId)) return records[0].standardName;
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
      label: medicationDisplayLabel(group.name, group.brands, group.records),
      search: [group.name, ...group.brands, ...group.records.flatMap(r => [r.displayName || r.name, r.standardName || '', ...(r.searchAliases || [])])].join(' ')
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
    const form = expandFormWords(n).match(/\b(solution|suspension|liquid|syrup|elixir|cream|ointment|gel|lotion|foam|powder|spray)\b/i);
    if (form) return form[1].toLowerCase();
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
    if (planGroup.key?.includes(':product:') && !sharedBrand) return false;
    // Verified plan notices may identify a trade name with a route suffix,
    // without populating the separate brand field (e.g. MOUNJARO (SUBCUTANEOUS)).
    const routeSuffix = planGroup.name.match(/^(.*?)\s*\((subcutaneous|oral|topical|nasal|inhalation|intravenous|intramuscular)\)\s*$/i);
    const routeBrand = routeSuffix && sharedGroup.brands.some(b => normalize(b) === normalize(routeSuffix[1]));
    if (!sameName && !sharedBrand && !routeBrand) return false;
    const resolvedForms = group => new Set((group.records || []).map(r => r.rxTermsForm?.form).filter(Boolean));
    const left = resolvedForms(planGroup), right = resolvedForms(sharedGroup);
    if (left.size && right.size && new Set([...left, ...right]).size > 1) return false;
    const a = medicationRoute(planGroup.name), b = medicationRoute(sharedGroup.name);
    if (!a || !b || a !== b) return sameName && a === b;
    const formA = medicationForm(planGroup.name), formB = medicationForm(sharedGroup.name);
    // A broad source description may omit the device, but explicit conflicting
    // forms and release mechanisms must never be merged.
    if (formA && formB && formA !== formB) {
      const injectionPackage = new Set(['auto-injector', 'syringe', 'vial', 'pen']);
      if (!(a === 'injection' && injectionPackage.has(formA) !== injectionPackage.has(formB))) return false;
    }
    if (releaseKind(planGroup.name) !== releaseKind(sharedGroup.name)) return false;
    const strengthA = strengthTokens(planGroup.name), strengthB = strengthTokens(sharedGroup.name);
    if (strengthA.length && strengthB.length && !strengthA.every(token => strengthB.includes(token))) return false;
    return true;
  }

  // Preserve unmatched products as the selected plan's supplement. Attach only
  // unambiguous equivalent products to the statewide entry; never blend rules.
  const groupCache = new Map();
  const constipationGenericRows = new Map([
    ['uhc-oct-complete-1648922bcbfb41de', 'Generic lubiprostone 24 mcg oral capsule'],
    ['uhc-oct-complete-62acb905190fdbd1', 'Generic lubiprostone 8 mcg oral capsule'],
    ['uhc-oct-complete-a75bf7c192276842', 'Generic prucalopride oral tablet']
  ]);
  const uhcLinzessId = 'uhc-oct-complete-856ab149c565f2d6';
  const uhcMotegrityId = 'uhc-oct-complete-e1b4c7a47cd7c144';
  const bannerLubiprostoneId = 'banner-full-df398cde927a2a85';
  const achSmartRecords = new Set(['ach-json-1246288', 'ach-json-1246304', 'az-complete-health:statewide:formulary-9819']);
  const achSmartNoticeUrl = 'https://www.azcompletehealth.com/newsroom/PU26135.html';

  const achConstipationLabels = new Map([
    ['ach-notice-13846', 'Linzess (linaclotide) oral capsules'],
    ['ach-notice-13847', 'Lubiprostone oral capsules (authorized generic)'],
    ['ach-notice-13848', 'Lubiprostone oral capsules (generic)'],
    ['ach-notice-13849', 'Prucalopride oral tablets']
  ]);
  const constipationPolicyId = 'uhc-nov2026-policy-gl-720196';

  const symbicortGenericNote = 'UHC source rows disagree on step therapy. Both print a quantity limit. The plan does not specify the applicable step or which packages it affects.';
  const tiotropiumContinuation = 'Continued use of two or more drugs in this class may require PA.';
  const fluticasoneUnspecified = 'Fluticasone Propionate Oral Inhalation (Dosage Form Unspecified)';
  const tiotropiumCapsules = 'Tiotropium Inhalation Capsules (Spiriva HandiHaler)';
  const spirivaSpray = 'Spiriva Respimat Metered Inhalation Spray';
  const epiPenAutoInjector = 'Epinephrine Anaphylaxis Autoinjector (EpiPen Reference)';
  const bannerEpiPenIds = new Set(['banner-full-2d2738513f664b31', 'banner-full-450fe20ea940c46c']);
  const bannerEpiPenDisplay = {label: epiPenAutoInjector, note: 'Banner: Viatris SP authorized generic only. Quantity limit: 2 per 30 days. PA is required above 2 per month.'};
  const augmentinSuspension = 'Amoxicillin/Clavulanate Oral Suspension (Augmentin Reference)';
  const rosuvastatinTablets = 'Rosuvastatin Tablets (Crestor Reference)';
  const simvastatinTablets = 'Simvastatin Tablets (Zocor Reference)';
  const genericStatinNote = 'UHC lists a quantity limit without specifying the numeric amount.';
  const butransPatches = 'Buprenorphine Transdermal Patches (Butrans)';
  // Package sizes describe the labeled product. Benefit and preference notes belong to each source row.
  const lisproProducts = {
    lisproPen: {heading: "Insulin lispro 100 units/mL KwikPen", packageLine: "3 mL · 1-unit increments", searchAlias: "insulin lispro U-100 injection prefilled pen", dosageForm: "solution",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=97d5e596-aae1-42c9-ae89-c3780959c467"},
    lisproVial: {heading: "Insulin lispro 100 units/mL multidose vial", packageLine: "Vial size: 10 mL", searchAlias: "insulin lispro U-100 injection", dosageForm: "solution",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=97d5e596-aae1-42c9-ae89-c3780959c467"},
    juniorPen: {heading: "Insulin lispro 100 units/mL Junior KwikPen", packageLine: "3 mL · 0.5-unit increments", searchAlias: "insulin lispro U-100 injection prefilled pen", dosageForm: "solution",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=97d5e596-aae1-42c9-ae89-c3780959c467"},
    mixPen: {heading: "Insulin lispro protamine/lispro 75/25 100 units/mL KwikPen", packageLine: "3 mL · 1-unit increments · suspension", searchAlias: "insulin lispro U-100 injection insulin lispro protamine prefilled pen", dosageForm: "suspension",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e49f701d-c19f-4cb2-b63f-01a917b33abc"},
    admelogVial: {heading: "Admelog 100 units/mL multidose vial", packageLine: "Vial sizes: 3 mL, 10 mL", searchAlias: "insulin lispro U-100 injection", dosageForm: "solution",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=0691def8-4a7b-4de3-866f-a280989f47f1"},
    admelogPen: {heading: "Admelog 100 units/mL SoloStar", packageLine: "3 mL · 1-unit increments", searchAlias: "insulin lispro U-100 injection prefilled pen", dosageForm: "solution",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=0691def8-4a7b-4de3-866f-a280989f47f1"},
    humalogVialCartridge: {heading: "Humalog 100 units/mL vial or cartridge", packageLine: "Vial size: 10 mL · Cartridge: 3 mL", searchAlias: "insulin lispro U-100 injection", dosageForm: "solution",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c8ecbd7a-0e22-4fc7-a503-faa58c1b6f3f"},
    humalogPen: {heading: "Humalog 100 units/mL KwikPen", packageLine: "3 mL · 1-unit increments", searchAlias: "insulin lispro U-100 injection prefilled pen", dosageForm: "solution",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c8ecbd7a-0e22-4fc7-a503-faa58c1b6f3f"},
    humalogMixVial: {heading: "Humalog Mix 75/25 100 units/mL multidose vial", packageLine: "Vial size: 10 mL · suspension", searchAlias: "insulin lispro U-100 injection insulin lispro protamine", dosageForm: "suspension",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c73da51a-1899-45ad-b6cf-9c52c36a25dd"},
    humalogMixPen: {heading: "Humalog Mix 75/25 100 units/mL KwikPen", packageLine: "3 mL · 1-unit increments · suspension", searchAlias: "insulin lispro U-100 injection insulin lispro protamine prefilled pen", dosageForm: "suspension",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c73da51a-1899-45ad-b6cf-9c52c36a25dd"},
    humalogFiftyPen: {heading: "Humalog Mix 50/50 100 units/mL KwikPen", packageLine: "3 mL · 1-unit increments · suspension", searchAlias: "insulin lispro U-100 injection insulin lispro protamine prefilled pen", dosageForm: "suspension",
      labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b34cd3ff-d0af-4852-b4ef-2a8b4a93aeae"},
  };
  const uhcLisproConflict = "UHC’s printed list flags PA. Its electronic list flags step therapy and reports no PA. Verify the restriction before prescribing.";
  const baqsimiPresentation = {
    dosageForm: '3 mg nasal powder', identityRxcui: 2180671,
    labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f1f5df9b-872f-44e5-a18f-f0b68e7e9254'
  };
  const zegalogueLabelUrl = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c6c32b47-c47c-4a7f-8d4d-23578f663217';
  const gvokeHypoPenDoses = '0.5 mg/0.1 mL or 1 mg/0.2 mL per autoinjector';
  const uhcGvokePresentations = new Map([
    ['uhc-oct-complete-5fcb0ddd3560f776', {
      label: 'Gvoke HypoPen Subcutaneous Autoinjector (1-Pack)', dose: gvokeHypoPenDoses
    }],
    ['uhc-oct-complete-7caf82e6ee33bfff', {
      label: 'Gvoke HypoPen Subcutaneous Autoinjector (2-Pack)', dose: gvokeHypoPenDoses
    }],
    ['uhc-oct-complete-a5fa4856ca09e8de', {
      label: 'Gvoke PFS Subcutaneous Prefilled Syringe', dose: '1 mg/0.2 mL per prefilled syringe'
    }],
    ['uhc-oct-complete-5eca184f4914d610', {
      label: 'Gvoke Kit Ready-to-Use Subcutaneous Solution (Vial and Syringe)', dose: '1 mg/0.2 mL per vial'
    }]
  ]);

  const gvokeLabelUrl = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=92385737-dbad-98c5-e053-2995a90a2805';
  const reviewedCardPresentations = new Map([
    ['uhc-oct-complete-86d347968a4e113f', {
      label: 'Humulin R U-500 KwikPen (regular insulin) 500 units/mL prefilled pen', dosageForm: 'solution for injection', separate: true,
      identityRxcui: 1731317, labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b60e8dd0-1d48-4dc9-87fd-e14675255e8c',
      note: '3 mL single-patient-use pen. Dial the prescribed units in 5-unit increments. Never withdraw insulin from the pen into a syringe.'
    }],
    ['uhc-oct-complete-2c1a20b7db0eeaaa', {
      label: 'Humulin 70/30 KwikPen (human NPH/regular insulin) 100 units/mL prefilled pen', dosageForm: 'injectable suspension', separate: true,
      identityRxcui: 847189, labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e245e0c5-b2d6-418b-baa4-1c3324292885',
      note: '3 mL single-patient-use pen. Each mL contains 70 units of NPH insulin and 30 units of regular insulin.'
    }],
    ['uhc-oct-complete-02f43d7633c6ae85', {
      label: 'Humulin 70/30 (human NPH/regular insulin) 100 units/mL multidose vial', dosageForm: 'injectable suspension', separate: true,
      identityRxcui: 106892, labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e245e0c5-b2d6-418b-baa4-1c3324292885',
      note: 'Labeled presentation: 10 mL multidose vial. Each mL contains 70 units of NPH insulin and 30 units of regular insulin.'
    }],
    ['uhc-oct-complete-b075e8c634ca1a47', {
      label: 'Dexmethylphenidate HCl oral tablet (generic for Focalin)', dosageForm: 'oral tablet', separate: true,
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=987b4983-1edc-40f1-adc9-724747080969',
      labelProductExamples: [['2.5 mg', 899557], ['5 mg', 899518], ['10 mg', 899548]]
    }],
    ['uhc-oct-complete-e381880966e4d494', {
      label: 'Methylphenidate transdermal patch (generic for Daytrana)', dosageForm: 'transdermal patch', separate: true,
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1643b6a5-80da-4d4f-8c5f-feb907875702',
      labelProductExamples: [['10 mg/9 hours', 753436], ['15 mg/9 hours', 753438], ['20 mg/9 hours', 753440], ['30 mg/9 hours', 753441]]
    }],
    ['uhc-oct-complete-f5b56fa0299bad0c', {
      label: 'Methylphenidate HCl CD extended-release oral capsule (generic for Metadate CD)', dosageForm: 'extended-release oral capsule', separate: true,
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e45c75dc-d381-475b-b649-a871c8a36e60',
      labelProductExamples: [['10 mg', 1806181], ['20 mg', 1806187], ['30 mg', 1806189], ['40 mg', 1806191], ['50 mg', 1806193], ['60 mg', 1806197]]
    }],
    ['uhc-oct-complete-229568f7f286fb5b', baqsimiPresentation],
    ['uhc-oct-complete-1c725dc535b842a6', baqsimiPresentation],
    ['ach-json-2535243', {dosageForm: 'subcutaneous solution', identityRxcui: 2535243, labelUrl: zegalogueLabelUrl}],
    ['ach-notice-13882', {dosageForm: '0.6 mg/0.6 mL injection solution', identityRxcui: 2535249, labelUrl: zegalogueLabelUrl}],
    ['ach-notice-13883', {dosageForm: '0.6 mg/0.6 mL injection solution', identityRxcui: 2535243, labelUrl: zegalogueLabelUrl}],
    ["uhc-oct-complete-2dbe0497f9246f1b", {...lisproProducts.lisproPen,
      label: "Insulin Lispro U-100 Prefilled Pen (1-Unit Increments)", separate: true,
      uhcFormRx: "1652639"}],
    ["uhc-oct-complete-99b7a79d60f9be27", {...lisproProducts.lisproVial,
      label: "Insulin Lispro U-100 Injection Solution (Labeled Vial)", separate: true,
      uhcFormRx: "242120", packageQualifier: "UHC does not specify a preferred vial size."}],
    ["uhc-oct-complete-d68963fe88140f42", {...lisproProducts.juniorPen,
      label: "Insulin Lispro Junior KwikPen U-100 Prefilled Pen (0.5-Unit Increments)", separate: true,
      uhcFormRx: "1926331", option: "Insulin Lispro Junior KwikPen Listing"}],
    ["uhc-oct-complete-1a0caccc9f7c79ae", {...lisproProducts.juniorPen,
      label: "Insulin Lispro Junior KwikPen U-100 Prefilled Pen (0.5-Unit Increments)", separate: true,
      uhcFormRx: "1926332", option: "Humalog Junior KwikPen", labelUrl: "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c8ecbd7a-0e22-4fc7-a503-faa58c1b6f3f", note: uhcLisproConflict}],
    ["uhc-oct-complete-6b20c512802745b5", {...lisproProducts.mixPen,
      label: "Insulin Lispro Protamine / Lispro 75/25 U-100 Prefilled Pen", separate: true,
      uhcFormRx: "847252"}],
    ["uhc-oct-complete-4b27f95aecd5c517", {...lisproProducts.admelogVial,
      label: "Admelog (Insulin Lispro) U-100 Injection Solution (Labeled Vial)", separate: true,
      uhcFormRx: "1992169", packageQualifier: "UHC does not specify eligible vial sizes.", note: uhcLisproConflict}],
    ["uhc-oct-complete-b66766253ca867d5", {...lisproProducts.admelogPen,
      label: "Admelog SoloStar (Insulin Lispro) U-100 Prefilled Pen", separate: true,
      uhcFormRx: "1992171", note: uhcLisproConflict}],
    ["uhc-oct-complete-7fb64d26f93768e3", {...lisproProducts.humalogVialCartridge,
      label: "Humalog (Insulin Lispro) U-100 Injection — Vial or Cartridge", separate: true,
      uhcFormRx: "865098, 1652646", packageQualifier: "UHC’s printed listing does not distinguish the vial from the cartridge.", note: uhcLisproConflict}],
    ["uhc-oct-complete-bdf84a7dca46a5c9", {...lisproProducts.humalogPen,
      label: "Humalog KwikPen (Insulin Lispro) Prefilled Pen", separate: true,
      heading: "Humalog KwikPen (insulin lispro) 100 units/mL or 200 units/mL prefilled pen",
      uhcFormRx: "1652640, 1652242", paSourceConflict: true,
      labelProductExamples: [["100 units/mL", 1652640], ["200 units/mL", 1652242]],
      note: "The October electronic formulary lists both 3 mL pens. The printed listing omits concentration. Never transfer U-200 insulin from the pen into a syringe. U-200 must not be used in a pump or given intravenously. " + uhcLisproConflict}],
    ["uhc-oct-complete-bdd6e173aa27ca29", {...lisproProducts.humalogMixVial,
      label: "Humalog Mix 75/25 U-100 Injection Suspension (Labeled Vial)", separate: true,
      uhcFormRx: "752388", packageQualifier: "UHC does not specify an eligible vial size.", note: uhcLisproConflict}],
    ["uhc-oct-complete-a864ab78ab9356d7", {...lisproProducts.humalogMixPen,
      label: "Humalog Mix 75/25 KwikPen (Insulin Lispro Mix) U-100 Prefilled Pen", separate: true,
      uhcFormRx: "847254", note: uhcLisproConflict}],
    ["uhc-oct-complete-ae4326cd39db152e", {...lisproProducts.humalogFiftyPen,
      label: "Humalog Mix 50/50 KwikPen (Insulin Lispro Mix) U-100 Prefilled Pen", separate: true,
      uhcFormRx: "847213"}],
    ["banner-oct26-028", {...lisproProducts.lisproVial,
      label: "Insulin Lispro Injection Solution (Container Unspecified) (Humalog Reference)", packageQualifier: "Banner does not specify a preferred vial size."}],
    ["formulary-9980", {...lisproProducts.lisproVial,
      label: "Insulin Lispro Injection Solution (Container Unspecified) (Humalog Reference)", packageQualifier: "The statewide list does not specify a preferred vial size."}],
    ["banner-pcp-nov10-004", {...lisproProducts.juniorPen,
      label: "Insulin Lispro U-100 Prefilled Pen (Humalog Junior KwikPen, 0.5-Unit Increments)", note: "Maximum 30 units per injection."}],
    ["formulary-9981", {...lisproProducts.juniorPen,
      label: "Insulin Lispro U-100 Prefilled Pen (Humalog Junior KwikPen, 0.5-Unit Increments)", note: "Maximum 30 units per injection."}],
    ["banner-pcp-nov10-005", {...lisproProducts.lisproPen,
      label: "Insulin Lispro U-100 Prefilled Pen (Humalog KwikPen, 1-Unit Increments)", note: "Maximum 60 units per injection."}],
    ["formulary-9982", {...lisproProducts.lisproPen,
      label: "Insulin Lispro U-100 Prefilled Pen (Humalog KwikPen, 1-Unit Increments)", note: "Maximum 60 units per injection."}],
    ['uhc-oct-complete-367d1f3038b2b927', {
      separate: true, label: 'Ivermectin (Soolantra) 1% topical cream',
      note: 'The drug label specifies 10 mg/g. UHC lists the brand without a form, strength or numeric quantity limit.',
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b1d5b166-ab06-4ab5-b0c6-31126238118a'
    }],
    ["banner-full-300d0c135e0cb20c",{"separate":true,"label":"Xalkori (Crizotinib) Oral Pellets (Banner Formulary)","note":"FDA-labeled oral pellets: 20 mg, 50 mg and 150 mg. Open the shell; administer the pellets without chewing or crushing. Do not swallow the shell. Banner GL-99695 names Xalkori without a form-specific branch; exact covered strengths and packages are unverified.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=2a51b0de-47d6-455e-a94c-d2c737b04ff7"}],
    ["banner-full-98c661a1f951a1e3",{"separate":true,"label":"Xalkori (Crizotinib) Oral Capsules (Banner Formulary)","note":"FDA-labeled capsules: 200 mg and 250 mg. Swallow whole; do not split, crush or chew. Distinct from oral pellets. Banner GL-99695 names Xalkori without a form-specific branch; exact covered strengths and packages are unverified.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=2a51b0de-47d6-455e-a94c-d2c737b04ff7"}],
    ['uhc-oct-complete-1f6816a7379d66cd', {
      label: butransPatches, option: 'Generic buprenorphine patches', separate: true,
      note: 'UHC lists a quantity limit. The October formulary row omits patch strengths and the numeric limit.'
    }],
    ['uhc-oct-complete-907ff55568d6ecfb', {
      label: butransPatches, option: 'Brand Butrans patches', separate: true,
      note: 'UHC requires a failed trial, contraindication or intolerance to generic buprenorphine patches for brand Butrans. The formulary omits eligible strengths.',
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=794aa355-66de-41b8-aedf-f2c40f6bc664'
    }],
    ["banner-full-ea0529db441446f6",{"separate":true,"label":"Berinert (C1 Esterase Inhibitor) IV Powder for Solution (Banner Formulary)","note":"FDA label: intravenous treatment of acute hereditary angioedema attacks; not a routine prophylaxis product. Banner prints a brand-only preferred PA listing without package details. Banner GL-525295 acute branch: documented HAE, acute treatment, no concurrent approved acute agent, allergist/immunologist; 12 months. Product-specific age/step conditions for other drugs do not apply to Berinert. Exact covered package remains unverified.","labelUrl":"https://www.fda.gov/vaccines-blood-biologics/approved-blood-products/berinert"}],
    ["banner-full-81af49ca953b804f",{"separate":true,"label":"Cinryze / Haegarda (C1 Esterase Inhibitor) Reconstituted Injection (Banner Combined Listing)","note":"Distinct FDA-labeled prophylaxis presentations: Cinryze intravenous; Haegarda subcutaneous. Not interchangeable by route. Banner prints both brands in one brand-only PA row; individual product/package eligibility remains unverified. Banner GL-525295 prophylaxis: confirmed HAE, age 6 or older, allergist/immunologist; 12 months. Acute off-label criteria name Cinryze only, not Haegarda. The guideline lists both as preferred, but the formulary row does not specify preference.","labelUrl":"https://www.fda.gov/vaccines-blood-biologics/approved-blood-products/haegarda"}],
    ["banner-full-63b29ba46f628277",{"separate":true,"label":"Brixadi (Buprenorphine) Subcutaneous Extended-Release Prefilled Syringe (Banner Formulary)","note":"FDA label distinguishes weekly and monthly formulations; the weekly formulation is used for initiation after a tolerated test dose in patients not currently receiving buprenorphine. Do not sum weekly doses to determine a monthly dose. Banner does not specify covered schedule or strength. GL-157633 has separate initial and renewal pathways.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=5d8a8fd0-8619-422a-a664-d1d2e8970f48"}],
    ["banner-full-f280cb398b11247e",{"separate":true,"dosageForm":"solution", "label":"Fasenra Pen (Benralizumab) Subcutaneous Autoinjector","note":"FDA label: 30 mg/mL pen only. The 10 mg pediatric asthma dose requires the prefilled syringe. Exact covered strength/package remains unverified. Banner GL-642200 separates asthma, EGPA and HES initial and renewal criteria.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=da6aca1a-19ed-44a4-abb7-696c7d58b784"}],
    ["banner-full-bc2f140b456dcb21",{"separate":true,"dosageForm":"solution", "label":"Fasenra (Benralizumab) Subcutaneous Prefilled Syringe","note":"FDA label: 10 mg/0.5 mL or 30 mg/mL syringes. Exact covered strength/package remains unverified. Banner GL-642200 separates asthma, EGPA and HES initial and renewal criteria.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=da6aca1a-19ed-44a4-abb7-696c7d58b784"}],
    ["banner-full-25a305f34bbe1d14",{"separate":true,"label":"Aristada Initio (Aripiprazole Lauroxil) IM Initiation Injection","note":"FDA label: 675 mg/2.4 mL single initiation or reinitiation dose; not interchangeable with Aristada and not for repeated maintenance dosing. Banner's printed quantity limit does not establish a maintenance regimen.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b18fdfd9-31cd-4a2f-9f1c-ebc70d7a9403"}],
    ["banner-full-753b957d55158ac0",{"separate":true,"label":"Abilify Asimtufii (Aripiprazole) Extended-Release IM Suspension","note":"FDA label: 720 mg and 960 mg prefilled syringes for every-two-month dosing; distinct from monthly Abilify Maintena. Banner does not specify strength or exact eligible package.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=da4c07fd-1130-4341-bb44-63acfa4162be"}],
    ["uhc-oct-complete-8989a933ae7b4319",{"separate":true,"label":"Aimovig (Erenumab-aooe) Subcutaneous Injection","note":"FDA label: 70 mg/mL or 140 mg/mL single-dose autoinjector or prefilled syringe. UHC GL-720193 pediatric exception applies to Ajovy only, not Aimovig. Exact device, package and numeric quantity limit are unverified.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b998ed05-94b0-47fd-b28f-cddd1e128fd8"}],
    ["uhc-oct-complete-f4bec275aa84db05",{"separate":true,"label":"Ajovy (Fremanezumab-vfrm) Subcutaneous Injection","note":"FDA label: 225 mg/1.5 mL. UHC GL-720193 allows an age 6–17 and weight at least 45 kg branch for episodic migraine only; adult criteria are separate. Exact device, package and numeric quantity limit are unverified.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=98e344ea-5916-4947-b6f2-4a76ccc04b6b"}],
    ["banner-full-150d0a331d6c46df",{"separate":true,"label":"Alpha1-Proteinase Inhibitor (Prolastin-C / Glassia; IV Form Unresolved)","note":"Banner combines Prolastin-C and Glassia under one solution listing. Prolastin-C powder requires reconstitution; Prolastin-C Liquid and Glassia are supplied as solutions. Exact covered brand, formulation and package are unverified. Confirm the product before applying PA criteria.","labelUrl":"https://www.fda.gov/vaccines-blood-biologics/approved-blood-products/alpha1-proteinase-inhibitor"}],
    ["banner-full-c50d5a831e1c6a83",{"separate":true,"label":"Aralast NP (Alpha1-Proteinase Inhibitor) IV Powder for Solution","note":"FDA label: 0.5 g and 1 g single-dose vials require reconstitution. Banner prints solution; the eligible package and product-specific PA criteria remain unverified.","labelUrl":"https://www.fda.gov/media/69965/download?attachment="}],
    ["banner-full-79924464664746a2",{"separate":true,"label":"Adefovir Dipivoxil Oral Tablets (Hepsera Reference)","note":"FDA-labeled tablet strength is 10 mg; the Banner listing does not specify strength. Exact plan PA criteria remain unverified.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=08e07fae-3191-b6a3-c894-d3a8cc53923f"}],
    ["uhc-oct-complete-14411026d49668ea",{"separate":true,"label":"Acthar Gel (Repository Corticotropin Injection; Device Unspecified by UHC)","note":"FDA-labeled vial: IM or SC; SelfJect autoinjector: SC only. UHC does not specify the eligible device. Infantile spasms policy branch is vial-only.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7b48ddec-e815-45f4-9ca0-5c0daaf56f30"}],
    ["uhc-oct-complete-9b40fc8558feebd0",{"separate":true,"label":"Cortrophin Gel (Repository Corticotropin Injection; Device Unspecified by UHC)","note":"FDA-labeled vial: IM or SC; prefilled syringe: SC only. UHC does not specify the eligible device.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f27544ee-a0e2-4d84-b193-1c9efdf9e34c"}],
    ["uhc-oct-complete-e4f26f2f128c5fba",{"separate":true,"label":"Actimmune (Interferon Gamma-1b) Subcutaneous Injection","note":"FDA-labeled single-dose vial: 100 mcg/0.5 mL. The UHC formulary does not specify strength or package.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=5d0b1256-1981-4519-94f4-a4a2f98bd8a3"}],
    ["uhc-oct-complete-649c128564a43176",{"separate":true,"label":"Hadlima PushTouch (Adalimumab-bwwd) Subcutaneous Autoinjector","note":"FDA-labeled autoinjectors: 40 mg/0.4 mL and 40 mg/0.8 mL. The April 2026 UHC policy lists package-specific preferred and nonpreferred NDCs; the October PDL lists this named product as preferred. Verify exact NDC before applying preference or step requirements.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4774a951-3ce8-43b6-80b1-e6b23752aae6"}],
    ["uhc-oct-complete-ea00e4f93f96d5d5",{"separate":true,"label":"Hadlima (Adalimumab-bwwd) Subcutaneous Solution (Device Unspecified by UHC)","note":"The FDA label distinguishes prefilled syringes, PushTouch autoinjectors and an institutional-use vial. UHC prints Hadlima separately from PushTouch without specifying device. The April policy has package-specific preferences; confirm exact NDC against the current PDL.","labelUrl":"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4774a951-3ce8-43b6-80b1-e6b23752aae6"}],
    ["uhc-oct-complete-f11674b52f81253c", {"separate": true, "label": "Amlodipine / Valsartan Oral Tablets (10/160, 10/320, 5/320 mg)", "note": "The October listing leaves quantity limits unspecified for these strengths."}],
    ["uhc-oct-complete-9bf5fd9f94e8ba52", {"separate": true, "label": "Amlodipine / Valsartan Oral Tablets (5/160 mg)", "note": "UHC prints a quantity limit for this strength. Numeric limit unverified."}],
    ["uhc-oct-complete-2eb0fcc9c7447507", {"separate": true, "label": "Repatha 140 mg/mL Subcutaneous Autoinjector", "note": "UHC lists NDCs starting with 72511 as preferred with PA. Exact eligible packages are unverified."}],
    ["uhc-oct-complete-bf8defb2317fedf5", {"separate": true, "label": "Praluent (Alirocumab) Subcutaneous Prefilled Pen", "note": "FDA-labeled strengths are 75 and 150 mg/mL. UHC does not identify eligible strengths."}],
    ["uhc-oct-complete-f89f65a34a3d7b1a", {"separate": true, "label": "Nexletol (Bempedoic Acid) Oral Tablet", "note": "FDA-labeled strength 180 mg. UHC lists the brand without a strength."}],
    ["uhc-oct-complete-0dba4b21951729c0", {"separate": true, "label": "Nexlizet (Bempedoic Acid / Ezetimibe) Oral Tablet", "note": "FDA-labeled strength 180 mg/10 mg. UHC lists the brand without a strength."}],
    ["uhc-oct-complete-add3a1f5176903ed", {"separate": true, "label": "Sodium Phenylbutyrate Oral Powder", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-3819c4b013640e1d", {"separate": true, "label": "Sodium Phenylbutyrate Oral Tablets", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-da625a05b2d95ed6", {"separate": true, "label": "Phyrago 100 mg Oral Tablets", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-58e7c253ac91773a", {"separate": true, "label": "Sprycel (Dasatinib Tablets)", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-f9bd87e671c0b1b4", {"separate": true, "label": "Promacta Oral Suspension Powder Packets", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-66aa6db51c8641f9", {"separate": true, "label": "Promacta Oral Tablets", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-73bdfcbd8ed83459", {"separate": true, "label": "Pred Forte Ophthalmic Suspension", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-e8904add38dcca50", {"separate": true, "label": "Prednisolone Acetate P-F (Exact Product Unverified)", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-fdb09a3969cbeac7", {"separate": true, "label": "Bosentan Oral Tablets", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-369ff35242ddaf80", {"separate": true, "label": "Bosentan Tablets for Oral Suspension", "note": "See the exact UHC listing for product-specific restrictions."}],
    ["uhc-oct-complete-cbe335d8e93b76c3", {"conflict": true, "note": "UHC lists preferred | non preferred (tiers 1 | 1). Printed flags by listing: *, QL, AL | PA, *, QL, AL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-4de408fad3af28c5", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 2 | 2). Printed flags by listing: (blank) | QL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-68d7ca7f971d686d", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 2 | 2). Printed flags by listing: (blank) | QL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-54d557b57f0fd561", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 1 | 2). Printed flags by listing: QL | QL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-9a605f6f7577f349", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 1 | 2). Printed flags by listing: QL | QL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-8e6412598dc3cc82", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 2 | 2). Printed flags by listing: DX2RX, ST, *, QL, AL | PA, ST, *, QL, AL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-86a272013762dd71", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 2 | 2). Printed flags by listing: DX2RX, ST, *, QL, AL | PA, ST, *, QL, AL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-4a432871483f8345", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 2 | 2). Printed flags by listing: DX2RX, ST, *, QL, AL | PA, ST, *, QL, AL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-e60cf4ef12c45d4c", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 2 | 2). Printed flags by listing: DX2RX, ST, *, QL, AL | PA, ST, *, QL, AL. Exact package applicability is unverified."}],
    ["uhc-oct-complete-daf39dbb5aa3d6ba", {"conflict": true, "note": "UHC lists preferred | preferred (tiers 1 | 2). Printed flags by listing: QL | QL. Exact package applicability is unverified."}],
    ["banner-full-cbfa838935217cc6", {"label": "Clindamycin Phosphate / Benzoyl Peroxide (Form Unspecified)", "note": "Banner prints “refrigerate” on the continuation of its October listing, page 24. Eligible concentration is unspecified."}],
    ['uhc-oct-complete-7643ae6c318710a6', {
      label: 'Omnipod 5 Dexcom insulin pump intro kit', separate: true,
      note: 'The formulary lists an intro kit. The higher-quantity exception is specific to pods.'
    }],
    ['uhc-oct-complete-fcc058d760894f93', {
      label: 'Omnipod 5 Dexcom insulin pump pods', separate: true
    }],
    ['uhc-oct-complete-4d48c8bd9a3822ca', {
      label: 'Nurtec ODT (rimegepant) orally disintegrating tablet', note: 'Labeled strength: 75 mg.',
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=9ef08e09-1098-35cc-e053-2a95a90a3e1d'
    }],
    ...[
      ['uhc-oct-complete-ebc651f39c6b05eb', '1.5', 3, 2749695],
      ['uhc-oct-complete-8148b6eef83b111c', '2', 4, 2749698],
    ].map(([id, dose, tablets, rxcui]) => [id, {
      label: `Eliquis (apixaban) ${dose} mg packet — 0.5 mg tablets for oral suspension`,
      dosageForm: 'tablets for oral suspension', separate: true,
      note: `Each packet contains ${tablets} tablets of 0.5 mg each. UHC lists a quantity limit without an amount or interval.`,
      identityRxcui: rxcui, uhcFormRx: String(rxcui),
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e9481622-7cc6-418a-acb6-c5450daae9b0'
    }]),
    ['uhc-oct-complete-a7836b3702968dcc', {
      label: 'Pradaxa (dabigatran etexilate) oral pellet packets',
      note: 'Labeled packet strengths: 20, 30, 40, 50, 110 and 150 mg. UHC lists the packet without specifying eligible strengths.',
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=9ac0a64a-8666-45f7-9d4f-40fd894f7e6d'
    }],
    ['uhc-oct-complete-8b74d0de978fabcb', {
      label: 'Eliquis DVT/PE 30-day starter pack — 5 mg oral tablets', dosageForm: 'oral tablets', separate: true,
      note: 'The labeled starter pack contains 74 tablets. UHC lists a quantity limit without an amount or interval.',
      identityRxcui: 1992428, uhcFormRx: '1992428',
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e9481622-7cc6-418a-acb6-c5450daae9b0'
    }],
    ['uhc-oct-complete-14a0d201b338bbcc', {
      label: 'Xarelto Starter Pack (30-day) — 15 mg and 20 mg oral tablets', dosageForm: 'oral tablets', separate: true,
      note: 'The labeled starter pack contains 42 tablets of 15 mg and 9 tablets of 20 mg. UHC lists a quantity limit without an amount or interval.',
      identityRxcui: 1549683, uhcFormRx: '1549683',
      labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=10db92f9-2300-4a80-836b-673e1ae91610'
    }],
    ['uhc-oct-complete-d6b49b27961f969c', {label: 'Vascepa (Icosapent Ethyl) Oral Capsules', generalPa: true}],
    ['uhc-oct-complete-552f551a574d06dd', {label: 'Crestor (Rosuvastatin) Oral Tablets', generalPa: true}],
    ['uhc-oct-complete-49482f69ae796c31', {label: 'Zocor (Simvastatin) Oral Tablets', generalPa: true}],
    ['uhc-oct-complete-6520d7a7c776b0eb', {label: 'Livalo (Pitavastatin Calcium) Oral Tablets', generalPa: true}],
    ['uhc-oct-complete-4001483fb5296830', {label: 'Zypitamag (Pitavastatin Magnesium) Oral Tablets', generalPa: true}],
    ['uhc-oct-complete-e1d7e6930656b4b2', {label: 'Vytorin (Ezetimibe/Simvastatin) Oral Tablets', generalPa: true}],
    ['uhc-oct-complete-6152d1a90840a215', {label: rosuvastatinTablets, note: genericStatinNote}],
    ['uhc-oct-complete-8dcccfa13dad2bf9', {label: simvastatinTablets, note: genericStatinNote}],
    ['banner-source-review-12-2-48', {label: rosuvastatinTablets, scope: 'Banner formulary · October 1, 2026', note: 'Banner quantity limit: 30 per 30 days.'}],
    ['banner-pcp-nov10-046', {label: simvastatinTablets, scope: 'Banner formulary · October 1, 2026', note: 'Banner quantity limit: 30 per 30 days.'}],
    ['formulary-10079', {label: rosuvastatinTablets, note: 'Statewide quantity limit: 30 per 30 days.'}],
    ['formulary-10080', {label: simvastatinTablets, note: 'Statewide quantity limit: 30 per 30 days.'}],
    ...[...bannerEpiPenIds].map(id => [id, bannerEpiPenDisplay]),
    ['formulary-11033', {label: epiPenAutoInjector, note: 'The statewide listing applies to its named authorized generic. Exact selected-plan package eligibility is unverified.'}],
    ['uhc-oct-complete-55381c317387d023', {
      label: 'AUVI-Q (epinephrine) single-dose prefilled autoinjector', dosageForm: 'injection solution', generalPa: true,
      deviceSourceUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=6180fb40-7fca-4602-b3da-ce62b8cd2470',
      note: 'Labeled doses are 0.1 mg/0.1 mL, 0.15 mg/0.15 mL and 0.3 mg/0.3 mL. UHC does not specify eligible strengths or packages.'
    }],
    ['uhc-oct-complete-feedc25102cbbdb1', {label: 'Epinephrine 0.15 mg/0.3 mL Autoinjector (EpiPen Jr Reference)'}],
    ['uhc-oct-complete-e1546021b5a54dde', {label: 'Epinephrine 0.3 mg/0.3 mL Autoinjector (AUVI-Q Reference)'}],
    ['uhc-oct-complete-347f997a8ebe87f9', {label: 'Amoxicillin/Clavulanate Oral Suspension (Augmentin ES-600 Reference)', note: 'Label reference strength: 600 mg/42.9 mg per 5 mL. UHC does not identify eligible packages.', labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=59979859-8c9b-4173-a5e3-2e6312fd9d79'}],
    ['uhc-oct-complete-9b7855078f1fa6e3', {label: 'Augmentin (Dosage Form and Strength Unspecified by UHC)'}],
    ['banner-full-30e8484da347ad72', {label: augmentinSuspension, scope: 'Banner formulary · October 1, 2026', note: 'The formulary does not specify a strength, preference, PA, step therapy or quantity limit.'}],
    ['formulary-10929', {label: augmentinSuspension, note: 'The statewide list does not specify strength or restrictions for this listing.'}],
    ['uhc-oct-complete-836fcbdd50338512', {label: 'Symbicort Metered-Dose Inhalation Aerosol', generalPa: true}],
    ['uhc-oct-complete-d286297ad03ac6d9', {label: 'Budesonide/Formoterol Inhalation Aerosol 80/4.5 mcg per actuation', note: symbicortGenericNote}],
    ['uhc-oct-complete-be916cf5ebe9501f', {label: 'Budesonide/Formoterol Inhalation Aerosol 160/4.5 mcg per actuation', note: symbicortGenericNote}],
    ['uhc-oct-complete-4295ce610108f0df', {label: tiotropiumCapsules, option: 'Brand Spiriva HandiHaler', note: tiotropiumContinuation, explicitPa: true, generalPa: true}],
    ['uhc-oct-complete-818668349b64ef42', {label: tiotropiumCapsules, option: 'Generic tiotropium inhalation capsules', note: tiotropiumContinuation}],
    ['uhc-oct-complete-9f26ef4f16fcfe13', {label: spirivaSpray, labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7b656b14-fcaa-2741-f6f0-e0be48971c02'}],
    ['banner-pcp-nov10-037', {label: 'Budesonide/Formoterol Inhalation Aerosol (Symbicort)', note: 'Banner lists the authorized generic only as preferred.'}],
    ['banner-pcp-nov10-024', {label: tiotropiumCapsules, scope: 'Banner formulary · October 1, 2026'}],
    ['banner-pcp-nov10-023', {label: spirivaSpray}],
    ['formulary-9798', {label: spirivaSpray}],
    ['formulary-9799', {label: tiotropiumCapsules}],
    ['formulary-9819', {label: 'Budesonide/Formoterol Inhalation Aerosol (Symbicort)'}],
    ['ach-notice-13839', {label: 'Tiotropium Inhalation (Dosage Form Unspecified)', scope: 'Arizona Complete Health notice · October 1, 2026'}],
    ['ach-notice-13840', {label: spirivaSpray, scope: 'Arizona Complete Health notice · October 1, 2026'}],
    ['banner-pcp-nov10-031', {label: 'Fluticasone Propionate HFA Inhalation Aerosol', relatedBannerIcs: true}],
    ['banner-full-8cf0b9aec0446880', {label: fluticasoneUnspecified, relatedBannerIcs: true}],
    ['formulary-9808', {label: 'Fluticasone Propionate HFA Inhalation Aerosol'}],
    ['formulary-9809', {label: fluticasoneUnspecified}]
  ]);

  const baselineLisproPackages = new Map([
    ['ach-json-242120', lisproProducts.lisproVial],
    ['ach-json-1652639', lisproProducts.lisproPen],
    ['ach-json-1926331', lisproProducts.juniorPen],
    ['ach-json-847213', lisproProducts.humalogFiftyPen],
    ['ach-json-847252', lisproProducts.mixPen]
  ]);

  const statewideCoverageSource = {
    label: 'AHCCCS Statewide',
    description: 'AHCCCS statewide reference. Exact-plan coverage and restrictions are unverified.'
  };

  function coverageSource(record) {
    if (record.isStatewideReference || record.auditScope === 'statewide_reference') return statewideCoverageSource;
    return null;
  }

  const humulin7030Label = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e245e0c5-b2d6-418b-baa4-1c3324292885';
  const premixDeviceUnknown = 'The formulary lists the brand without a device or package.';
  const bannerHumanPremix = new Map([
    ['HUMULIN 70/30', {
      label: 'Humulin 70/30 (human NPH/regular insulin) 100 units/mL injectable suspension',
      note: premixDeviceUnknown, labelUrl: humulin7030Label
    }],
    ['HUMULIN 70/30 KWIKPEN', {
      label: 'Humulin 70/30 KwikPen (human NPH/regular insulin) 100 units/mL prefilled pen',
      note: '3 mL single-patient-use pen with 1-unit dose increments.', labelUrl: humulin7030Label,
      identityRxcui: 847189
    }],
    ['NOVOLIN 70/30', {
      label: 'Novolin 70/30 (human NPH/regular insulin) 100 units/mL injectable suspension',
      note: premixDeviceUnknown, labelUrl: 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=508a2763-3cb7-4be5-9e53-544e84cd9b1f'
    }]
  ]);

  function reviewedCardPresentation(record) {
    if (record.id === 'banner-ufc:statewide:formulary-9598' && record.brand === 'CATAPRES') return {dosageForm: 'oral tablet'};
    // Pair each Banner October brand row only with its matching statewide November row.
    if (record.planId === 'banner-ufc' && record.name === 'INSULIN NPH ISOPHANE & REG (HUMAN) SUSPENSION'
        && record.sourceEffective === (record.isStatewideReference ? '2026-11-01' : '2026-10-01')
        && bannerHumanPremix.has(record.brand)) return bannerHumanPremix.get(record.brand);
    if (uhcGvokePresentations.has(record.id)) return {dosageForm: 'solution', deviceSourceUrl: gvokeLabelUrl};
    const id = record.isStatewideReference ? record.id.split(':').at(-1) : record.id;
    const reviewed = record.reviewedPresentation || reviewedCardPresentations.get(id);
    if (reviewed) return reviewed;
    const product = record.baselineSource && baselineLisproPackages.get(record.id);
    if (product) return {...product, separate: true,
      packageQualifier: product === lisproProducts.lisproVial ? 'The plan does not specify a preferred vial size.' : ''};
    return null;
  }

  function selectedPlanRecords() {
    return state.data.medications.filter(record => record.planId === state.planId && record.recordType === 'formulary');
  }

  function planMedicationGroups() {
    const key = state.planId + ':' + state.data.medications.length;
    if (groupCache.has(key)) return groupCache.get(key);
    const planGroups = medicationGroups(selectedPlanRecords());
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
      const packId = group.records.length === 1 && group.records[0].verifiedStatewidePackId;
      if (packId) {
        const pack = sharedGroups.find(g => g.statewideRecord.id === state.planId + ':statewide:' + packId);
        if (pack) {
          pack.records.push(...group.records);
          pack.search += ' ' + group.search;
        } else supplements.push(group);
        continue;
      }
      if (group.records.some(record => uhcReviewedProductGroups.has(record.id) || reviewedCardPresentation(record)?.separate)) {
        supplements.push(group);
        continue;
      }
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
    if (state.planId === 'banner-ufc') {
      for (const group of result) {
        const insulin = group.records.find(r => r.reviewedBannerBranches?.policyId === 'banner-policy-12-969');
        if (insulin) {
          group.label = insulin.reviewedPresentation.heading;
          group.search += ' ' + group.label.toLowerCase();
        }
      }
    }
    if (state.planId === 'uhc-community-az') {
      const packets = result.find(group => group.records.some(record => record.id === 'uhc-oct-complete-b91029349d6055f8'));
      if (packets) {
        packets.label = 'Pantoprazole Delayed-Release Granules for Oral Suspension (Protonix Packets)';
        packets.search += ' ' + packets.label;
      }
    }
    if (state.planId === 'uhc-community-az') {
      const linzess = result.find(group => group.records.some(record => record.id === uhcLinzessId));
      const statewideIndex = result.findIndex(group => group.statewideRecord?.id.endsWith(':formulary-10735'));
      if (linzess && statewideIndex >= 0) {
        const [statewide] = result.splice(statewideIndex, 1);
        linzess.records.push(statewide.statewideRecord);
        linzess.search += ' ' + statewide.search;
      }
    }
    groupCache.set(key, result);
    return result;
  }

  function uniqueMedicationNames() {
    return [...new Set([...planMedicationGroups().map(group => dosageFormHeading(group)), tirosintSolutionLabel])]
      .sort((a, b) => a.localeCompare(b));
  }

  // A presentation filter, independent of the payer's therapeutic category.
  // Classify only explicit inhaler/device/form names; ambiguous solutions stay out.
  function isInhaler(record) {
    if (record.recordType !== 'formulary') return false;
    const name = normalize([record.name, record.brand, record.standardName, record.standardDisplayName].filter(Boolean).join(' '));
    if (/\b(?:nebuliz\w*|nebulis\w*|syrup|nasal|spacer|chamber|mask|adapter|accessor\w*)\b|oral (?:solution|tablet|capsule)|inhaler aids/.test(name)) return false;
    return /\b(?:inhaler|hfa|respimat|ellipta|diskus|diskhaler|flexhaler|redihaler|respiclick|digihaler|handihaler|twisthaler|pressair|aerosphere|turbuhaler|neohaler|podhaler)\b/.test(name)
      || /inhalation (?:spray|aerosol|powder)|(?:powder|aerosol|aepb|aerb|aers|capsules?)[^.;]*\binhalation\b|inhalable powder/.test(name);
  }

  function matchesCategory(record, category) {
    return !category || (normalize(category) === 'inhalers' ? isInhaler(record) : normalize(record.category).includes(normalize(category)));
  }

  function categoryOptions() {
    return [...new Set([...recordsForPlan().map((record) => record.category).filter(Boolean), 'Inhalers'])]
      .sort((a, b) => a.localeCompare(b));
  }

  function subcategoryLabel(value) {
    const clean = String(value || '').replace(/\+[A-Z]{1,3}\d{3,}\b/gi, '')
      .replace(/\*+\s*$/, '').replace(/\banti-\s+/gi, 'anti-').replace(/\s+/g, ' ').trim();
    const acronyms = new Map('ADHD HIV AIDS HCV HBV COPD CNS GI GU ENT OTC IV IM SC SQ HFA DPI NSAID SSRI SNRI MAOI ACE ARB PDE3 PDE4 PDE5 GLP-1 SGLT2 DPP-4 TNF IL-6 CAM GABA NMDA COMT DOPA CGRP CDK4 CDK6 JAK VEGF HMG DNA RNA'.split(' ').map(word => [word.toLowerCase(), word]));
    acronyms.set('nsaids', 'NSAIDs');
    return titleCase(clean).replace(/[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/g, word => acronyms.get(word.toLowerCase()) || word);
  }

  function matchesSubcategory(value, query) {
    return normalize(subcategoryLabel(value)).includes(normalize(subcategoryLabel(query)));
  }

  function subcategoryOptions() {
    const category = normalize(state.category);
    return [...new Set(recordsForPlan()
      .filter((record) => matchesCategory(record, category))
      .map((record) => subcategoryLabel(record.subcategory))
      .filter(Boolean))]
      .sort((a, b) => a.localeCompare(b));
  }

  function displayPlanName(plan) { return plan ? 'AHCCCS: ' + plan.name.replace(/^AHCCCS:\s*/i, '') : ''; }

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
      .map(displayPlanName);
    if (!state.planId) return [];
    if (name === 'medication') return uniqueMedicationNames();
    if (name === 'category') return categoryOptions();
    return subcategoryOptions();
  }

  function populateControls() {
    el.planInput.value = displayPlanName(state.data.plans.find((p) => p.id === state.planId));
  }

  function updateSubcategoryOptions() {
    if (!el.subcategoryOptions.hidden) renderComboboxOptions('subcategory', comboState.subcategory.showAll);
  }

  function resolveExact(values, input) {
    const target = normalize(input);
    return values.find((value) => normalize(value) === target) || '';
  }

  function resolvePlan(input) {
    const target = normalize(input).replace(/^ahcccs:\s*/, '');
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
    const medicationSearch = new Map();
    if (name === 'medication') for (const group of planMedicationGroups()) {
      const heading = dosageFormHeading(group);
      const compact = compactPresentation(group);
      const aliases = normalize([group.search, heading, compact?.packageLine, compact?.searchAlias].join(' '));
      medicationSearch.set(heading, (medicationSearch.get(heading) || '') + ' ' + aliases);
    }
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
      state.selectedMedicationKey = null;
    } else if (name === 'medication') {
      state.term = value;
      state.selectedMedicationKey = planMedicationGroups().find(group => dosageFormHeading(group) === value)?.key || null;
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
        state.planId = plan?.id || null;
        state.selectedMedicationKey = null;
      } else if (name === 'medication') {
        state.term = input.value;
        state.selectedMedicationKey = null;
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
    if (record.planId === 'banner-ufc' && bannerInsulinConflicts.has(record.id)
        && ['listed', 'preferred'].includes(state.coverage)) return false;
    if (state.coverage === 'listed') return record.recordType === 'formulary' && record.coverage !== 'explicit_not_covered';
    if (state.coverage === 'preferred') return record.preferred === 'preferred';
    if (state.coverage === 'non_preferred') return record.preferred === 'non_preferred';
    const pa = reviewedCardPresentation(record)?.explicitPa ? 'required' : record.pa;
    if (state.coverage === 'pa_required') return pa === 'required';
    if (state.coverage === 'pa_conditional') return pa === 'conditional';
    return record.coverage === state.coverage;
  }

  function filteredRecords() {
    const category = normalize(state.category);
    const subcategory = normalize(state.subcategory);
    const selectedGroup = state.selectedMedicationKey
      ? planMedicationGroups().find(g => g.key === state.selectedMedicationKey) : null;
    // Exact-plan, statewide and historical listings can share one prescribing heading.
    const selectedHeading = selectedGroup && compactPresentation(selectedGroup)?.heading;
    const terms = normalize(state.term).split(/\s+/).filter(Boolean);
    return recordsForPlan()
      .filter((record) => matchesCategory(record, category))
      .filter((record) => !subcategory || matchesSubcategory(record.subcategory, subcategory))
      .filter(matchesCoverage)
      .filter((record) => {
        const presentation = reviewedCardPresentation(record);
        if (selectedHeading && selectedHeading === state.term) return presentation?.heading === selectedHeading;
        if (selectedGroup) return selectedGroup.records.some(r => r.id === record.id);
        const haystack = normalize([
          presentation?.heading, presentation?.packageLine, presentation?.searchAlias, record.displayName || record.name, expandFormWords(record.name), record.brand, record.standardName, record.rxTermsForm?.form, presentation?.dosageForm, record.searchAliases?.join(' '), presentation?.label
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
      baseline_plus_updates: 'Formulary and updates',
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

  function statusChips(record, showCoverage = true) {
    const chips = [];
    // Description-correction provenance remains in the source records.
    if (record.planId === 'uhc-community-az' && record.sourceEffective === '2026-07-01') {
      chips.push(['Historical July 2026 · current status unverified', 'negative']);
    }
    if (record.suppressCoverageAndPaBadges) return '';
    if (record.recordType === 'policy') chips.push([record.guide ? 'PA guide · clinical review pending' : 'Policy criteria', 'warning']);
    else if (record.recordType === 'policy_index') chips.push(['Policy source indexed', 'warning']);
    else if (showCoverage && record.coverage !== 'explicit_not_covered') {
      const listingLabel = record.isStatewideReference || record.planId === 'ahcccs-statewide' ? 'Covered'
        : record.planId === 'uhc-community-az' && record.sourceEffective === '2026-07-01' ? 'On archived formulary' : record.coverage === 'listed' ? 'Covered' : 'On formulary';
      const verifiedCoverage = hasVerifiedMandatedCoverage(record);
      chips.push([verifiedCoverage ? 'Covered' : (/exact.plan preference notice/i.test(record.listingLabel || '') ? 'On formulary' : record.listingLabel) || listingLabel, verifiedCoverage || !record.listingLabel ? 'positive' : 'neutral', 'Appears in this source. Listed restrictions still apply.']);
    }
    if (record.guide?.ambiguity) chips.push(['Source clarification needed', 'negative']);
    if (showCoverage && record.coverage === 'explicit_not_covered') chips.push(['Explicitly not covered', 'negative']);
    if (record.coverageCaveat) chips.push([record.coverageCaveat, 'warning']);
    if (record.preferred === 'preferred') chips.push(['Preferred', 'positive']);
    if (record.preferred === 'non_preferred') chips.push(['Nonpreferred', 'warning']);
    if (/\bbrand\s*only\b/i.test(record.brandGenericNotes || record.notes || '')) chips.push(['Brand only', 'warning']);
    if (/\bauthorized\s+generic\s+only\b/i.test([record.brandGenericNotes, record.notes].join(' '))) chips.push(['Authorized generic only', 'warning']);
    else if (/\bgeneric(?:\s+formulations)?\s+only\b/i.test([record.brandGenericNotes, record.notes].join(' '))) chips.push(['Generic only', 'warning']);
    if (record.tier) chips.push([`Tier ${record.tier}`, 'neutral']);
    if (uhcReviewedPaConflicts.has(record.id) || reviewedCardPresentation(record)?.paSourceConflict) chips.push(['PA listings conflict', 'warning']);
    else if (record.pa === 'required') chips.push(['PA required', 'warning']);
    else if (record.pa === 'conditional') chips.push(['Conditional PA', 'warning']);
    if (record.step === 'specified') chips.push(['Step therapy', 'warning']);
    if (record.quantityLimited || record.qlAmount || record.qlDays) chips.push([bannerAdhdLimit(record) || 'Quantity limit', 'warning']);
    if (record.ageLimited) chips.push(['Age limit', 'warning']);
    if (record.specialty) chips.push(['Specialty', 'warning']);
    if (record.diagnosisRequired) chips.push(['Diagnosis required', 'warning']);
    return chips.filter(([text]) => !/conflicting source listings\s*=\s*conservative status|PA not addressed by notice|exact.plan preference notice/i.test(text)).map(([text, kind, help]) => `<span class="chip ${kind}"${help ? ` title="${escapeHtml(help)}"` : ''}>${escapeHtml(text)}</span>`).join('');
  }

  function baselineBadgeRows(record) {
    const origins = record.benefitSources;
    const sources = [
      ['presumed_2022', ''],
      ['selected_plan', 'Plan notice'],
      ['statewide_reference', statewideCoverageSource.label]
    ];
    const lines = sources.map(([scope, label]) => {
      const belongs = field => origins[field] === scope;
      const badges = statusChips({
        recordType: 'formulary', coverage: record.coverage,
        preferred: belongs('preferred') && record.preferred,
        pa: belongs('pa') && record.pa, step: belongs('step') && record.step,
        quantityLimited: belongs('quantityLimited') && record.quantityLimited,
        ageLimited: belongs('ageLimited') && record.ageLimited
      }, belongs('coverage'));
      const preference = belongs('coverage') && record.coverage === 'listed' && record.preferred === 'not_specified'
        && !record.preferenceUncertaintyReason ? '<span class="chip neutral">Preference not specified</span>' : '';
      const sourceChip = label ? `<span class="chip neutral">${escapeHtml(label)}</span>` : '';
      return badges ? `<div class="chips" aria-label="${escapeHtml(label || 'Plan')} coverage attributes">${sourceChip}${badges}${preference}</div>` : '';
    }).join('');
    const holds = [...new Set([record.sourceConflict, record.paUncertaintyReason].filter(Boolean))];
    return lines + holds.map(reason => `<p class="pa-condition">${escapeHtml(reason)}</p>`).join('');
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

  const bannerRepeatPositions = new Map([
    ["banner-full-fa62279e75a1c387", ["BAN-P1-T1-R15", "BAN-P13-T2-R10"]],
    ["banner-full-f31c38d5659b78f6", ["BAN-P3-T2-R10", "BAN-P11-T2-R30"]],
    ["banner-full-9e2ca54467b1006f", ["BAN-P7-T2-R9", "BAN-P7-T2-R10"]],
    ["banner-full-40c3115ef1ad1803", ["BAN-P8-T2-R13", "BAN-P8-T2-R14"]],
    ["banner-full-852b41b52868cf72", ["BAN-P14-T2-R57", "BAN-P14-T2-R58"]],
    ["banner-full-f22f49c3477e4037", ["BAN-P33-T1-R4", "BAN-P33-T1-R49"]],
    ["banner-full-ff1d139c33245527", ["BAN-P33-T1-R5", "BAN-P33-T1-R50"]],
    ["banner-full-5052f7a967c11f83", ["BAN-P33-T1-R6", "BAN-P33-T1-R51"]],
    ["banner-full-80442cb908e5bcba", ["BAN-P33-T1-R7", "BAN-P33-T1-R52"]],
    ["banner-full-65339b73f8166d78", ["BAN-P33-T1-R9", "BAN-P33-T1-R54"]],
    ["banner-full-c3ae43b283a26835", ["BAN-P33-T1-R11", "BAN-P33-T2-R3"]],
    ["banner-full-ac4a6de41fe9232c", ["BAN-P33-T1-R12", "BAN-P33-T2-R4"]],
    ["banner-full-40d2ce2b10232236", ["BAN-P33-T1-R13", "BAN-P33-T2-R5"]],
    ["banner-full-8ce1a180298156cf", ["BAN-P33-T1-R14", "BAN-P33-T2-R6"]],
    ["banner-full-c76993e33965759b", ["BAN-P33-T1-R15", "BAN-P33-T2-R7"]],
    ["banner-full-b3ceeabcf5ba0a55", ["BAN-P33-T1-R16", "BAN-P33-T2-R8"]],
    ["banner-full-133d83c6be5e530a", ["BAN-P33-T1-R30", "BAN-P34-T1-R4"]],
    ["banner-full-c5f5752e2b231544", ["BAN-P33-T1-R31", "BAN-P34-T1-R5"]],
    ["banner-full-7fd6bb53bef2f899", ["BAN-P33-T1-R33", "BAN-P34-T1-R7"]],
    ["banner-full-709064318758552a", ["BAN-P33-T1-R34", "BAN-P34-T1-R8"]],
    ["banner-full-74245884da8150ee", ["BAN-P33-T1-R35", "BAN-P34-T1-R9"]],
    ["banner-full-d87ee3b1f4f054ac", ["BAN-P33-T1-R36", "BAN-P34-T1-R10"]],
    ["banner-full-64478e6c4d093c63", ["BAN-P33-T1-R37", "BAN-P34-T1-R11"]],
    ["banner-full-8181f169d42f5dbb", ["BAN-P33-T1-R38", "BAN-P34-T1-R12"]],
    ["banner-full-338a2c1a943dcb71", ["BAN-P33-T1-R39", "BAN-P34-T1-R13"]],
    ["banner-full-e9d3201769338c6c", ["BAN-P33-T1-R41", "BAN-P34-T1-R15"]],
    ["banner-full-3f55e627c5259328", ["BAN-P33-T1-R42", "BAN-P34-T1-R16"]],
    ["banner-full-ae17a433c5207130", ["BAN-P33-T1-R43", "BAN-P34-T1-R17"]],
    ["banner-full-345351bab03d7259", ["BAN-P33-T1-R44", "BAN-P34-T1-R18"]],
    ["banner-full-5871af4cc5e1eb9b", ["BAN-P33-T1-R45", "BAN-P34-T1-R19"]]
  ]);

  function recordDetails(record) {
    const details = [];
    const presentation = reviewedCardPresentation(record);
    const scope = coverageSource(record);
    if (scope) details.push(`<p>${escapeHtml(scope.description)}</p>`);
    if (achSmartRecords.has(record.id)) {
      details.push(`<p><a class="source-link" href="${achSmartNoticeUrl}" target="_blank" rel="noopener">Arizona Complete Health formulary notice ↗</a> · effective October 1, 2026 · SMART asthma therapy paragraph</p>`);
    }
    if (presentation?.identityRxcui) {
      const id = Number(presentation.identityRxcui);
      details.push(`<p><strong>Prescribing presentation:</strong> <a href="https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&amp;searchTerm=${id}" target="_blank" rel="noopener">RxCUI ${id}</a> · <a href="${escapeHtml(presentation.labelUrl)}" target="_blank" rel="noopener">DailyMed drug label ↗</a></p>`);
    }
    if (presentation?.labelProductExamples) {
      const links = presentation.labelProductExamples.map(([description, id]) =>
        `<a href="https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&amp;searchTerm=${Number(id)}" target="_blank" rel="noopener">${escapeHtml(description)} · RxCUI ${Number(id)}</a>`);
      details.push(`<p><strong>Labeled presentations:</strong> ${links.join(' · ')}. The formulary does not identify the covered package. <a href="${escapeHtml(presentation.labelUrl)}" target="_blank" rel="noopener">DailyMed drug label ↗</a></p>`);
    }
    if (presentation?.electronicRow) details.push(`<p><a href="https://legacy.providerlookuponline.com/mrf/optumrx/drugs/2877216/JSON_Drugs_UHCCPAZ.json" target="_blank" rel="noopener">UHC electronic formulary ↗</a> · UCSAZQ3, October 20, 2026 file · row ${Number(presentation.electronicRow)} · RxCUI ${Number(presentation.identityRxcui)}</p>`);
    const formRx = presentation?.uhcFormRx;
    if (formRx) details.push(`<p><a href="https://legacy.providerlookuponline.com/mrf/optumrx/drugs/2877216/JSON_Drugs_UHCCPAZ.json" target="_blank" rel="noopener">UHC electronic formulary</a> · UCSAZQ3, 2026 · RxCUI ${escapeHtml(formRx)} · file dated October 20, 2026.</p>`);
    for (const position of bannerRepeatPositions.get(record.id) || []) {
      const [, page, table, row] = position.match(/BAN-P(\d+)-T(\d+)-R(\d+)/);
      details.push(`<a href="${escapeHtml(record.sourceUrl)}#page=${page}" target="_blank" rel="noopener">Banner page ${page}, table ${table}, row ${row}</a>`);
    }
    if (record.rxTermsForm) {
      const {form, exampleRxcui} = record.rxTermsForm;
      details.push(`<p><strong>Dosage form:</strong> ${escapeHtml(form)} · <a href="https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&amp;searchTerm=${Number(exampleRxcui)}" target="_blank" rel="noopener">RxNorm product example ↗</a> (RxTerms, November 2026). This identifies the form only. See the payer row for listed strengths and restrictions.</p>`);
    }
    if (record.standardName) details.push(`<p><strong>Standardized name:</strong> ${escapeHtml(record.standardName)}<br>${escapeHtml(record.standardNameType)} · RxCUI ${escapeHtml(record.rxnormId)} · NLM release ${escapeHtml(record.standardNameProvenance.release)} · ${escapeHtml(record.standardNameProvenance.sourceFile)}</p>`);
    if (record.baselineSource) {
      const baseline = record.baselineSource;
      details.push(`<p><strong>2022 plan source:</strong> <a href="${escapeHtml(baseline.url)}" target="_blank" rel="noopener">Arizona Complete Health formulary</a> · row ${Number(baseline.row)} · RxNorm ${escapeHtml(record.rxnormId)}.</p>`);
      if (record.paUncertaintyReason) details.push(`<p>${escapeHtml(record.paUncertaintyReason)}</p>`);
    }
    if (record.sourceUpdates?.length) details.push('<p><strong>Later applicable sources:</strong></p>' + record.sourceUpdates.map(item =>
      `<p>${item.scope === 'statewide_reference' ? 'AHCCCS Statewide' : 'Plan notice'} · <a href="${escapeHtml(sourceHref(item))}" target="_blank" rel="noopener">${escapeHtml(item.name)} · ${escapeHtml(item.sourceEffective)}</a>${item.paText ? ' · ' + escapeHtml(item.paText) : ''}</p>`).join(''));
    if (record.achProviderRule) details.push(`<p><strong>Plan PA rule:</strong> ${escapeHtml(record.achProviderRule.text)} <a href="${escapeHtml(record.achProviderRule.sourceUrl)}" target="_blank" rel="noopener">Provider pharmacy page ↗</a> · accessed ${escapeHtml(record.achProviderRule.observedDate)}.</p>`);
    if (record.quantityLimited && !record.qlAmount && !record.qlDays) details.push('<p><strong>Quantity limit:</strong> The source lists a limit without specifying an amount or interval.</p>');
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
      // The injectable grid uses HCPCS billing units, not prescribing doses.
      if ((record.id === 'banner-oct2026-j1306' || presentation?.opioidScope) && presentation?.note) {
        details.push(`<p><strong>Prescribing presentation:</strong> ${escapeHtml(presentation.note)}${presentation.labelUrl ? ` <a class="source-link" href="${escapeHtml(presentation.labelUrl)}" target="_blank" rel="noopener">Drug label ↗</a>` : ''}</p>`);
      }
      if (presentation?.deviceSourceUrl) details.push(`<p><strong>Device reference:</strong> <a class="source-link" href="${escapeHtml(presentation.deviceSourceUrl)}" target="_blank" rel="noopener">Manufacturer or FDA device reference ↗</a></p>`);
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
        `<p><a class="source-link" href="${escapeHtml(policy.url)}#page=${Number(policy.firstPage)}" target="_blank" rel="noopener">${escapeHtml(policy.title)} · pages ${Number(policy.firstPage)}–${Number(policy.lastPage)} ${policy.effective ? `· effective ${escapeHtml(policy.effective)}` : ''}</a> · <a href="${escapeHtml(policy.textUrl)}" target="_blank" rel="noopener">Read full source text</a></p>${record.planId === 'banner-ufc' && policy.scope ? `<p>${escapeHtml(policy.scope)}</p>` : ''}`
      ).join('') + '<p>Check the full indication, initial/renewal criteria and exceptions. Related-source links do not establish eligibility or approval.</p>');
    }
    if (record.sourceTextUrl && !record.guide) details.push(`<p><a class="source-link" href="${escapeHtml(record.sourceTextUrl)}" target="_blank" rel="noopener">Read full source text · PDF pages ${Number(record.sourcePage)}–${Number(record.sourceLastPage)}</a></p>`);
    if (record.planId === 'banner-ufc' && /ERYTHROMYCIN.*GEL/i.test(record.name)) details.push('<p>FDA lists the 63739-053-66 and 63739-053-68 erythromycin gel packages as discontinued. Exact claim eligibility is unverified.</p>');
    const sourceTitle = record.baselineSource ? 'Archived Arizona Complete Health formulary' : record.sourceTitle;
    const sourceLabel = [sourceTitle, record.sourceEffective && `effective ${record.sourceEffective}`, record.sourcePage && `page ${record.sourcePage}`].filter(Boolean).join(' · ');
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

  function renderCriteriaLibrary(query = el.criteriaSearch.value, target = el.criteriaResults) {
    const policies = criteriaSources();
    const matches = searchIndexedCriteria(query, policies);
    const guides = clinicalPolicyOnlyGroups(query, []);
    const count = matches.length;
    const structuredCount = matches.filter(policy => policy.structuredCriteriaUrl).length;
    el.criteriaCount.textContent = !normalize(query)
      ? `${Number(state.data.structuredCriteriaCount || 0)} of ${(state.data.statewidePaCriteria || []).length} statewide policies with clinical criteria · ${policies.length} total indexed sections · Type a medication or policy name`
      : `${guides.length} structured clinical guide${guides.length === 1 ? '' : 's'} · ${structuredCount} source-transcribed clinical polic${structuredCount === 1 ? 'y' : 'ies'} · ${count} matching source section${count === 1 ? '' : 's'}${count > 25 ? ' · Showing first 25 source sections' : ''}`;
    target.innerHTML = guides.map(group => `<article class="criteria-source">
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
        ${target === el.criteriaResults && policy.notes ? `<p>${escapeHtml(policy.notes)}</p>` : ''}
        ${structuredPolicyPanel(policy)}
        ${policy.guide ? `<details class="approval-guide"><summary>PA criteria · ${escapeHtml(policy.indication || policy.name)}</summary>${approvalGuideContent(policy)}</details>` : ''}
        <p><a class="source-link" href="${escapeHtml(sourceHref(policy))}" target="_blank" rel="noopener">Open policy chapter · PDF</a></p>
        ${policy.sourceTextUrl ? `<button type="button" class="text-button criteria-load" data-read-guideline="${escapeHtml(policy.id)}">Read full guideline text</button>` : ''}
        <pre class="guideline-verbatim" hidden></pre>
      </article>
    `).join('') || (normalize(query) ? '<p>No matching indexed sections. This does not prove a drug has no authorization requirements.</p>' : '');
  }

  function criteriaSources() {
    return [...(state.data.statewidePaCriteria || []),
      ...(state.data.policies || []).filter(policy => policy.planId === state.planId)];
  }

  function structuredPolicyPanel(policy) {
    if (policy.planId !== 'ahcccs-ffs-aihp' || !policy.structuredCriteriaUrl) return '';
    return `<section class="structured-policy">
      <button type="button" class="text-button" data-read-criteria="${escapeHtml(policy.id)}">View clinical criteria · ${Number(policy.structuredBranchCount)} product/indication branches</button>
      <div class="structured-criteria-content" hidden></div>
    </section>`;
  }

  function branchPageLink(branch, policy) {
    if (!policy?.sourceUrl || !Number.isInteger(branch.sourcePage)
        || branch.sourcePage < policy.sourcePage || branch.sourcePage > policy.sourceLastPage) return '';
    const href = policy.sourceUrl.split('#')[0] + '#page=' + branch.sourcePage;
    return `<p><a class="source-link" href="${escapeHtml(href)}" target="_blank" rel="noopener">Criteria source · PDF page ${branch.sourcePage}</a></p>`;
  }

  function structuredCriteriaMarkup(policy, source) {
    const field = (branch, key) => branch.fields[key]?.text || '';
    const rules = items => items.map(item => {
      const number = /^(\d+(?:\.\d+)*)\b/.exec(item.text)?.[1];
      const depth = number ? Math.min(number.split('.').length - 1, 4) : 0;
      return `<p class="clinical-source-rule ${item.kind === 'connector' ? 'clinical-source-connector' : ''}" style="margin-left:${depth * .5}rem">${escapeHtml(item.displayText || item.text)}</p>`;
    }).join('');
    return `<p>Source-transcribed clinical criteria · ${escapeHtml(policy.policyCode)} · ${escapeHtml(policy.sourceEffective)}. Clinician approval pending. Follow the product, indication and AND/OR wording below; this reference does not establish selected-plan coverage or PA status.</p>`
      + policy.branches.map((branch, i) => `<details class="clinical-source-branch result-disclosure">
        <summary>${escapeHtml([field(branch, 'Product Name'), field(branch, 'Diagnosis'), field(branch, 'Therapy Stage')].filter(Boolean).join(' · '))}</summary>
        <div class="result-disclosure-body">
          ${branchPageLink(branch, source)}
          ${['Diagnosis', 'Therapy Stage', 'Approval Length', 'Guideline Type'].map(key => field(branch, key) ? `<p><strong>${escapeHtml(key === 'Approval Length' ? 'Approval duration' : key)}:</strong> ${escapeHtml(field(branch, key))}</p>` : '').join('')}
          <p><strong>Clinical criteria — source order and logic:</strong></p>
          ${rules(branch.criteria)}
          ${branch.notes.length ? `<details class="result-disclosure" open><summary>Restrictions, exceptions and source notes</summary>${rules(branch.notes)}</details>` : ''}
        </div>
      </details>`).join('')
      + (policy.supplement?.text ? `<details class="result-disclosure"><summary>Supporting coverage information and source tables</summary><pre class="guideline-verbatim">${escapeHtml(policy.supplement.verbatim)}</pre></details>` : '')
      + `<details class="result-disclosure"><summary>Original policy context</summary><p>${escapeHtml(policy.context.text)}</p></details>`;
  }

  // Slice, never summarize: reconstructing these parts yields the exact source.
  // Product headings label source branches; they do not assert applicability.
  function policySourceBranches(text) {
    const pages = [...text.matchAll(/^(?:--- PDF page (\d+) ---|=== PDF PAGE (\d+) ===)\s*$/gmi)];
    let pageIndex = 0;
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
      while (pageIndex + 1 < pages.length && pages[pageIndex + 1].index <= marker.index) pageIndex++;
      const page = pages[pageIndex];
      const sourcePage = page && page.index <= marker.index ? Number(page[1] || page[2]) : null;
      return {sourcePage, product: product || 'Product branch (see source text)', stage, duration, text: content};
    })};
  }

  function policySourceBranchMarkup(text, policy) {
    const parsed = policySourceBranches(text);
    if (!parsed.branches.length) return '';
    return '<p>Original source branches — select the applicable product and treatment stage. All source wording and logical connectors are preserved; these are not clinician-approved summaries.</p>'
      + parsed.branches.map((branch, index) => `<details class="source-branch result-disclosure">
          <summary>${escapeHtml(branch.product)}${branch.stage ? ' · ' + escapeHtml(branch.stage) : ''}${branch.duration ? ' · ' + escapeHtml(branch.duration) : ''}</summary>
          ${policy ? branchPageLink(branch, policy) : ''}
          <pre class="guideline-verbatim">${escapeHtml(branch.text)}</pre>
        </details>`).join('')
      + `<details class="result-disclosure"><summary>Complete unformatted source, including document notes</summary><pre class="guideline-verbatim">${escapeHtml(text)}</pre></details>`;
  }

  function bindCriteriaLibrary() {
    el.criteriaSearch.addEventListener('input', () => renderCriteriaLibrary());
    document.addEventListener('toggle', event => {
      if (event.target.matches?.('details[data-card-clinical]')) populateCardClinical(event.target);
    }, true);
    document.addEventListener('click', event => {
      const retry = event.target.closest('[data-retry-card-criteria]');
      if (retry) populateCardClinical(retry.closest('details[data-card-clinical]'));
    });
    document.addEventListener('click', event => {
      const dialog = document.getElementById('sourceDialog');
      if (event.target.closest('[data-close-sources]')) { dialog.close(); return; }
      const button = event.target.closest('[data-card-sources]');
      if (!button) return;
      const entry = cardSourceGroups.get(button.dataset.cardSources);
      if (!entry || entry.planId !== state.planId) return;
      const preferredNdcs = bannerAlbuterolPreferredNdcs(entry.group);
      dialog.querySelector('#sourceDialogTitle').textContent = 'Sources — ' + (preferredNdcs.length ? 'Albuterol HFA inhaler' : dosageFormHeading(entry.group));
      const clinical = cardClinicalGroups.get(entry.group.key || entry.group.label);
      const bannerBranch = entry.group.records.find(r => r.planId === 'banner-ufc' && r.reviewedBannerBranches?.exactReferencePage)?.reviewedBannerBranches;
      const sourcePolicies = (clinical?.policies || []).map(policy => policy.id === bannerBranch?.policyId
        ? {...policy, sourcePage: bannerBranch.exactReferencePage} : policy);
      const originalRows = entry.group.records.map(record => `<section><h3>${escapeHtml(readableMedicationName(record.name))}</h3>${recordDetails(record)}</section>`).join('');
      dialog.querySelector('#sourceDialogContent').innerHTML = (preferredNdcs.length ? bannerAlbuterolSources(entry.group, originalRows) : originalRows)
        + (clinical?.guidance ? `<section><p>Source-reviewed summary; clinician approval pending.</p><p>${escapeHtml(clinical.guidance.guidelineCaution)}</p></section>` : '')
        + sourcePolicies.map(policy => `<section>${policy.planId === 'ahcccs-ffs-aihp' ? `<p><strong>${statewideFfsLabel}</strong></p>` : ''}<a href="${escapeHtml(sourceHref(policy))}" target="_blank" rel="noopener">${escapeHtml(policy.name || policy.policyCode)} · ${escapeHtml(policy.sourceEffective)}</a>${policy.scope ? `<p>${escapeHtml(policy.scope)}</p>` : ''}${policy.sourceTextUrl ? `<p><a href="${escapeHtml(policy.sourceTextUrl)}" target="_blank" rel="noopener">Original policy text</a></p>` : ''}<p>Source-transcribed criteria; clinician approval pending. Policy references do not independently establish selected-plan coverage or PA status.</p></section>`).join('');
      dialog.showModal();
    });
    document.addEventListener('click', async event => {
      const button = event.target.closest('[data-read-criteria]');
      if (!button) return;
      const policy = (state.data.statewidePaCriteria || []).find(p => p.id === button.dataset.readCriteria);
      if (!policy?.structuredCriteriaUrl || policy.planId !== 'ahcccs-ffs-aihp') return;
      const content = button.closest('.structured-policy').querySelector('.structured-criteria-content');
      const label = `View clinical criteria · ${Number(policy.structuredBranchCount)} product/indication branches`;
      if (button.dataset.loaded === 'true') {
        content.hidden = !content.hidden;
        button.textContent = content.hidden ? label : 'Hide clinical criteria';
        return;
      }
      button.disabled = true;
      button.textContent = 'Loading clinical criteria…';
      try {
        const response = await fetch(policy.structuredCriteriaUrl);
        if (!response.ok) throw new Error('Criteria unavailable');
        const structured = await response.json();
        if (structured.policyCode !== policy.policyCode || structured.sourceEffective !== policy.sourceEffective) throw new Error('Wrong source');
        content.innerHTML = structuredCriteriaMarkup(structured, policy);
        content.hidden = false;
        button.dataset.loaded = 'true';
        button.textContent = 'Hide clinical criteria';
      } catch (error) {
        content.textContent = 'Clinical criteria could not be loaded. Use the original PDF or full guideline text below.';
        content.hidden = false;
        button.textContent = 'Retry clinical criteria';
      } finally { button.disabled = false; }
    });
    document.addEventListener('click', event => {
      const shortcut = event.target.closest('[data-criteria-query]');
      if (!shortcut) return;
      el.criteriaSearch.value = shortcut.dataset.criteriaQuery;
      // A legacy reference brand may be absent from current policy headings.
      // Broaden source discovery to the displayed generic name only; this
      // never creates a policy assignment or an approval/coverage assertion.
      if (shortcut.dataset.criteriaFallback
          && !searchIndexedCriteria(el.criteriaSearch.value, criteriaSources()).length
          && !clinicalPolicyOnlyGroups(el.criteriaSearch.value, []).length) {
        el.criteriaSearch.value = shortcut.dataset.criteriaFallback;
      }
      if (el.criteriaLibrary.hidden) {
        const content = shortcut.closest('.inline-criteria-lookup').querySelector('.inline-criteria-results');
        if (content.dataset.loaded === 'true') content.hidden = !content.hidden;
        else { renderCriteriaLibrary(el.criteriaSearch.value, content); content.hidden = false; content.dataset.loaded = 'true'; }
        shortcut.setAttribute('aria-expanded', String(!content.hidden));
      } else {
        el.criteriaLibrary.open = true;
        renderCriteriaLibrary();
        el.criteriaLibrary.scrollIntoView({behavior:'smooth',block:'start'});
        el.criteriaSearch.focus();
      }
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
        const markup = policySourceBranchMarkup(pre.textContent, policy);
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
    // Banner has a product-specific counterpart to the statewide U-500 guideline.
    if (group.records?.some(r => r.reviewedBannerBranches?.policyId === 'banner-policy-12-969')) return null;
    const hasUhcGlp1Criteria = group.records?.some(record => !record.isStatewideReference
      && record.uhcClinicalBindings?.some(binding => binding.policyId === 'uhc-nov2026-policy-gl-720195'));
    const brands = new Set(group.brands.map(normalize));
    const generic = normalize(group.name);
    return (state.data.statewideClinicalGuidance || []).find(guide => {
      if (hasUhcGlp1Criteria && guide.policyCode === 'GL-749236') return false;
      if (group.records?.some(record => record.excludedStatewidePolicyCode === guide.policyCode)) return false;
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

  function clinicalGuidanceContent(guide, compact = false) {
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
    if (compact) return `${(guide.pathways || guide.stages || []).some(x => x.approvalDuration) ? '' : `<p><strong>Approval duration:</strong> ${escapeHtml(guide.approvalDuration)}</p>`}${stages || pathways}`;
    return `
      <p>${escapeHtml(guide.summary)}</p>
      ${stages ? `<p><strong>Requirements by treatment stage:</strong></p>${stages}` : `<p><strong>Qualifying pathways — any ONE:</strong></p>${pathways}`}
      ${(guide.pathways || guide.stages || []).some(x => x.approvalDuration) ? '' : `<p><strong>Approval duration:</strong> ${escapeHtml(guide.approvalDuration)}</p>`}
      <p><strong>Suggested documentation to include:</strong></p>
      <ul>${guide.documentationSuggestions.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
      <p class="guide-review-status">Documentation suggestions are not a separate insurer-prescribed checklist.</p>
      <p>${escapeHtml(guide.guidelineCaution)}</p>
      <p class="guide-review-status">Source-reviewed summary; clinician approval pending. The guideline does not independently establish plan coverage or PA status.</p>
      <p><a class="source-link" href="${escapeHtml(sourceHref(guide))}" target="_blank" rel="noopener">PA reference: ${escapeHtml(guide.policyCode)} · PDF page ${Number(guide.sourcePage)}${guide.sourceLastPage !== guide.sourcePage ? '–' + Number(guide.sourceLastPage) : ''}</a> · <a href="${escapeHtml(guide.sourceTextUrl)}" target="_blank" rel="noopener">Full guideline text</a></p>`;
  }

  function criteriaLibraryShortcut(group) {
    const query = group.brands[0] || group.name;
    return `<section class="inline-criteria-lookup"><button type="button" aria-expanded="false" class="text-button source-action criteria-shortcut" data-criteria-query="${escapeHtml(query)}" data-criteria-fallback="${escapeHtml(policyLookupQuery(group.name))}">More clinical criteria</button><div class="inline-criteria-results" hidden></div></section>`;
  }

  function policyLookupQuery(name) {
    const presentation = new Set('hcl hydrochloride oral topical transdermal rectal vaginal ophthalmic otic inhalation nasal intravenous intramuscular subcutaneous injection injectable tablet tablets capsule capsules solution suspension soln susp gel cream ointment patch patches powder aerosol spray syrup elixir lozenge chewable disintegrating extended delayed controlled release er xr sr ir dr cr xl ec mg mcg ml meq gm g units hr hour hours day pack packet kit pref prefilled syr syringe pen auto inj usp'.split(' '));
    return [...new Set((String(name).toLowerCase().match(/[a-z]+/g) || []).filter(word => !presentation.has(word)))].join(' ');
  }

  const inlinePolicySources = new Map();
  const namedPolicyCache = new Map();
  function namedPlanPolicies(group, statewide = false) {
    const scope = statewide ? 'ahcccs-ffs-aihp' : state.planId;
    const identities = [...new Set([...group.brands, group.name, ...(group.records || []).map(record => (record.standardDisplayName || '').replace(/\s*\([^)]*\)\s*/g, ' ').trim())].map(normalize).filter(name => name.length >= 4 && name !== 'various'))];
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

  function linkedPolicyPanels(group, collectOnly = false) {
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
        add(state.data.policies.find(p => p.id === link.policyId && p.planId === state.planId) || policy);
      }
      if (record.scopedPolicyReference) {
        const { id, scope } = record.scopedPolicyReference;
        const policy = state.data.policies.find(p => p.id === id && p.planId === state.planId);
        if (policy) add({ ...policy, scope });
      }
      for (const binding of uhcRecordBindings(record)) {
        const policy = state.data.policies.find(p => p.id === binding.policyId && p.planId === state.planId);
        if (policy) add(binding.role === 'duplication'
          ? {...policy, scope: 'Applies when a therapeutic duplication edit is triggered.'}
          : uhcStandalonePolicyReferences.has(binding.role)
          ? {...policy, scope: uhcStandalonePolicyReferences.get(binding.role).scope}
          : binding.role === 'nonpreferred' && record.id === 'uhc-oct-complete-009ca23afd12966f'
          ? {...policy, scope: 'General nonpreferred guidance linked to brand Pradaxa oral capsules.'} : policy);
      }
    }
    // Navigation only: a named source is not an assertion that its criteria
    // apply to every formulation or that this medication requires PA.
    for (const policy of [...namedPlanPolicies(group), ...namedPlanPolicies(group, true)]) {
      if (policy.planId === 'ahcccs-ffs-aihp' && policy.policyCode === 'GL-99431'
          && group.records.some(record => record.id === 'uhc-oct-complete-367d1f3038b2b927')) continue;
      if (group.records.some(record => record.unverifiedPolicyCode === policy.policyCode || record.excludedPolicyCode === policy.policyCode
        || record.excludedStatewidePolicyCode === policy.policyCode)) continue;
      if (policy.policyCode === 'GL-572198' && policy.planId === 'uhc-community-az'
          && group.records.some(record => uhcBrandTopamaxRows.has(record.id) || uhcAgeEightPa(record))) continue;
      add(policy);
    }
    if (collectOnly) return [...links.values()];
    const plan = state.data.plans.find(p => p.id === state.planId);
    return [...links.values()].map(policy => `<section class="linked-clinical-policy">
      <h4>${policy.planId === 'ahcccs-ffs-aihp' ? 'AHCCCS reference policy' : 'Selected-plan policy'} · ${escapeHtml(policy.name)}</h4>
      <article class="criteria-source result-disclosure-body">
        <p><strong>${escapeHtml(policy.planId === 'ahcccs-ffs-aihp' ? 'AHCCCS statewide clinical reference' : plan?.name)}</strong>${policy.sourceEffective ? ' · source ' + escapeHtml(policy.sourceEffective) : ''}</p>
        <p>Review the applicable product and indication. This policy reference does not independently establish plan coverage or PA status.</p>
        ${policy.scope ? `<p>${escapeHtml(policy.scope)}</p>` : ''}
        ${structuredPolicyPanel(policy)}
        <p><a class="source-link" href="${escapeHtml(sourceHref(policy))}" target="_blank" rel="noopener">PA reference · pages ${Number(policy.sourcePage)}–${Number(policy.sourceLastPage)}</a></p>
        <button type="button" class="text-button criteria-load" data-read-guideline="${escapeHtml(policy.id)}">Read full guideline text</button>
        <pre class="guideline-verbatim" hidden></pre>
      </article>
    </section>`).join('');
  }

  const cardSourceGroups = new Map();
  function bannerAlbuterolPreferredNdcs(group) {
    if (state.planId !== 'banner-ufc' || normalize(group.name) !== 'albuterol sulfate inhaler') return [];
    return [...new Set(group.records.filter(record => record.planId === state.planId && !record.isStatewideReference
      && /Source preferred-status wording:\s*Preferred Albuterol NDCs\b/i.test(record.notes || ''))
      .flatMap(record => [...record.notes.matchAll(/\bNDC\s+(\d{11})\b/gi)].map(match => match[1])))];
  }

  function bannerAlbuterolSources(group, originalRows) {
    const sources = new Map();
    for (const record of group.records) {
      if (!record.sourceUrl || sources.has(record.sourceUrl)) continue;
      sources.set(record.sourceUrl, `<li>${record.isStatewideReference ? 'Statewide reference: ' : 'Banner formulary: '}
        <a href="${escapeHtml(sourceHref(record))}" target="_blank" rel="noopener">${escapeHtml(record.sourceTitle)} · effective ${escapeHtml(record.sourceEffective)}</a></li>`);
    }
    return `<ul>${[...sources.values()].join('')}</ul>
      <details class="result-disclosure"><summary>Original source rows</summary>${originalRows}</details>`;
  }

  function sourcesLink(group) {
    const key = group.key || group.label;
    cardSourceGroups.set(key, {group, planId: state.planId});
    return `<button type="button" class="text-button source-action" data-card-sources="${escapeHtml(key)}">Sources</button>`;
  }

  // Card content is product-scoped; full policies stay in the archived library/Sources.
  function productIdentity(value) {
    return policyLookupQuery(String(value).replace(/\([^)]*\)/g, ' '))
      .replace(/\b(?:brand|generic|free base|hydrochloride|hcl)\b/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  function matchingClinicalBranches(policy, group) {
    const brands = group.brands.map(productIdentity).filter(Boolean);
    const names = [...new Set([group.name, ...(group.records || []).map(r => r.name)].map(productIdentity).filter(Boolean))];
    return (policy.branches || []).filter(branch => {
      const product = branch.fields?.['Product Name']?.text || branch.product || '';
      const identities = product.split(/[,;]|\bgeneric\b|\bbrand\b/gi).map(productIdentity).filter(Boolean);
      const presentation = String(group.name) + ' ' + (group.records || []).map(r => r.name).join(' ');
      for (const form of ['ophthalmic', 'otic', 'topical', 'ointment', 'cream', 'injection', 'nasal', 'inhalation', 'extended release']) {
        if (normalize(product).includes(form) && !normalize(presentation).includes(form)) return false;
      }
      const sourceStrengths = [...product.matchAll(/\b(\d+(?:\.\d+)?)\s*mg\b/gi)].map(m => Number(m[1]));
      if (sourceStrengths.length && !(group.records || []).every(record => {
        const strengths = [...record.name.matchAll(/\b(\d+(?:\.\d+)?)\s*mg\b/gi)].map(m => Number(m[1]));
        return strengths.length && strengths.every(value => sourceStrengths.includes(value));
      })) return false;
      return brands.length ? brands.every(brand => identities.includes(brand)) : identities.some(identity => names.includes(identity));
    });
  }

  function cardSourceRules(items, additional = true) {
    const last = items[items.length - 1]?.text || '';
    if (additional && items.length > 2 && items[items.length - 2]?.text.trim() === 'AND'
        && /^(?:\d+\s*-\s*)?(?:For generic\b|If the request is for generic\b)/i.test(last)) {
      return cardSourceRules(items.slice(0, -2), false)
        + `<details class="additional-medication-criteria"><summary>More clinical criteria</summary>${cardSourceRules(items.slice(-2), false)}</details>`;
    }
    return items.map(item => {
      const value = item.displayText || item.text;
      const number = /^(\d+(?:\.\d+)*)\b/.exec(value)?.[1];
      const depth = number ? Math.min(number.split('.').length - 1, 4) : 1;
      return `<p class="card-clinical-rule ${item.kind === 'connector' ? 'clinical-source-connector' : /(?:all|one) of the following:/i.test(value) ? 'clinical-logic-label' : ''}" style="margin-left:${depth * .65}rem">${escapeHtml(value.replace(/^\d+(?:\.\d+)*(?:\s*-\s*|\s+(?=(?:ALL|ONE|For|If)\b))/i, '').replace(/^•\s*/, '• '))}</p>`;
    }).join('');
  }

  function cardBranchMarkup(branch, policy) {
    const field = key => branch.fields?.[key]?.displayText || branch.fields?.[key]?.text || '';
    // Administrative dispensing instructions are retained in the source, not clinical UI.
    const notes = (branch.notes || []).filter(item => !/^PA Team Note:/i.test(item.text));
    return `<section class="card-clinical-branch">
      ${branchPageLink(branch, policy)}
      ${['Diagnosis', 'Therapy Stage', 'Approval Length'].filter(key => field(key)).map(key => `<p><strong>${key === 'Approval Length' ? 'Approval duration' : key === 'Therapy Stage' ? 'Treatment stage' : key}:</strong> ${escapeHtml(field(key))}</p>`).join('')}
      ${cardSourceRules(branch.criteria || [])}
      ${notes.length ? `<div class="clinical-exceptions"><strong>Restrictions &amp; exceptions</strong>${cardSourceRules(notes)}</div>` : ''}
    </section>`;
  }

  function cardTextBranchMarkup(branch, policy) {
    const text = branch.text.replace(/^\s*(?:--- PDF page \d+ ---|=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
    // Split at the first actual heading, not at subsequent inline references to approval criteria.
    const heading = /^[\t ]*Approval[\t ]+Criteria[\t ]*:?[ \t]*$/im.exec(text);
    const body = heading ? text.slice(heading.index + heading[0].length) : '';
    if (!body) return '<p>Formatted criteria for this medication are not available. See the PA reference.</p>';
    // Original clinical text is retained verbatim, with only line-break/page
    // furniture cleanup. Administrative PA-team dispensing notes stay internal.
    const clinical = body.split(/\bPA Team Note\s*:/i)[0]
      .replace(/^.*UnitedHealthcare Community Plan of Arizona.*Clinical Pharmacy Guidelines.*$/gmi, '')
      .replace(/\bNotes\s*$/i, '').trim();
    const paragraphs = [];
    for (const raw of clinical.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line) continue;
      if (/^(?:•|\d+(?:\.\d+)*\s*(?:-|[A-Za-z])|OR$|AND$)/.test(line) || !paragraphs.length) paragraphs.push(line);
      else paragraphs[paragraphs.length - 1] += ' ' + line;
    }
    return `<section class="card-clinical-branch">
      ${branchPageLink(branch, policy)}
      ${branch.stage ? `<p><strong>Treatment stage:</strong> ${escapeHtml(branch.stage)}</p>` : ''}
      ${branch.duration ? `<p><strong>Approval duration:</strong> ${escapeHtml(branch.duration)}</p>` : ''}
      ${cardSourceRules(paragraphs.map(text => ({text, kind: /^(?:AND|OR)$/.test(text) ? 'connector' : 'requirement'})))}
    </section>`;
  }

  const cardClinicalGroups = new Map();
  const statewideFfsLabel = 'AHCCCS Statewide · Fee-for-service';
  const bannerRespiratoryGuides = new Map([
    ['banner-pcp-nov10-041', {
      name: 'Stiolto Respimat', policyCode: 'GL-269199', sourcePage: 1049, sourceLastPage: 1050,
      pathways: [{title: 'COPD', all: [
        'Diagnosis of chronic obstructive pulmonary disease (COPD).',
        {any: [
          'History of failure, contraindication, or intolerance to treatment with a 30-day trial of a long-acting beta agonist.',
          'History of failure, contraindication, or intolerance to treatment with a 30-day trial of an orally inhaled anticholinergic.'
        ]}
      ]}]
    }],
    ['banner-full-9e2ca54467b1006f', {
      name: 'Serevent Diskus', policyCode: 'GL-99495', sourcePage: 1564, sourceLastPage: 1566,
      pathways: [
        {title: 'Asthma', all: ['Diagnosis of asthma.', 'Age 4 years or older.', 'Also receiving treatment with an inhaled corticosteroid.']},
        {title: 'Exercise-induced bronchospasm', all: ['Diagnosis of exercise-induced bronchospasm.', 'Used for prevention.', 'Age 4 years or older.']},
        {title: 'COPD-associated bronchospasm', all: ['Diagnosis of bronchospasm associated with COPD.']}
      ]
    }]
  ]);

  function bannerRespiratoryGuide(group) {
    const record = group.records.find(row => !row.isStatewideReference && row.planId === 'banner-ufc'
      && row.sourceEffective === '2026-10-01' && row.pa === 'required' && bannerRespiratoryGuides.has(row.id));
    if (!record) return null;
    const guide = bannerRespiratoryGuides.get(record.id);
    return {
      ...guide, planId: 'banner-ufc', approvalDuration: '12 months', sourceEffective: '2026-11-01',
      sourceUrl: 'https://www.bannerhealth.com/bhpprovider/-/media/files/project/bhpprovider/pharmacy/medicaid/prov-bufc_pharmacy-pa-criteria_eff11012026_en.pdf?hash=383206F074F0B301767EC09CEC9F35FA&sc_lang=en',
      sourceTextUrl: `./banner-policy-text/12-${guide.sourcePage}.txt`,
      guidelineCaution: 'The policy does not specify an initial or renewal stage.'
    };
  }

  const calcipotrieneStep = 'For 0.005% cream or ointment, trial of two medium- to high-potency topical corticosteroids.';
  const uhcFormularySteps = new Map([
    ['uhc-oct-complete-aadf073c434c4009', '30-day trial of one inhaled corticosteroid, a long-acting beta agonist, or an orally inhaled anticholinergic.'],
    ['uhc-oct-complete-e27f2cb8dcfa082e', '30-day trial of one inhaled corticosteroid.'],
    ['uhc-oct-complete-836fcbdd50338512', '30-day trial of one inhaled corticosteroid, a long-acting beta agonist, or an inhaled anticholinergic.'],
    ['uhc-oct-complete-f341f42e74fd7bbd', calcipotrieneStep],
    ['uhc-oct-complete-d3c2686424414dde', calcipotrieneStep]
  ]);

  function uhcRecordBindings(record) {
    const bindings = record.uhcClinicalBindings || [];
    // Keep the source binding intact in data. Render its scope, not an implied
    // authorization for an indication that the verified label does not support.
    const opioidScope = isUhcOctoberRow(record) && record.reviewedPresentation?.opioidScope;
    if (opioidScope === 'oud_only') return bindings.map(binding =>
      binding.policyId.endsWith('gl-620192') ? {...binding, role: 'methadose_pain_reference'} : binding);
    if (opioidScope === 'pain') return bindings.flatMap(binding => {
      if (!binding.policyId.endsWith('gl-620192') || binding.role !== 'product') return [binding];
      return [
        {...binding, branchIndexes: binding.branchIndexes.filter(i => [1,4,7].includes(i))},
        {...binding, role: 'concurrent_opioid_dur', branchIndexes: binding.branchIndexes.filter(i => i === 0)},
        {...binding, role: 'mme_exception', branchIndexes: binding.branchIndexes.filter(i => [9,10,11].includes(i))}
      ].filter(b => b.branchIndexes.length);
    });
    const glucoseSupply = isUhcOctoberRow(record) && uhcReviewedGlucoseSupplies.get(record.id);
    if (glucoseSupply?.strip || glucoseSupply?.meterPolicy) {
      const policyId = glucoseSupply.strip ? uhcTestStripPolicyId : uhcMeterPolicyId;
      return [
        ...bindings.filter(binding => binding.role !== 'nonpreferred' && binding.policyId !== policyId),
        {policyId, role: 'product', branchIndexes: [0]},
        ...(glucoseSupply.strip ? [{policyId, role: 'quantity', branchIndexes: [1]}] : [])
      ];
    }
    if (isUhcOctoberRow(record) && uhcReviewedTestStrips.has(record.id)
        && (record.qlAmount || record.qlDays) && !bindings.some(binding => binding.policyId === uhcTestStripPolicyId)) {
      // GL-369221 branch 1 applies to QL exceptions for preferred and nonpreferred strips.
      return [...bindings, {policyId: uhcTestStripPolicyId, role: 'quantity', branchIndexes: [1], exactQuantityPage: 1687}];
    }
    if (uhcAgePaCardLabels.has(record.id) && uhcAgeEightPa(record)) {
      return bindings.map(binding => {
        if (binding.role === 'nonsolid' && binding.policyId === generalNonsolidPolicyId) {
          return {...binding, role: 'general_nonsolid_reference'};
        }
        if (record.id === 'uhc-oct-complete-14ba345bf06d2a5e' && binding.policyId === 'uhc-nov2026-policy-gl-140683') {
          return {...binding, role: 'epaned_reference'};
        }
        return binding;
      });
    }
    if (record.id === uhcLowStrengthAlbuterolId && uhcAgeEightPa(record)) {
      return bindings.map(binding => binding.policyId === generalNonsolidPolicyId && binding.role === 'nonsolid'
        ? {...binding, role: 'general_nebulizer_reference'} : binding);
    }
    if (uhcBrandTopamaxRows.has(record.id)) {
      // GL-572198's 50 mg sprinkle branch is not a product match for either listing.
      return bindings.filter(binding => binding.policyId !== 'uhc-nov2026-policy-gl-572198');
    }
    if (record.id !== 'uhc-oct-complete-0d5d9de3ba6af1f0' || record.sourceEffective !== '2026-10-01'
        || record.isStatewideReference || record.planId !== 'uhc-community-az'
        || bindings.some(binding => binding.policyId === 'uhc-nov2026-policy-gl-735259')) return bindings;
    return [...bindings, {
      policyId: 'uhc-nov2026-policy-gl-735259', role: 'duplication', branchIndexes: [0],
      productLabel: 'Perforomist nebulizer solution'
    }];
  }

  const clinicalSourceLoads = new Map();
  async function loadClinicalSource(policy) {
    const url = policy.structuredCriteriaUrl || policy.sourceTextUrl;
    if (!clinicalSourceLoads.has(url)) {
      const request = (async () => {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Clinical source unavailable');
        if (policy.structuredCriteriaUrl) {
          const structured = await response.json();
          if (structured.policyCode !== policy.policyCode || structured.sourceEffective !== policy.sourceEffective) throw new Error('Wrong clinical source');
          return structured;
        }
        return {branches: policySourceBranches(await response.text()).branches};
      })();
      clinicalSourceLoads.set(url, request);
      request.catch(() => clinicalSourceLoads.delete(url));
    }
    return clinicalSourceLoads.get(url);
  }

  function uhcGroupBindings(group) {
    if (state.planId !== 'uhc-community-az') return [];
    const found = new Map();
    for (const record of group.records || []) {
      if (record.planId !== state.planId || record.isStatewideReference) continue;
      for (const binding of uhcRecordBindings(record)) {
        const key = [binding.policyId, binding.role, binding.branchIndexes.join(','),
          uhcReviewedProductGroups.has(record.id) ? binding.productLabel : ''].join(':');
        found.set(key, binding);
      }
    }
    return [...found.values()];
  }

  function uhcRestrictionSummary(group) {
    if (state.planId !== 'uhc-community-az') return '';
    const rows = (group.records || []).filter(r => r.planId === state.planId && !r.isStatewideReference);
    const ql = rows.filter(r => r.qlAmount || r.qlDays);
    const statedLimits = [...new Set(ql.map(r => r.policyQuantityLimit?.text).filter(Boolean))];
    if (statedLimits.length) return `<p><strong>Quantity limit:</strong> ${escapeHtml(statedLimits.join(' '))}</p>`;
    const amounts = [...new Set(ql.map(r => r.qlAmount).filter(v => v && !/QL printed|numeric limit not shown/i.test(v)))];
    const days = [...new Set(ql.map(r => r.qlDays).filter(Boolean))];
    if (!ql.length) return '';
    return `<p><strong>Quantity limit:</strong> ${amounts.length ? escapeHtml(amounts.join('; ')) + (days.length ? ' per ' + escapeHtml(days.join('; ')) + ' days' : '') : 'Applies. The formulary does not publish a numeric limit; see the quantity-limit policy below.'}</p>`;
  }

  async function uhcClinicalContent(group, bindings, guidance = null) {
    const policies = state.data.policies.filter(p => p.planId === state.planId);
    const byRole = roles => bindings.filter(b => roles.includes(b.role));
    let primary = byRole(['product']);
    if (!primary.length) primary = byRole(['nonsolid']);
    if (!primary.length) primary = byRole(['nonpreferred']);
    let quantity = byRole(['quantity']);
    if (!quantity.length) quantity = byRole(['global_quantity']);
    const sections = [], references = [], seen = new Set();
    const duplication = byRole(['duplication']);
    const hypnoticRequest = byRole(['hypnotic_request']);
    const hypnoticStep = byRole(['hypnotic_step']);
    const ageScoped = byRole(['age_scoped', 'preferred_adhd_request']);
    const diagnosisRequest = byRole(['diagnosis_request']);
    const psoriasisRequest = byRole(['psoriasis_request']);
    const topicalQuantity = byRole(['topical_quantity']);
    const monthlyPrescriptionException = byRole(['monthly_prescription_exception']);
    const anxiolyticRequest = byRole(['anxiolytic_request']);
    const scopedOptionNames = role => [...new Set((group.records || []).filter(r => r.planId === state.planId && !r.isStatewideReference && r.uhcClinicalBindings?.some(b => b.role === role)).map(r => r.name))].map(escapeHtml).join('; ');
    const packetReference = byRole(['packet_reference']);
    const reviewedInsulin = group.records?.some(record => uhcInsulinAndSupplyLabels.has(record.id) || reviewedCardPresentation(record)?.uhcFormRx);
    const genericDabigatran = group.records.find(record => record.id === genericDabigatranId);
    const reviewedGvoke = group.records.some(record => uhcGvokePresentations.has(record.id));
    const generalPaPresentation = group.records.some(record => reviewedCardPresentation(record)?.generalPa);
    const administrativeFallback = primary.length && primary.every(binding => binding.role === 'nonpreferred');
    const paRows = (group.records || []).filter(r => r.planId === state.planId && !r.isStatewideReference
      && !constipationGenericRows.has(r.id) && ['required','conditional'].includes(r.pa));
    const reviewedAgeRow = paRows.find(record => uhcAgePaCardLabels.has(record.id) && uhcAgeEightPa(record));
    const asmanexHfa = reviewedAgeRow?.id === 'uhc-oct-complete-de1ca42f17826905';
    const fallbackRows = administrativeFallback ? paRows.filter(r => r.uhcClinicalBindings?.some(b => b.role === 'nonpreferred')) : [];
    const reviewedProduct = group.records.some(record => uhcReviewedProductGroups.has(record.id));
    const glucoseSupply = group.records.map(r => uhcReviewedGlucoseSupplies.get(r.id)).find(Boolean);
    const glucosePolicyLabel = glucoseSupply?.strip ? 'Test strip PA and QL guideline' : 'Nonpreferred meter PA guideline';
    const criteriaSections = [
      [glucoseSupply?.strip || glucoseSupply?.meterPolicy ? glucosePolicyLabel : asmanexHfa ? 'Asthma PA guideline' : administrativeFallback ? 'General nonpreferred PA criteria' : 'Prior authorization', primary],
      ['Age-specific PA criteria', ageScoped],
      ['Conditional hypnotic PA criteria', hypnoticRequest],
      ['Ramelteon step therapy', hypnoticStep],
      ['Diagnosis-linked PA request criteria', diagnosisRequest],
      ['Psoriasis request criteria', psoriasisRequest],
      ['Packet PA guideline', packetReference],
      ['Therapeutic duplication exceptions', duplication],
      ['Concurrent opioid therapy (DUR)', byRole(['concurrent_opioid_dur'])],
      ['Cumulative MME exceptions', byRole(['mme_exception'])],
      ['Quantity-limit exceptions', quantity],
      ['Topical quantity-limit exceptions', topicalQuantity],
      ['Monthly prescription-limit exception', monthlyPrescriptionException],
      ['Anxiolytic request criteria', anxiolyticRequest]
    ];
    for (const [kind, selected] of criteriaSections) {
      const body = [];
      for (const binding of selected) {
        const policy = policies.find(p => p.id === binding.policyId);
        if (!policy) continue;
        const source = await loadClinicalSource(policy);
        for (const i of binding.branchIndexes) {
          const key = policy.id + ':' + i;
          if (seen.has(key)) continue;
          const branch = source.branches[i];
          if (!branch) throw new Error('Clinical branch missing');
          seen.add(key);
          const scope = binding.branchLabels?.[i];
          const productLabel = reviewedProduct
            ? [...new Set(selected.filter(b => b.policyId === policy.id && b.branchIndexes.includes(i))
              .map(b => b.productLabel).filter(Boolean))].join(' / ')
            : binding.productLabel || (binding.policyId === constipationPolicyId
              && group.records.some(record => record.id === uhcMotegrityId) ? 'Brand Motegrity oral tablets' : '');
          const label = productLabel && selected !== packetReference ? `<p><strong>Product:</strong> ${escapeHtml(productLabel)}</p>`
            : scope ? `<p><strong>Formulation:</strong> ${escapeHtml(scope)}</p>` : '';
          // The final condition and preceding AND in this shared policy apply only to brand Nexium.
          let applicable = selected === packetReference ? {...branch, criteria: branch.criteria.slice(0, -2)} : branch;
          // DEC-12/13: the exact preferred SC listing omits the source's
          // nonpreferred-only prerequisite, without editing the source.
          if (policy.policyCode === 'GL-565279' && binding.omitNonpreferredCondition === true) {
            const final = branch.criteria.at(-1);
            const connector = branch.criteria.at(-2);
            if (connector?.kind !== 'connector' || connector.text !== 'AND'
                || !final?.text.startsWith('3 - If the request is non-preferred')
                || !final.text.includes('tocilizumab biosimilars')) throw new Error('Tocilizumab preference scope changed');
            applicable = {...branch, criteria: branch.criteria.slice(0, -2)};
          }
          if (binding.role === 'preferred_adhd_request') {
            const cutoff = branch.criteria.findIndex(item => item.text.startsWith('2 - If the request is non-preferred'));
            if (policy.policyCode !== 'GL-689195' || branch.criteria[cutoff - 1]?.text !== 'AND'
                || !branch.criteria[0].text.includes('under 6 years old')) throw new Error('Preferred ADHD request scope changed');
            applicable = {...branch, criteria: branch.criteria.slice(0, cutoff - 1), notes: []};
          }
          body.push(label + cardBranchMarkup(applicable, policy));
        }
        if (!references.some(p => p.id === policy.id)) {
          references.push(binding.exactQuantityPage ? {...policy, exactQuantityPage: binding.exactQuantityPage} : policy);
        }
      }
      const context = selected === duplication ? '<p>Applies when a therapeutic duplication edit is triggered.</p>'
        : selected === hypnoticRequest ? '<p>For the named generic hypnotics: PA criteria for more than one hypnotic in 30 days or a patient younger than six years. This is not a routine PA requirement.</p>'
        : selected === hypnoticStep ? '<p>Applies to generic ramelteon only; this is step therapy, not routine PA.</p>'
        : selected === ageScoped ? '<p>The October 2026 formulary lists an age limit and leaves the PA field blank for the listed product. The November 2026 guideline specifies these age-based criteria.</p>'
        : selected === psoriasisRequest ? '<p>The October 2026 formulary prints step therapy and a quantity limit. These are the named psoriasis request criteria, not a verified routine PA trigger or a numeric quantity limit.</p>'
        : selected === monthlyPrescriptionException ? `<p>Applies to monthly prescription-limit exception requests for: ${scopedOptionNames('monthly_prescription_exception')}. This is separate from the individual product quantity limit and other conditional request criteria.</p>`
        : selected === anxiolyticRequest ? `<p>Named options: ${scopedOptionNames('anxiolytic_request')}. Criteria for requests in patients under age 6 or for more than one anxiolytic in 30 days. This is not a routine PA requirement or a numeric product quantity limit.</p>`
        : selected === topicalQuantity ? '<p>Applies to requests exceeding the allowed topical package size or monthly quantity. The numeric limit is unverified.</p>'
        : selected === diagnosisRequest ? '<p>The October 2026 formulary requires a diagnosis and lists a quantity limit. This named UHC guideline supplies request criteria; the exact PA trigger or diagnosis-code override is unverified.</p>'
        : selected === packetReference ? '<p>The October 2026 formulary lists age and quantity limits for both packets and leaves their PA fields blank. The UHC guideline names both packets and gives criteria by age and ability to swallow solid forms.</p>'
        : selected === primary && glucoseSupply?.strip
        ? '<p>PA criteria apply to nonpreferred strip products. The quantity-limit exception below also covers preferred strips.</p>'
        : selected === primary && glucoseSupply?.meterPolicy
        ? '<p>Applies to a nonpreferred meter listing with approval at NDC level. Confirm the exact covered package.</p>'
        : selected === primary && asmanexHfa
        ? '<p>The guideline covers asthma. How it applies to the age and continued-use conditions in the formulary is unverified.</p>'
        : selected === primary && administrativeFallback ? (
          (fallbackRows.length < paRows.length || (reviewedInsulin && fallbackRows.length < group.records.length)
            ? `<p><strong>Applies to:</strong> ${escapeHtml(fallbackRows.map(r => uhcReviewedProductGroups.get(r.id)?.label || (reviewedCardPresentation(r)?.uhcFormRx && reviewedCardPresentation(r).option) || uhcInsulinAndSupplyLabels.get(r.id) || readableMedicationName(r.name)).join('; '))}</p>` : '')
          + '<p>Product-specific approval criteria are unverified.</p>'
        ) : '';
      if (body.length) sections.push(`<section class="uhc-restriction-criteria"><h4>${kind}</h4>${context}${body.join('')}</section>`);
    }
    // Dated UHC PDL class edit; keep distinct from the named hypnotic request
    // policy and from the individual product's printed QL/PA fields.
    const classRuleIds = new Set(['uhc-oct-complete-ee91f45e62d87482','uhc-oct-complete-cc0214a5924ebd77','uhc-oct-complete-4f1a6bcd488425ec','uhc-oct-complete-d63fde77a711b8ce','uhc-oct-complete-e3438ba8499baf2f','uhc-oct-complete-64b218c84fdb66aa']);
    const classRows = (group.records || []).filter(r => r.planId === state.planId && !r.isStatewideReference && r.sourceEffective === '2026-10-01' && classRuleIds.has(r.id));
    if (classRows.length) sections.push('<section class="uhc-restriction-criteria"><h4>Class-wide prescription limit</h4><p>Applies to the listed options: ' + escapeHtml(classRows.map(r => r.name).join('; ')) + '. The October 2026 PDL limits sedative hypnotics, barbiturates and select muscle relaxants to four medications per 30 days; PA is required for additional fills. This is not an individual product quantity limit. <a class="source-link" href="' + escapeHtml(sourceHref({...classRows[0], sourcePage: 35})) + '" target="_blank" rel="noopener">UHC formulary · PDF page 35</a></p></section>');
    const conditionalOnly = duplication.length && paRows.length && paRows.every(r => r.pa === 'conditional');
    if (conditionalOnly) sections.unshift('<p>The formulary lists conditional PA. See the formulation-specific restrictions and the duplication exception below.</p>');
    else if (paRows.length && !primary.length) sections.unshift(paRows.every(r => r.pa === 'conditional')
      ? '<p>Product-specific approval criteria are unverified. See the formulary for the conditional PA requirement.</p>'
      : '<p>PA is required. Approval criteria have not yet been verified for this formulation. Review the linked UHC source.</p>');
    const datedGeneric = group.records.some(record => constipationGenericRows.has(record.id));
    if (datedGeneric && !references.some(policy => policy.id === constipationPolicyId)) {
      const datedPolicy = policies.find(policy => policy.id === constipationPolicyId);
      if (datedPolicy) references.unshift(datedPolicy);
    }
    const referenceLabels = references.map(p => p.id === constipationPolicyId && datedGeneric && !primary.length
      ? 'UHC October 18 policy' : [...primary, ...ageScoped].some(b => b.policyId === p.id)
      ? ([uhcTestStripPolicyId, uhcMeterPolicyId].includes(p.id) && glucoseSupply ? glucosePolicyLabel
        : reviewedInsulin && quantity.some(b => b.policyId === p.id) ? 'PA and QL reference'
        : asmanexHfa && p.policyCode === 'GL-605215' ? 'Asthma PA guideline'
        : (reviewedGvoke || generalPaPresentation) && p.policyCode === 'GL-231255' ? 'General nonpreferred PA reference'
        : genericDabigatran && p.policyCode === 'GL-231255' ? 'Brand nonpreferred reference' : 'PA reference')
      : [...hypnoticRequest, ...hypnoticStep].some(b => b.policyId === p.id) ? 'Hypnotic conditional PA / step guideline'
      : anxiolyticRequest.some(b => b.policyId === p.id) ? 'Anxiolytic request guideline'
      : psoriasisRequest.some(b => b.policyId === p.id) ? 'Psoriasis request guideline'
      : diagnosisRequest.some(b => b.policyId === p.id) ? 'Diagnosis-linked request guideline'
      : packetReference.some(b => b.policyId === p.id) ? 'Packet PA guideline'
      : duplication.some(b => b.policyId === p.id) ? 'Duplication reference'
      : p.id === uhcTestStripPolicyId ? 'Test strip QL reference' : 'QL reference');
    if (genericDabigatran) {
      sections.unshift('<p><strong>Generic dabigatran oral capsules:</strong> The formulary lists PA. Product-specific approval criteria are unverified.</p>');
      references.unshift(genericDabigatran);
      referenceLabels.unshift('Generic PA formulary');
    }
    if (!paRows.length && !primary.length && !packetReference.length && guidance) {
      sections.unshift(clinicalGuidanceContent(guidance, true));
      references.unshift(guidance); referenceLabels.unshift('Clinical reference');
    }
    if (reviewedAgeRow?.sourceUrl) {
      references.unshift(reviewedAgeRow);
      referenceLabels.unshift('PA formulary');
    } else if (paRows.length && !primary.length && !genericDabigatran) {
      const [record] = paRows;
      const relatedIds = new Set((group.records || []).filter(r => r.planId === state.planId && !r.isStatewideReference).flatMap(r => r.policySources || []).map(p => p.policyId));
      const related = policies.find(p => !uhcDuplicationPolicies.has(p.policyCode) && relatedIds.has(p.id));
      if (related && !bindings.some(b => b.role === 'korlym_reference' || (b.policyId === related.id && b.role === 'methadose_pain_reference'))) { references.unshift(related); referenceLabels.unshift('PA source'); }
      else if (record?.sourceUrl) { references.unshift(record); referenceLabels.unshift('PA formulary'); }
    }
    for (const binding of bindings) {
      const reference = uhcStandalonePolicyReferences.get(binding.role);
      if (!reference) continue;
      const policy = policies.find(item => item.id === binding.policyId);
      if (!policy || references.some(item => item.id === policy.id)) continue;
      references.push(policy);
      referenceLabels.push(reference.label);
      if (binding.role !== 'general_nebulizer_reference') sections.push(`<p>${escapeHtml(reference.scope)}</p>`);
    }
    return {html: sections.join(''), references, referenceLabels};
  }

  async function populateCardClinical(details) {
    if (!details.open || details.dataset.loaded === 'true' || details.dataset.loading === 'true') return;
    const entry = cardClinicalGroups.get(details.dataset.cardClinical);
    if (!entry || entry.planId !== state.planId) return;
    if (entry.bannerGuide || entry.bannerIcs) return;
    const {group, policies, guidance} = entry;
    const target = details.querySelector('.card-clinical-content');
    if (!policies.length && !(state.planId === 'uhc-community-az' && (group.records || []).some(r => r.planId === state.planId && !r.isStatewideReference && (['required','conditional'].includes(r.pa) || r.qlAmount || r.qlDays || r.uhcClinicalBindings?.some(b => b.role === 'hypnotic_request'))))) return;
    details.dataset.loading = 'true';
    target.innerHTML = '<p role="status">Loading clinical criteria…</p>';
    try {
      const bindings = uhcGroupBindings(group);
      if (state.planId === 'uhc-community-az' && (group.records || []).some(r => r.planId === state.planId && !r.isStatewideReference && (['required','conditional'].includes(r.pa) || r.qlAmount || r.qlDays || r.uhcClinicalBindings?.some(b => b.role === 'hypnotic_request')))) {
        const content = await uhcClinicalContent(group, bindings, guidance);
        if (target.isConnected === false) return;
        target.innerHTML = content.html;
        const references = details.querySelector('.card-pa-references');
        if (references) references.innerHTML = content.references.map((p,i) => cardPaReference(p, content.referenceLabels[i])).join('');
        details.dataset.loaded = 'true';
        return;
      }
      let sections = [];
      let activeSource = guidance;
      // DEC-12/13: use explicitly reviewed exact-plan stage pages for these rows.
      // Never fall back to other product, statewide policy or stage if the reviewed branch is missing.
      const exactRows = (group.records || []).filter(r => r.planId === 'banner-ufc' && !r.isStatewideReference);
      const scoped = state.planId === 'banner-ufc' && exactRows.some(r => r.reviewedBannerBranches);
      if (scoped) {
        const bindings = exactRows.map(r => r.reviewedBannerBranches);
        const unique = new Set(bindings.map(b => JSON.stringify(b)));
        if (bindings.some(b => !b) || unique.size !== 1) throw new Error('Mixed Banner branch scope');
        const b = bindings[0], policy = policies.find(p => p.id === b.policyId && p.planId === 'banner-ufc');
        if (!policy) throw new Error('Missing exact Banner policy');
        const source = await loadClinicalSource(policy);
        const stages = b.indicationPages || (b.painPages ? [['', 1100, 'Cancer-related pain / hospice / end-of-life (stage not separately labeled)'], ['Initial Authorization', 1104, 'Noncancer pain / non-hospice / non-end-of-life'], ['Reauthorization', 1110, 'Noncancer pain / non-hospice / non-end-of-life']] : b.unstagedPage ? [['', b.unstagedPage]] : [['Initial Authorization', b.initialPage], ['Reauthorization', b.renewalPage]]);
        const selected = stages.map(([stage,page,heading,diagnosisHint]) => {
          const matches = source.branches.filter(branch => branch.stage === stage && branch.sourcePage === page && new RegExp('(?:^|[^a-z])'+b.product+'(?:[^a-z]|$)', 'i').test(branch.product) && (!diagnosisHint || branch.product.toLowerCase().includes(diagnosisHint.toLowerCase())));
          if (matches.length !== 1) throw new Error('Exact Banner product/stage branch not verified');
          if (b.quantityExceptionOnly && (b.policyId !== 'banner-policy-12-1690' || !/^Brand suboxone,/i.test(matches[0].product) || !/Guideline Type\s+Quantity Limit/i.test(matches[0].text) || !/requests exceeding\s+24 mg/i.test(matches[0].text) && stage === 'Initial Authorization' || !/requests exceeding\s+16 mg/i.test(matches[0].text) && stage === 'Reauthorization')) throw new Error('Unverified Banner quantity-exception branch');
          let text = matches[0].text.split(/\n\s*2\s*\.\s*Revision History/i)[0];
          if (b.omitNintedanibNonpreferredStep) {
            if (b.policyId !== 'banner-policy-12-589' || !/generic nintedanib 100mg and 150mg capsules \(Sandoz mfg\)/i.test(matches[0].product)) throw new Error('Sandoz product scope not verified');
            const cleaned = text.replace(/^(?:=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
            const nonpreferred = /\n\s*AND\s*\n\s*\d+\s*-\s*For Non-Preferred requests:/i.exec(cleaned);
            if (!nonpreferred) throw new Error('Reviewed nonpreferred-only step not verified');
            text = cleaned.slice(0, nonpreferred.index);
          }
          if (b.omitEltrombopagNonpreferredStep) {
            if (b.policyId !== 'banner-policy-12-1798' || b.product !== 'generic eltrombopag tablet' || !/^Preferred:\s*(?:Nplate,\s*)?generic eltrombopag tablet,/i.test(matches[0].product) || ![1798,1799,1800,1801,1802].includes(page) || !stage) throw new Error('Eltrombopag scope not verified');
            const cleaned = text.replace(/^(?:=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
            const nonpreferred = /\n\s*AND\s*\n\s*\d+\s*-\s*For Non-Preferred Drug requests:/i.exec(cleaned);
            if (!nonpreferred) throw new Error('Reviewed eltrombopag nonpreferred-only step not verified');
            text = cleaned.slice(0, nonpreferred.index);
          }
          if (b.scopeAimovigAdult && stage === 'Initial Authorization') {
            if (b.policyId !== 'banner-policy-12-305' || b.product !== 'Aimovig' || page !== 305 || !/^Aimovig, Ajovy, Emgality 120 mg\/ml Diagnosis Preventive Treatment of Migraine/i.test(matches[0].product)) throw new Error('Aimovig adult scope not verified');
            const cleaned = text.replace(/^(?:=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
            const age = /2\s*-\s*One of the following:\s*2\.1 Patient is 18 years of age or older\s*OR\s*2\.2 Both of the following \(applies to Ajovy for episodic migraines ONLY\):\s*•\s*Patient is between 6-17 years of age\s*•\s*Patient weight at least 45 kg or greater(?=\s*AND\s*3\s*-)/i;
            if (!age.test(cleaned)) throw new Error('Reviewed Ajovy-only pediatric alternative not verified');
            text = cleaned.replace(age,'2 - Patient is 18 years of age or older');
          }
          if (b.omitNplateNonpreferredStep && stage) {
            if (b.policyId !== 'banner-policy-12-1798' || !/^Preferred:\s*Nplate,/i.test(matches[0].product) || ![1798,1799].includes(page)) throw new Error('Nplate preferred product scope not verified');
            const cleaned = text.replace(/^(?:=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
            const nonpreferred = /\n\s*AND\s*\n\s*\d+\s*-\s*For Non-Preferred Drug requests:/i.exec(cleaned);
            if (!nonpreferred) throw new Error('Reviewed Nplate nonpreferred-only step not verified');
            text = cleaned.slice(0, nonpreferred.index);
          }
          if (b.omitElelysoVprivStep) {
            if (b.policyId !== 'banner-policy-12-704' || page !== 706 || stage !== 'Initial Authorization' || b.product !== 'Elelyso' || !/^PREFERRED:\s*Elelyso;\s*NON-PREFERRED:\s*Vpriv/i.test(matches[0].product)) throw new Error('Unverified Elelyso branch');
            const cleaned = text.replace(/^(?:=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
            const vpriv = /\n\s*AND\s*\n\s*2\s*-\s*For VPRIV requests ONLY:/i.exec(cleaned);
            if (!vpriv) throw new Error('Unverified Vpriv-only prerequisite');
            text = cleaned.slice(0, vpriv.index);
          }
          if (b.scopePahGeneric && stage === 'Initial Authorization') {
            if (b.policyId !== 'banner-policy-12-1422' || page !== 1422 || !['generic sildenafil tablets','generic tadalafil','Orenitram','Yutrepia'].includes(b.product)) throw new Error('Unverified PAH scope');
            const cleaned = text.replace(/^(?:=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
            const age = /2\s*-\s*One of the following:\s*2\.1 Patient is 18 years of age or older\s*OR\s*2\.2 One of the following:[\s\S]*?(?=\n\s*AND\s*\n\s*3\s*-\s*Pulmonary arterial hypertension is symptomatic)/i;
            const nonpreferred = /\n\s*AND\s*\n\s*6\s*-\s*If the patient is requesting a non-preferred product/i;
            if (!age.test(cleaned) || !nonpreferred.test(cleaned)) throw new Error('PAH exact conditional steps not verified');
            text = cleaned.slice(0, nonpreferred.exec(cleaned).index).replace(age,'2 - Patient is 18 years of age or older');
          }
          if (b.omitGranisolStep) {
            if (b.policyId !== 'banner-policy-12-129' || b.product !== 'Anzemet' || stage || ![129,130,131].includes(page)) throw new Error('Unverified Anzemet scope');
            const cleaned = text.replace(/^(?:=== PDF PAGE \d+ ===|Page \d+)\s*$/gmi, '');
            const only = /\n\s*AND\s*\n\s*2\s*-\s*For Granisol requests ONLY, BOTH of the following:/i.exec(cleaned);
            if (!only) throw new Error('Granisol-only condition not verified');
            text = cleaned.slice(0, only.index);
          }
          if (b.omitOtherProductStep) {
            const otherStep = /\n\s*AND\s*\n\s*3\s*-\s*For Norliqva and Sdamlo requests ONLY:/i.exec(text);
            if (!otherStep) throw new Error('Reviewed other-product step not verified');
            text = text.slice(0, otherStep.index);
          }
          const stageHeading = heading && !stage && !/stage not separately labeled/i.test(heading) && b.policyId === 'banner-policy-12-1530' ? heading + ' (stage not separately labeled)' : heading;
          // A product heading can start on the page before its renewal criteria.
          const sourcePage = stage === 'Reauthorization' ? (b.renewalCriteriaPage ?? page) : page;
          return {...matches[0], sourcePage, heading: stageHeading, text};
        });
        const exclusion = b.exclusionPage ? source.branches.filter(branch => branch.sourcePage === b.exclusionPage && /^All products\b/i.test(branch.product) && /Idiopathic Short Stature/i.test(branch.product)) : [];
        if (b.exclusionPage && exclusion.length !== 1) throw new Error('Missing reviewed exclusion');
        const painScope = b.painPages ? '<p>These criteria apply to pain only. Opioid use disorder authorization is unverified.</p>' : '';
        const conditional = b.painPages ? '<h4>Separate conditional review references</h4><p>Not routine pain PA criteria or OUD approval:</p>' + [[1099,'Concurrent MAT / opioid DUR'],[1111,'Quantity limit review'],[1112,'MME review']].map(([page,label]) => '<p>'+escapeHtml(label)+'</p>'+branchPageLink({sourcePage:page},policy)).join('') : '';
        target.innerHTML = (b.quantityExceptionOnly ? '<h4>Quantity-limit exceptions</h4><p>Applies only to requests exceeding the plan dose threshold, not a routine PA requirement or absolute prescribing limit.</p>' : '') + painScope + (b.unstagedPage ? '<p>Authorization stage is not separately labeled in the source.</p>' : '') + selected.map(branch => (branch.heading ? '<h4>'+escapeHtml(branch.heading)+'</h4>' : '') + cardTextBranchMarkup(branch, policy)).join('') + conditional + (exclusion.length ? '<h4>Separate indication exclusion</h4>'+cardTextBranchMarkup(exclusion[0], policy) : '');
        const references = details.querySelector('.card-pa-references');
        if (references) references.innerHTML = cardPaReference(policy, b.quantityExceptionOnly ? 'Quantity-limit exception guideline' : undefined, b.exactReferencePage);
        details.dataset.loaded = 'true';
        return;
      }
      // Use the selected plan's exact named product branches first. Never
      // concatenate two payer versions into one apparent set of requirements.
      const planPolicies = policies.filter(p => p.planId === state.planId && !uhcDuplicationPolicies.has(p.policyCode));
      const referencePolicies = policies.filter(p => p.planId === 'ahcccs-ffs-aihp');
      for (const candidates of [planPolicies, guidance ? [] : referencePolicies]) {
        for (const policy of candidates) {
          const structured = await loadClinicalSource(policy);
          const branches = matchingClinicalBranches(structured, group);
          if (!branches.length) continue;
          activeSource = policy;
          const seen = new Set();
          sections = branches.filter(branch => {
            const signature = JSON.stringify(branch.fields ? [branch.fields, branch.criteria, branch.notes] : branch.text);
            if (seen.has(signature)) return false;
            seen.add(signature); return true;
          }).map(branch => branch.fields ? cardBranchMarkup(branch, policy) : cardTextBranchMarkup(branch, policy));
          break;
        }
        if (sections.length) break;
      }
      if (!target.isConnected && typeof target.isConnected === 'boolean') return;
      if (sections.length && activeSource?.planId === 'ahcccs-ffs-aihp') {
        sections = [`<details class="result-disclosure statewide-criteria-reference"><summary>${statewideFfsLabel} criteria</summary><div class="result-disclosure-body">${sections.join('')}</div></details>`];
      }
      target.innerHTML = sections.length ? sections.join('') : (guidance ? clinicalGuidanceContent(guidance, true) : '<p>Formatted criteria for this medication are not available. See the PA reference.</p>');
      const reference = details.querySelector('.card-pa-references');
      if (reference && activeSource) reference.innerHTML = cardPaReference(activeSource);
      details.dataset.loaded = 'true';
    } catch (error) {
      target.innerHTML = '<p>Clinical criteria could not be loaded.</p><button type="button" class="text-button" data-retry-card-criteria>Retry clinical criteria</button>';
    } finally { details.dataset.loading = 'false'; }
  }

  function cardPaReference(source, label = 'PA reference', exactPage = source.exactQuantityPage) {
    if (source.planId === 'ahcccs-ffs-aihp') label = statewideFfsLabel + ' reference';
    const chapter = exactPage ? ' · p. ' + exactPage
      : source.recordType === 'policy_index' && source.sourcePage ? ' · chapter p. ' + source.sourcePage : '';
    const destination = exactPage ? {...source, sourcePage: exactPage} : source;
    return `<a class="source-link card-pa-reference" href="${escapeHtml(sourceHref(destination))}" target="_blank" rel="noopener" title="PDF source · ${escapeHtml(source.policyCode || source.name || 'PA source')} · ${escapeHtml(source.sourceEffective || '')}">${escapeHtml(label)} ↗${escapeHtml(chapter)}</a>`;
  }

  function constipationCoverageNote(record) {
    if (constipationGenericRows.has(record.id)) {
      const step = record.id === 'uhc-oct-complete-a75bf7c192276842' ? ''
        : ' Its duplicate rows disagree on step therapy.';
      return `<p class="pa-condition">UHC October 1, 2026 formulary lists PA and a quantity limit.${step} The October 18, 2026 policy says generic is preferred without PA. Current claim requirements are unverified.</p>`;
    }
    if (record.id === uhcLinzessId) {
      return '<p class="pa-condition">UHC October 1, 2026 formulary lists a diagnosis requirement and a quantity limit, with PA unspecified. UHC’s October 18, 2026 policy publishes Linzess PA criteria.</p>';
    }
    if (record.id === bannerLubiprostoneId) {
      return '<p class="pa-condition"><strong>Banner quantity limit:</strong> 180 per 90 days. The formulary does not specify a unit.</p>';
    }
    if (achConstipationLabels.has(record.id)) {
      return '<p class="pa-condition">Arizona Complete Health October 1, 2026 notice lists this option as preferred. Product-specific restrictions are unspecified in the notice.</p>';
    }
    return '';
  }

  function bannerAdhdLimit(record) {
    if (record.planId !== 'banner-ufc') return '';
    if (['banner-full-726809feb6a79584','banner-full-24c168cabe867c51','banner-ufc:statewide:formulary-9599','banner-ufc:statewide:formulary-10095'].includes(record.id) && record.qlAmount === '4' && record.qlDays === '28') return 'QL: 4 patches per 28 days';
    if (record.qlDays !== '30') return '';
    if (['banner-full-fa62279e75a1c387','banner-ufc:statewide:formulary-9601'].includes(record.id) && record.qlAmount === '30') return 'QL: 30 tablets per 30 days';
    if (['banner-full-e7a4e750d4c75cc1','banner-ufc:statewide:formulary-9597'].includes(record.id) && record.qlAmount === '30') return 'QL: 30 capsules per 30 days';
    if (['banner-full-a457525bbf1d1d54','banner-ufc:statewide:formulary-9600'].includes(record.id) && record.qlAmount === '120') return 'QL: 120 tablets per 30 days';
    return '';
  }

  const tirosintSolutionLabel = 'Tirosint-SOL (Levothyroxine Sodium Oral Solution)';
  const tirosintSolutionSource = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=5d378add-f13d-40f2-99dc-0f2340ab44b7';

  function formularyStrengthDetails(group, title) {
    const units = /\d(?:[\d.,/-]*\d)?\s*(?:mcg|mg|grams?|gm|g|units?|meq|%)(?![a-z])/i;
    const rows = new Map();
    for (const record of group.records) {
      // Only quote dated, direct formulary rows. Baseline mappings, billing
      // units, reference aliases and statewide projections have different scopes.
      if (record.isStatewideReference || record.baselineSource || record.reviewedPresentation
          || record.sourceEffective !== '2026-10-01' || !record.sourcePage
          || !['banner-ufc', 'uhc-community-az'].includes(record.planId)) continue;
      const product = readableMedicationName(record.name.split(/\s+\((?:brand|generic) for /i)[0]);
      if (!units.test(product) || normalize(title).includes(normalize(product))) continue;
      const url = sourceHref(record);
      rows.set(product + '|' + url, `<li>${escapeHtml(product)} · <a href="${escapeHtml(url)}" target="_blank" rel="noopener">p. ${Number(record.sourcePage)}</a></li>`);
    }
    return rows.size ? `<details class="result-disclosure"><summary>Strengths listed in the plan formulary</summary><ul>${[...rows.values()].join('')}</ul></details>` : '';
  }

  function medicationGroupCard(group) {
    if (group.identityOnly) return `<article class="result-card">
      <h3>${escapeHtml(tirosintSolutionLabel)}</h3>
      <details><summary>Labeled concentrations (mcg/mL)</summary><p>13, 25, 37.5, 44, 50, 62.5, 75, 88, 100, 112, 125, 137, 150, 175 and 200 mcg/mL.</p></details>
      <p>Plan coverage, preference and restrictions are unverified.</p>
      <a class="source-link" href="${escapeHtml(tirosintSolutionSource)}" target="_blank" rel="noopener">FDA drug label ↗</a>
    </article>`;
    const isUhc = state.planId === 'uhc-community-az';
    const isBanner = state.planId === 'banner-ufc';
    const insulinConflict = isBanner && group.records.find(record => bannerInsulinConflicts.has(record.id));
    const bannerGuide = isBanner && !group.policyOnly ? bannerRespiratoryGuide(group) : null;
    const bannerIcs = isBanner && group.records.some(record => reviewedCardPresentation(record)?.relatedBannerIcs)
      && state.data.policies.find(policy => policy.id === 'banner-guide-ics-nonpreferred');
    const achSmart = state.planId === 'az-complete-health' && group.records.some(record => achSmartRecords.has(record.id));
    const achNotice = group.records.find(record => achConstipationLabels.has(record.id));
    const constipationGeneric = group.records.find(record => constipationGenericRows.has(record.id));
    const constipationBrand = group.records.find(record => record.id === uhcMotegrityId);
    const linzess = group.records.find(record => record.id === uhcLinzessId);
    const title = achNotice ? achConstipationLabels.get(achNotice.id)
      : linzess ? 'Linzess (linaclotide) oral capsules'
      : constipationBrand ? 'Prucalopride oral tablets (Motegrity)'
      : constipationGeneric ? 'Lubiprostone oral capsules (Amitiza reference)' : group.label;
    const achFemring = state.planId === 'az-complete-health' && group.records.some(record =>
      record.id === 'ach-json-848333' || record.id === 'ach-json-848343');
    const noticeOnly = group.records.some(record => record.reviewedPresentation?.policyUnverified);
    const guide = group.policyOnly ? group.guide : (insulinConflict || bannerIcs || noticeOnly || achFemring) ? null : bannerGuide || clinicalGuidanceFor(group);
    const statewideGlp1 = isUhc && guide?.policyCode === 'GL-749236' && group.isStatewide
      && group.records.every(record => record.isStatewideReference);
    const guidance = statewideGlp1 ? {...guide, planId: 'ahcccs-ffs-aihp'} : guide;
    const policies = group.policyOnly || insulinConflict || bannerIcs || noticeOnly ? [] : bannerGuide ? [bannerGuide]
      : linkedPolicyPanels(group, true).filter(policy => !statewideGlp1 || policy.planId === 'ahcccs-ffs-aihp');
    const key = group.key || group.label;
    cardClinicalGroups.set(key, {group, policies, guidance, bannerGuide, bannerIcs, planId: state.planId});
    const restriction = state.planId === 'uhc-community-az' && (group.records || []).find(r => r.planId === state.planId && !r.isStatewideReference && (['required','conditional'].includes(r.pa) || r.qlAmount || r.qlDays || r.uhcClinicalBindings?.some(b => b.role === 'hypnotic_request')));
    const agePaFormulary = isUhc && restriction &&
      (restriction.id === uhcLowStrengthAlbuterolId || uhcAgePaCardLabels.has(restriction.id)) && uhcAgeEightPa(restriction);
    const reference = (isUhc ? (agePaFormulary ? restriction : policies.find(p => p.planId === state.planId) || restriction) : guidance) || guidance || policies.find(p => p.planId === state.planId) || policies[0];
    const psoriasisGuideline = reference?.policyCode === 'GL-140713' && group.records?.some(record => record.uhcClinicalBindings?.some(binding => binding.role === 'psoriasis_request'));
    const psoriasisOintmentReference = reference?.policyCode === 'GL-140713' && group.records?.some(record => record.uhcClinicalBindings?.some(binding => binding.role === 'psoriasis_ointment_reference'));
    const packetGuideline = reference?.policyCode === 'GL-255208' && group.records?.some(record =>
      record.uhcClinicalBindings?.some(binding => binding.role === 'packet_reference'));
    const glucoseSupply = isUhc && group.records.find(record => uhcReviewedGlucoseSupplies.has(record.id));
    const glucoseDisplay = glucoseSupply && uhcReviewedGlucoseSupplies.get(glucoseSupply.id);
    const glucosePolicy = glucoseDisplay && policies.find(policy =>
      glucoseDisplay.strip ? policy.id === uhcTestStripPolicyId : glucoseDisplay.meterPolicy && policy.id === uhcMeterPolicyId);
    const exactStripQuantity = isUhc && uhcGroupBindings(group)
      .find(binding => binding.policyId === uhcTestStripPolicyId && binding.exactQuantityPage);
    const stripQuantity = isUhc && (exactStripQuantity || group.records.some(record => isUhcOctoberRow(record) && uhcReviewedTestStrips.has(record.id)))
      && policies.find(policy => policy.id === uhcTestStripPolicyId);
    const hypnoticGuideline = reference?.policyCode === 'GL-637194' && group.records.some(r => r.uhcClinicalBindings?.some(b => b.role === 'hypnotic_request'));
    const anxiolyticGuideline = reference?.policyCode === 'GL-140805' && group.records.some(r => r.uhcClinicalBindings?.some(b => b.role === 'anxiolytic_request'));
    const scopedQuantity = isUhc && reference?.policyCode === 'GL-140667';
    const insulinQuantity = state.planId === 'uhc-community-az' && reference
      && !group.records?.some(record => ['required', 'conditional'].includes(record.pa))
      && group.records?.some(record => (uhcInsulinAndSupplyLabels.has(record.id) || reviewedCardPresentation(record)?.uhcFormRx)
        && record.uhcClinicalBindings?.some(binding => binding.policyId === reference.id
          && ['quantity', 'global_quantity'].includes(binding.role)));
    const reviewedQuantity = isUhc && reference && !group.records.some(record => ['required', 'conditional'].includes(record.pa))
      && group.records.some(record => uhcReviewedProductGroups.has(record.id)
        && record.uhcClinicalBindings?.some(binding => binding.policyId === reference.id
          && ['quantity', 'global_quantity'].includes(binding.role)));
    const brandCapsuleReference = isUhc && reference?.policyCode === 'GL-231255'
      && group.records.some(record => record.id === 'uhc-oct-complete-009ca23afd12966f');
    const constipationPolicy = (constipationGeneric || linzess) && state.data.policies.find(policy => policy.id === constipationPolicyId);
    const bannerQuantityException = isBanner && group.records.some(r => r.reviewedBannerBranches?.quantityExceptionOnly);
    const exactBannerReference = isBanner && group.records.find(r => r.reviewedBannerBranches?.exactReferencePage)?.reviewedBannerBranches;
    const exactBannerPolicy = exactBannerReference && policies.find(p => p.id === exactBannerReference.policyId);
    const refs = exactBannerPolicy ? cardPaReference(exactBannerPolicy, 'PA reference', exactBannerReference.exactReferencePage) : bannerQuantityException && reference ? cardPaReference(reference, 'Quantity-limit exception guideline') : bannerIcs ? cardPaReference(bannerIcs, 'Related inhaled corticosteroid guidance') : constipationPolicy ? cardPaReference(constipationPolicy,
      linzess ? 'Linzess PA guideline' : 'UHC October 18 policy')
      : glucosePolicy ? cardPaReference(glucosePolicy, glucoseDisplay.strip ? 'Test strip PA and QL guideline' : 'Nonpreferred meter PA guideline')
      : stripQuantity ? cardPaReference({...stripQuantity, exactQuantityPage: exactStripQuantity?.exactQuantityPage}, 'Test strip QL reference')
      : reference ? cardPaReference(reference, psoriasisGuideline ? 'Psoriasis request guideline'
      : psoriasisOintmentReference ? 'UHC psoriasis guideline (ointment only)'
      : hypnoticGuideline ? 'Hypnotic conditional PA / step guideline'
      : anxiolyticGuideline ? 'Anxiolytic request guideline'
      : packetGuideline ? 'Packet PA guideline'
      : agePaFormulary ? 'PA formulary'
      : scopedQuantity || insulinQuantity || reviewedQuantity ? 'QL reference'
      : brandCapsuleReference ? 'Brand nonpreferred reference'
      : reference.policyCode === 'GL-231255' && group.records.some(record => reviewedCardPresentation(record)?.generalPa)
      ? 'General nonpreferred PA reference'
      : isUhc && uhcDuplicationPolicies.has(reference.policyCode) ? 'Duplication reference' : 'PA reference') : '';
    const exactScopedRows = isUhc && (group.records || []).some(record =>
      record.planId === state.planId && !record.isStatewideReference &&
      (uhcAgeEightPa(record) || record.uhcClinicalBindings?.some(binding => ['age_scoped', 'packet_reference'].includes(binding.role))));
    const bannerProducts = isBanner ? group.records.filter(record => [
      'banner-pcp-nov10-038', 'banner-pcp-nov10-039', 'banner-full-a2a4d1dc0085c78f'
    ].includes(record.id) && !record.isStatewideReference) : [];
    const uhcStepRows = isUhc ? group.records.filter(record => record.planId === state.planId && !record.isStatewideReference
      && record.sourceEffective === '2026-10-01' && uhcFormularySteps.has(record.id)) : [];
    const constipationRows = group.records.filter(record => constipationGenericRows.has(record.id) ||
      [uhcMotegrityId, uhcLinzessId, bannerLubiprostoneId, achNotice?.id].includes(record.id));
    const reviewedExactRows = group.records.filter(record => !record.isStatewideReference
      && reviewedCardPresentation(record) && !record.baselineSource);
    const conflictGroup = reviewedExactRows.some(record => reviewedCardPresentation(record)?.conflict);
    const exactDisplayRows = conflictGroup ? group.records.filter(record => !record.isStatewideReference)
      : reviewedExactRows.length === 2 && reviewedExactRows.every(record => bannerEpiPenIds.has(record.id))
      ? reviewedExactRows.slice(0, 1) : reviewedExactRows;
    const directRows = group.records.filter(record => !record.isStatewideReference);
    const mixedPlanRows = directRows.filter(record => !record.baselineSource);
    const scopeFields = ['coverage','preferred','pa','step','qlAmount','qlDays','ageRestrictionText','paExceptionText','stepText'];
    const showStatewideRow = group.isStatewide && (!mixedPlanRows.length || mixedPlanRows.some(record =>
      scopeFields.some(field => (record[field] || '') !== (group.statewideRecord[field] || ''))
      || (record.pa === 'conditional' && record.paText !== group.statewideRecord.paText)));
    const planScopeLabel = isBanner ? 'Banner formulary' : isUhc ? 'UHC formulary' : 'Arizona Complete Health notice';
    let rows = directRows;
    if (constipationRows.length) rows = constipationRows;
    else if (exactDisplayRows.length) rows = exactDisplayRows;
    else if (bannerProducts.length) rows = bannerProducts;
    else if (group.isStatewide && !exactScopedRows && !uhcStepRows.length) {
      rows = showStatewideRow ? [...mixedPlanRows, group.statewideRecord] : mixedPlanRows;
    }
    // Keep every strength-specific plan row visible alongside any shared reference.
    if (directRows.some(record => record.baselineSource)) {
      rows = [...new Set([...rows, ...directRows.filter(record => record.baselineSource)])];
      if (group.isStatewide && !rows.includes(group.statewideRecord)) rows.push(group.statewideRecord);
    }
    const conditions = [...new Set(rows.flatMap(record => [
      ['required', 'conditional'].includes(record.pa) && !bannerEpiPenIds.has(record.id) && !reviewedCardPresentation(record)?.note?.includes(tiotropiumContinuation) && !record.baselineSource && !constipationGenericRows.has(record.id) && !(isUhc && uhcAgeEightPa(record)) ? record.paText : '', record.paExceptionText, record.ageRestrictionText
    ].filter(text => text && text !== 'PA is printed in at least one source row.').map(text =>
      !record.baselineSource && group.isStatewide && mixedPlanRows.length ? (record.isStatewideReference ? 'AHCCCS statewide reference' : planScopeLabel) + ' · ' + text : text)))];
    const labeledCaplets = isUhc && rows.some(record => uhcReviewedProductGroups.get(record.id)?.labelId);
    const preferredNdcs = state.planId === 'banner-ufc' ? bannerAlbuterolPreferredNdcs(group) : [];
    const hideEmptyPa = insulinConflict || noticeOnly || (preferredNdcs.length && !guidance && !policies.length && !conditions.length
      && !group.records.some(record => ['required', 'conditional'].includes(record.pa) || record.policySource));
    const compact = compactPresentation(group);
    const packageQualifiers = compact ? [...new Set(rows.map(r => reviewedCardPresentation(r))
      .map(p => p?.packageQualifier).filter(Boolean))] : [];
    const commonLabelUrl = compact && rows.length && rows.every(r => reviewedCardPresentation(r)?.labelUrl === compact.labelUrl)
      ? compact.labelUrl : '';
    return `<article class="result-card${compact ? ' compact-prescription' : ''}">
      <div class="prescribing-details">
      <h3>${escapeHtml(preferredNdcs.length ? 'Albuterol HFA inhaler' : dosageFormHeading(group, title))}</h3>
      ${compact ? `<p class="package-line">${escapeHtml(compact.packageLine)}</p>` : ''}
      ${packageQualifiers.map(note => `<p class="pa-condition">${escapeHtml(note)}</p>`).join('')}
      ${commonLabelUrl ? `<p><a class="source-link" href="${escapeHtml(commonLabelUrl)}" target="_blank" rel="noopener">Drug label ↗</a></p>` : ''}
      ${formularyStrengthDetails(group, title)}
      ${[...new Map(group.records.filter(r => r.agePolicyConflict).map(r => [r.agePolicyConflict.url, r.agePolicyConflict])).values()].map(conflict =>
        `<p class="pa-condition">${escapeHtml(conflict.note)} <a class="source-link" href="${escapeHtml(conflict.url)}" target="_blank" rel="noopener">Banner guideline · PDF page ${escapeHtml(conflict.page)} ↗</a></p>`).join('')}
      ${labeledCaplets ? '<p>Acetaminophen 250 mg / aspirin 250 mg / caffeine 65 mg per caplet.</p>' : ''}
      </div>
      <div class="coverage-options">
      ${rows.map(record => {
        const insulinWarning = insulinConflict && bannerInsulinConflicts.get(record.id);
        if (insulinWarning) return `<div class="chips"><span class="chip warning">Banner source conflict</span></div>
          <p class="pa-condition">${escapeHtml(insulinWarning.reason)} Exact pen coverage and preference are unverified.</p>`;
        const nebulizerNote = isUhc && uhcNebulizedAlbuterol.get(record.id)?.note;
        const insulinLabel = state.planId === 'uhc-community-az' && uhcInsulinAndSupplyLabels.get(record.id);
        const reviewed = isUhc && uhcReviewedProductGroups.get(record.id);
        const presentation = reviewedCardPresentation(record);
        const label = rows.length > 1 && (presentation?.option || constipationGenericRows.get(record.id) ||
          (record.id === uhcMotegrityId ? 'Brand Motegrity oral tablets' : '') || reviewed?.label || insulinLabel || record.coverageProductLabel
          || record.uhcClinicalBindings?.find(binding => binding.productLabel)?.productLabel || ((conflictGroup || record.baselineSource) && record.name)
          || (group.isStatewide && mixedPlanRows.includes(record) && readableMedicationName(record.name)));
        const exactAge = isUhc && uhcAgeEightPa(record)
          ? '<p class="pa-condition">PA required at age 8 and older.</p>'
          : isUhc && record.id === 'uhc-oct-complete-d37573826a734ebb'
          ? '<p class="pa-condition">The formulary prints a PA flag and an age-8 PA condition. PA scope below age 8 is unverified.</p>'
          : reviewed && record.rawRestrictions?.includes('Members >= 8 years of age')
          ? '<p class="pa-condition">The formulary says PA applies at age 8 and older, with an exemption at age 6 and older for prescriptions by a psychiatric clinician, behavioral health pediatrician, or other behavioral health provider.</p>' : '';
        const avivaConflict = isUhc && isUhcOctoberRow(record) && record.id === uhcAvivaDeviceId;
        const gvoke = isUhc && isUhcOctoberRow(record) && uhcGvokePresentations.get(record.id);
        const productLabelLink = reviewed?.labelId
          ? ` · <a class="source-link" href="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=${escapeHtml(reviewed.labelId)}" target="_blank" rel="noopener">Drug Facts ↗</a>` : '';
        const step = uhcStepRows.includes(record) ? uhcFormularySteps.get(record.id) : '';
        const continuedUse = isUhc && record.id === 'uhc-oct-complete-de1ca42f17826905' && uhcAgeEightPa(record)
          && record.rawRestrictions?.includes('Continued use of two or more drugs in this class may require prior authorization')
          ? '<p class="pa-condition">Continued use of two or more drugs in this class may require PA.</p>' : '';
        const limit = !bannerAdhdLimit(record) && (bannerProducts.includes(record) || (isBanner && group.isStatewide && mixedPlanRows.includes(record)))
          && /^\d+(?:\.\d+)?$/.test(record.qlAmount) && /^\d+$/.test(record.qlDays)
          ? `<p class="pa-condition"><strong>Quantity limit:</strong> ${escapeHtml(record.qlAmount)} per ${escapeHtml(record.qlDays)} days. The formulary does not specify a unit.</p>` : '';
        const source = coverageSource(record);
        const badges = record.baselineSource ? '' : presentation?.explicitPa ? statusChips({...record, pa: 'required'})
          : constipationGenericRows.has(record.id) ? statusChips({...record, pa: 'not_specified', step: 'not_specified'})
          + '<span class="chip warning">PA sources conflict</span>'
          : achConstipationLabels.has(record.id)
          ? statusChips({...record, coverageCaveat: ''}) : statusChips(record);
        const scope = !source && (presentation?.scope || (group.isStatewide && mixedPlanRows.includes(record) ? planScopeLabel : ''));
        return `${label ? `<p class="coverage-product-label"><strong>${escapeHtml(label)}</strong>${productLabelLink}</p>` : ''}
          ${scope ? `<p class="pa-condition">${escapeHtml(scope)}</p>` : ''}
          ${record.baselineSource ? baselineBadgeRows(record) : `<div class="chips" aria-label="Coverage attributes${label ? ` for ${escapeHtml(label)}` : ''}">${source ? `<span class="chip neutral">${escapeHtml(source.label)}</span>` : ''}${badges}${preferredNdcs.length && record === rows[0] ? '<span class="chip positive">Preferred for listed products</span>' : ''}${step && record.step !== 'specified' ? '<span class="chip warning">Step therapy</span>' : ''}</div>`}
          ${glucoseSupply === record && glucoseDisplay.note ? `<p class="pa-condition"><strong>UHC formulary disagreement:</strong> ${escapeHtml(glucoseDisplay.note)} ${glucoseDisplay.pages.map(page => `<a class="source-link" href="${escapeHtml(sourceHref({...record, sourcePage: page}))}" target="_blank" rel="noopener">PDL p. ${page} ↗</a>`).join(' · ')}</p>` : ''}
          ${record.unverifiedPolicyCode ? '<p class="pa-condition">UHC lists PA. Criteria for this exact presentation are unverified.</p>' : ''}
          ${avivaConflict ? '<p class="pa-condition"><strong>UHC source conflict:</strong> The formulary names the Aviva device and aliases it to a control solution. Exact meter package eligibility is unverified.</p>' : ''}
          ${gvoke ? `<p class="pa-condition"><strong>FDA-labeled presentation:</strong> ${escapeHtml(gvoke.dose)}. UHC does not specify eligible strengths. <a class="source-link" href="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=92385737-dbad-98c5-e053-2995a90a2805" target="_blank" rel="noopener">Drug label ↗</a></p>` : ''}
          ${presentation?.note ? `<p class="pa-condition">${escapeHtml(presentation.note)}</p>` : ''}
          ${record.achProviderRule ? `<p class="pa-condition">${escapeHtml(record.achProviderRule.text)} <a class="source-link" href="${escapeHtml(record.achProviderRule.sourceUrl)}" target="_blank" rel="noopener">Plan PA rule ↗</a></p>` : ''}

          ${presentation?.deviceSourceUrl ? `<p><a class="source-link" href="${escapeHtml(presentation.deviceSourceUrl)}" target="_blank" rel="noopener">Device reference ↗</a></p>` : ''}
          ${presentation?.billingUrl ? `<p><a class="source-link" href="${escapeHtml(presentation.billingUrl)}" target="_blank" rel="noopener">Plan billing notice ↗</a></p>` : ''}
          ${presentation?.labelUrl && !commonLabelUrl ? `<p><a class="source-link" href="${escapeHtml(presentation.labelUrl)}" target="_blank" rel="noopener">Drug label ↗</a></p>` : ''}
          ${constipationCoverageNote(record)}${exactAge}${continuedUse}${limit}${nebulizerNote ? `<p class="pa-condition">${escapeHtml(nebulizerNote)}</p>` : ''}
          ${step ? `<p class="pa-condition"><strong>Step therapy:</strong> ${escapeHtml(step)} <a class="source-link" href="${escapeHtml(sourceHref({...record, sourcePage: 36}))}" target="_blank" rel="noopener">UHC formulary · step table ↗</a></p>` : ''}`;
      }).join('')}
      </div>
      ${achFemring ? '<p class="pa-condition">Arizona Complete Health’s product-specific approval criteria are unverified.</p>' : ''}
      ${achSmart ? `<p class="pa-condition">Arizona Complete Health’s SMART asthma notice covers the authorized generic and Teva generic effective October 1, 2026. The notice does not specify strengths, NDCs, preference, PA, step therapy or quantity limits. <a class="source-link" href="${achSmartNoticeUrl}" target="_blank" rel="noopener">Plan notice ↗</a></p>` : ''}
      ${linzess || achNotice?.id === 'ach-notice-13846' ? '<p class="pa-condition">AHCCCS statewide reference lists PA.</p>' : ''}
      <div class="card-source-access">${sourcesLink(group)}</div>
      ${preferredNdcs.length ? `<details class="result-disclosure">
        <summary>View ${preferredNdcs.length} preferred NDCs</summary>
        <div class="result-disclosure-body"><ul>${preferredNdcs.map(ndc => `<li>${escapeHtml(ndc)}${['00254100752', '72572001401'].includes(ndc) ? ' · FDA lists this package as discontinued' : ''}</li>`).join('')}</ul></div>
      </details>` : ''}
      ${hideEmptyPa ? '' : `<details class="clinical-details result-disclosure" data-card-clinical="${escapeHtml(key)}">
        <summary><span>Clinical details &amp; PA criteria</span><span class="card-pa-references">${refs}</span></summary>
        <div class="result-disclosure-body">
          ${conditions.map(text => `<p class="pa-condition">${escapeHtml(text)}</p>`).join('')}
          ${uhcRestrictionSummary(group)}
          <div class="card-clinical-content">${guidance ? clinicalGuidanceContent(guidance, true) : !policies.length ? '<p>Formatted criteria for this medication are not available.</p>' : ''}
          ${bannerIcs ? '<p>Banner’s class guideline mentions fluticasone propionate as a trial alternative. The selected formulary row does not specify PA.</p>' : ''}
          ${bannerGuide ? `<p>${escapeHtml(bannerGuide.guidelineCaution)} <a class="source-link" href="${escapeHtml(bannerGuide.sourceTextUrl)}" target="_blank" rel="noopener">Original policy text ↗</a></p>` : ''}</div>
        </div>
      </details>`}
    </article>`;
  }

  function medicationSortName(group) {
    // Standard prescribable names already put release/strength after the
    // medicine. Preserve numbers that are genuinely part of its name.
    return group.label;
  }

  function render() {
    const selectedPlan = state.planId;
    if (!selectedPlan) {
      el.resultGrid.innerHTML = '';
      el.resultCount.textContent = '0';
      el.planStatus.textContent = '';
      el.planEvidence.hidden = true;
      el.effectiveDate.textContent = '';
      el.criteriaResults.innerHTML = '';
      el.criteriaCount.textContent = '';
      el.loadingState.hidden = false;
      el.loadingState.textContent = 'Select an insurance plan to see medication results.';
      el.emptyState.hidden = true;
      el.showMore.hidden = true;
      return [];
    }
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
    cardSourceGroups.clear();
    const matchingRecords = filteredRecords();
    const medicationRows = matchingRecords.filter(r => r.recordType === 'formulary');
    // Include the other confirmed products in a matching medication group,
    // while preserving explicit coverage/category filters.
    const allGroups = planMedicationGroups();
    const matchedIds = new Set(medicationRows.map(r => r.id));
    const groups = allGroups.filter(group => group.records.some(record => matchedIds.has(record.id)))
      .map(group => {
        if (!state.coverage && !state.category && !state.subcategory) return group;
        const records = group.records.filter(record => matchesCoverage(record)
          && matchesCategory(record, state.category)
          && (!state.subcategory || matchesSubcategory(record.subcategory, state.subcategory)));
        const statewideRecord = group.isStatewide && records.find(record => record.isStatewideReference);
        return {...group, records, isStatewide: Boolean(statewideRecord), statewideRecord};
      }).filter(group => group.records.length);
    // Order the complete matching set before taking the visible page.
    const direction = state.sort === 'za' ? -1 : 1;
    const collator = new Intl.Collator('en', {sensitivity: 'base', numeric: true});
    if (!state.coverage && !state.category && !state.subcategory
        && (normalize(state.term) === normalize(tirosintSolutionLabel)
          || /^(?:tirosint(?:[- ]sol)?|levothyroxine(?: sodium)? oral solution)$/.test(normalize(state.term)))) {
      groups.push({key: 'tirosint-sol-identity', label: tirosintSolutionLabel, identityOnly: true, records: []});
    }
    const records = groups.sort((a, b) => direction * (
      collator.compare(medicationSortName(a), medicationSortName(b))
      || collator.compare(a.label, b.label) || String(a.key).localeCompare(String(b.key), 'en')));
    // Keep matching clinical information accessible in its own panel. Policy,
    // administrative and source records never enter the medication results.
    el.criteriaSearch.value = state.term;
    renderCriteriaLibrary();
    if (!el.criteriaLibrary.hidden && !records.length && normalize(state.term) && el.criteriaResults.innerHTML.trimStart().startsWith('<article')) {
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
    el.sortInput.addEventListener('change', () => { state.sort = el.sortInput.value === 'za' ? 'za' : 'az'; resetLimitAndRender(); });
    el.planStatus.addEventListener('click', (event) => {
      if (!event.target.closest('[data-open-state-reference]')) return;
      state.planId = 'ahcccs-statewide';
      el.planInput.value = displayPlanName(state.data.plans.find((plan) => plan.id === state.planId));
      if (state.coverage === 'policy_index') {
        state.coverage = '';
        el.coverageInput.value = '';
      }
      closeAllComboboxes();
      resetLimitAndRender();
    });
    el.clearFilters.addEventListener('click', () => {
      Object.assign(state, { planId: 'az-complete-health', term: '', selectedMedicationKey: null, category: '', subcategory: '', coverage: '', sort: 'az', limit: PAGE_SIZE });
      el.sortInput.value = 'az';
      el.planInput.value = displayPlanName(state.data.plans.find((plan) => plan.id === state.planId));
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

  function medicationSearchResult(group) {
    if (group.identityOnly) return {
      name: group.label, brands: ['Tirosint-SOL'], coverage: 'not_specified', pa: 'not_specified',
      source: tirosintSolutionSource, source_scope: 'drug_label_only', products: []
    };
    const primary = group.isStatewide ? group.statewideRecord : group.records.length === 1 ? group.records[0] : null;
    const common = field => {
      const values = [...new Set(group.records.map(record => record[field] || 'not_specified'))];
      return values.length === 1 ? values[0] : 'not_specified';
    };
    const product = record => ({
      name: record.name, brand: record.brand || '', coverage: record.coverage,
      medication_id: record.id, rxcui: record.rxnormId || null,
      display_name: record.standardName || record.name,
      display_name_standard: record.standardNameType || null,
      preferred: record.preferred, pa: constipationGenericRows.has(record.id) ? 'conflicting' : record.pa || 'not_specified',
      pa_text: constipationGenericRows.has(record.id)
        ? 'UHC October 1, 2026 PDL lists PA. October 18, 2026 policy lists generic as preferred without PA. Current claim requirements are unverified.'
        : record.paText || '',
      step: record.step, step_text: record.stepText || '', quantity: record.qlAmount || '', quantity_interval: record.qlDays || '',
      source: sourceHref(record), source_effective: record.sourceEffective || '',
      ...(record.baselineSource ? {quantity_limited: record.quantityUncertaintyReason ? null : record.quantityLimited,
        benefit_sources: record.benefitSources, source_updates: record.sourceUpdates} : {}),
      source_scope: record.auditScope || (record.isStatewideReference ? 'statewide_reference' : 'selected_plan')
    });
    return {name: dosageFormHeading(group), brands: group.brands, category: primary?.category || '',
      coverage: primary?.coverage || common('coverage'),
      pa: group.records.some(record => constipationGenericRows.has(record.id)) ? 'conflicting' : primary?.pa || common('pa'),
      source: primary ? sourceHref(primary) : '',
      source_scope: group.isStatewide ? 'statewide_reference' : primary?.auditScope || (group.records.every(record => record.auditScope === 'presumed_2022') ? 'presumed_2022' : group.records.some(record => record.baselineSource) ? 'mixed_sources' : 'selected_plan'),
      products: group.records.map(product)};
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
        if (plan) { state.planId = plan.id; el.planInput.value = displayPlanName(plan); state.selectedMedicationKey = null; }
        if (args.medication !== undefined) { state.term = args.medication; el.medicationInput.value = args.medication; state.selectedMedicationKey = null; }
        if (args.category !== undefined) { state.category = args.category; el.categoryInput.value = args.category; }
        if (args.subcategory !== undefined) { state.subcategory = args.subcategory; el.subcategoryInput.value = args.subcategory; }
        if (args.coverage_status !== undefined) { state.coverage = args.coverage_status; el.coverageInput.value = args.coverage_status; }
        if (!state.planId) return { error: 'Select an insurance plan.' };
        await ensurePlanData(state.planId);
        updateSubcategoryOptions();
        const matches = render();
        return { count: matches.length, plan: state.planId, results: matches.slice(0, 25).map(medicationSearchResult) };
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
    initTheme();
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
      state.sort = el.sortInput.value === 'za' ? 'za' : 'az';
      if (el.planInput.value.trim()) state.planId = resolvePlan(el.planInput.value)?.id || null;
      if (state.planId) populateControls();
      bindEvents();
      bindCriteriaLibrary();
      render();
      registerModelTools();
    } catch (error) {
      el.loadingState.textContent = 'Coverage data could not be loaded. Please refresh or try again later.';
      console.error(error);
    }
  }

  function initTheme() {
    const control = document.getElementById('themeChoice');
    const preference = window.matchMedia('(prefers-color-scheme: dark)');
    const storageKey = 'coverage-theme';
    const toggle = document.getElementById('carbonToggle');
    let previous = 'system';
    try {
      const prior = localStorage.getItem('coverage-theme-previous');
      if (prior === 'dark' || prior === 'light') previous = prior;
      const saved = localStorage.getItem(storageKey);
      if (['dark', 'light', 'carbon'].includes(saved)) control.value = saved;
    } catch { /* Storage can be disabled in private browsing. */ }

    function applyTheme() {
      const carbon = control.value === 'carbon';
      if (!carbon) previous = control.value;
      toggle.setAttribute('aria-pressed', String(carbon));
      document.documentElement.toggleAttribute('data-carbon', carbon);
      document.documentElement.dataset.theme = carbon ? 'dark' : control.value === 'system'
        ? (preference.matches ? 'dark' : 'light')
        : control.value;
    }
    control.addEventListener('change', () => {
      applyTheme();
      try {
        localStorage.setItem('coverage-theme-previous', previous);
        if (control.value === 'system') localStorage.removeItem(storageKey);
        else localStorage.setItem(storageKey, control.value);
      } catch { /* The selection still applies for this page. */ }
    });
    toggle.addEventListener('click', () => {
      control.value = control.value === 'carbon' ? previous : 'carbon';
      control.dispatchEvent(new Event('change'));
    });
    preference.addEventListener('change', applyTheme);
    applyTheme();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
