let currentJob = null;
let inputs = { files: [], recommended: [] };
let packageListEdited = false;
let platformProfiles = [];
let detectedPlatform = '';
let targetReleaseIsAutomatic = true;
let lastAutomaticTargetRelease = '';
let pollTimer = null;
let activityTimer = null;
let storageInfo = null;
const $ = selector => document.querySelector(selector);
const lines = value => value.split(/\n|,/).map(item => item.trim()).filter(Boolean);
const selectedPackages = () => lines(
  $('[name=package_selection_mode]:checked').value === 'manual'
    ? $('[name=pkglist_override]').value
    : $('[name=pkglist]').value
);
const api = (url, options = {}) => fetch(url, options).then(async response => {
  const text = await response.text();
  let body = {};
  try { body = text ? JSON.parse(text) : {}; }
  catch { body = {error: text || `HTTP ${response.status}`}; }
  if (!response.ok) throw new Error(body.error || 'An unexpected error occurred');
  return body;
});

let pendingDialog = null;
function showAppDialog({title, message, confirmText = 'Continue', cancelText = 'Cancel', danger = false, notice = false}) {
  const dialog = $('#app-dialog');
  const confirmButton = $('#app-dialog-confirm');
  const cancelButton = $('#app-dialog-cancel');
  const previousFocus = document.activeElement;

  if (dialog.open && pendingDialog) {
    const previousDialog = pendingDialog;
    pendingDialog = null;
    dialog.close('cancel');
    previousDialog.resolve(false);
  }
  $('#app-dialog-eyebrow').textContent = notice ? 'NOTICE' : 'CONFIRM ACTION';
  $('#app-dialog-title').textContent = title;
  $('#app-dialog-message').textContent = message;
  confirmButton.textContent = notice ? 'Close' : confirmText;
  confirmButton.className = danger ? 'primary dialog-danger' : 'primary';
  cancelButton.textContent = cancelText;
  cancelButton.hidden = notice;
  dialog.returnValue = 'cancel';

  return new Promise(resolve => {
    pendingDialog = {resolve, previousFocus};
    dialog.showModal();
    (danger ? cancelButton : confirmButton).focus();
  });
}

function showNotice(title, message) {
  return showAppDialog({title, message, notice: true});
}

function showConfirmation(title, message, confirmText, danger = false) {
  return showAppDialog({title, message, confirmText, danger});
}

$('#app-dialog-confirm').onclick = () => $('#app-dialog').close('confirm');
$('#app-dialog-cancel').onclick = () => $('#app-dialog').close('cancel');
$('#app-dialog').addEventListener('cancel', event => {
  event.preventDefault();
  $('#app-dialog').close('cancel');
});
$('#app-dialog').addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    event.preventDefault();
    $('#app-dialog').close('cancel');
  }
});
$('#app-dialog').addEventListener('close', () => {
  if (!pendingDialog) return;
  const {resolve, previousFocus} = pendingDialog;
  pendingDialog = null;
  resolve($('#app-dialog').returnValue === 'confirm');
  if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
});

async function copyText(value, button, resetText) {
  try {
    await navigator.clipboard.writeText(value);
    if (button) { button.textContent = 'Copied'; setTimeout(() => { button.textContent = resetText; }, 1200); }
  } catch { await showNotice('Could not copy', 'Clipboard access was denied. Select and copy the text manually.'); }
}

function setReadyCard(selector, ready, text) {
  const card = $(selector);
  card.className = `ready-card ${ready ? 'ready' : 'missing'}`;
  card.querySelector('.ready-icon').textContent = ready ? '✓' : '!';
  card.querySelector('p').textContent = text;
}

let renderedInventoryRevision = null;
let activeUploads = 0;
const INVENTORY_WATCH_MS = 10000;

// Automatic refresh: files can change without this tab doing anything (a
// Cisco download finishing, another browser, files copied into the volume).
// Poll the cheap revision and re-render only when it moves. Never while this
// tab is uploading (upload completion refreshes itself) and never over a
// manual package selection the operator is still editing - that gets a
// notice instead, so a refresh cannot silently discard their choices.
async function checkInventoryChanged() {
  if (document.visibilityState !== 'visible' || activeUploads > 0 || !renderedInventoryRevision) return;
  try {
    const {inventory_revision: revision} = await api('/api/inventory/revision');
    if (revision === renderedInventoryRevision) return;
    if (packageListEdited) $('#inventory-changed').hidden = false;
    else await loadInputs();
  } catch { /* Transient; the next tick retries. */ }
}

async function watchInventory() {
  await checkInventoryChanged();
  setTimeout(watchInventory, INVENTORY_WATCH_MS);
}

// A background tab skips ticks; check as soon as it is looked at again.
document.addEventListener('visibilitychange', checkInventoryChanged);

function renderInputs(data) {
  inputs = data;
  renderedInventoryRevision = data.inventory_revision || null;
  $('#inventory-changed').hidden = true;
  const isoFiles = data.files.filter(file => file.type === '.iso');
  const addOptions = (selector, files) => {
    const list = $(selector); list.replaceChildren();
    files.forEach(file => { const option = document.createElement('option'); option.value = file.path; list.appendChild(option); });
  };
  addOptions('#iso-files', isoFiles);
  const yamlFiles = data.files.filter(file => ['.yaml', '.yml'].includes(file.type));
  addOptions('#yaml-files', yamlFiles);
  addOptions('#all-files', data.files);
  const matrixSelect = $('[name=compatibility_matrix]');
  const selectedMatrix = matrixSelect.value;
  matrixSelect.replaceChildren();
  const noMatrix = document.createElement('option'); noMatrix.value=''; noMatrix.textContent='No matrix uploaded'; matrixSelect.appendChild(noMatrix);
  (data.matrices || []).forEach(path => { const option=document.createElement('option'); option.value=path; option.textContent=path; matrixSelect.appendChild(option); });
  if ([...matrixSelect.options].some(option => option.value === selectedMatrix)) matrixSelect.value=selectedMatrix;

  const iso = isoFiles.length === 1 ? isoFiles[0].path : '';
  $('[name=iso]').value = iso;
  const releaseMatch = iso.match(/-(\d+\.\d+\.\d+)(?:[-.]|$)/);
  updateAutomaticTargetRelease(releaseMatch?.[1] || '');
  applySmuRecommendation(data.recommendation || {ready:false,selected:[],excluded:[],message:'No automatic package plan is available.'});
  setReadyCard('#iso-check', Boolean(iso), iso ? 'Found and ready' : isoFiles.length > 1 ? 'Select one base ISO in Expert settings' : 'Upload the Cisco base file');
  const plan=data.recommendation || {};
  renderManualPackages(data, plan);
  const rpmStatus=plan.ready
    ? `${data.recommended.length} compatible RPM${data.recommended.length === 1 ? '' : 's'} selected${plan.excluded?.length ? ` · ${plan.excluded.length} excluded` : ''}`
    : plan.message || 'Optional: add SMU files or another customization';
  setReadyCard('#rpm-check', plan.ready && data.recommended.length > 0, rpmStatus);

  const library = $('#file-library'); library.replaceChildren();
  if (iso) library.appendChild(fileRow('Base image', iso));
  if (data.recommended.length) library.appendChild(fileRow('Updates', `${data.recommended.length} compatible RPM files selected automatically`));
  if (!iso && !data.recommended.length) {
    const empty = document.createElement('p'); empty.textContent = 'No Cisco files have been found yet.'; empty.className = 'empty'; library.appendChild(empty);
  }
  updateBuildAvailability();
}

function updateAutomaticTargetRelease(release) {
  const field=$('[name=target_release]');
  if (targetReleaseIsAutomatic || field.value === lastAutomaticTargetRelease) {
    field.value=release;
    lastAutomaticTargetRelease=release;
    targetReleaseIsAutomatic=true;
  }
}

function expectedOutputText(platformId) {
  const profile=platformProfiles.find(item=>item.id === platformId);
  if (!profile) return '—';
  const usb=Boolean(profile.capabilities?.usb_image) && !$('[name=skip_usb_image]').checked;
  return usb ? 'ISO + USB' : 'ISO only';
}

function refreshExpectedOutput() {
  const value=$('#expected-output-value');
  if (value) value.textContent=expectedOutputText($('[name=platform]').value || detectedPlatform);
}
$('[name=skip_usb_image]').addEventListener('change', refreshExpectedOutput);

function formatGiB(bytes) { return (bytes / 1073741824).toFixed(1); }

function estimatedOutputBytes(plan) {
  // Not an authoritative size (gisobuild may de-duplicate or add its own
  // overhead) - a straightforward, honestly-labelled upper bound: the base
  // ISO plus every selected RPM, from sizes already in the uploaded
  // inventory (inputs.files), so this needs no extra backend request.
  if (!plan?.ready) return null;
  const iso=inputs.files.find(file => file.type === '.iso' && file.basename === plan.iso);
  if (!iso) return null;
  const packageBytes=(plan.selected || []).reduce((sum, name) => {
    const file=inputs.files.find(item => item.basename === name);
    return sum + (file ? file.size : 0);
  }, 0);
  return iso.size + packageBytes;
}

const VOLUME_LABELS = {uploads: 'uploads', work: 'build working', output: 'build output'};

function renderDiskEstimate() {
  const el=$('#disk-estimate');
  if (!el) return;
  const estimate=estimatedOutputBytes(inputs.recommendation);
  if (estimate === null || !storageInfo) { el.hidden=true; el.textContent=''; return; }
  // /api/storage now reports every volume a build touches, not just uploads:
  // gisobuild extracts into the working volume and writes its image to the
  // output volume, which a deployment can size independently.
  const volumes=storageInfo.volume_free_bytes
    || {uploads: storageInfo.disk_free_bytes};
  const entries=Object.entries(volumes);
  const shortVolumes=entries.filter(([, free]) => free < estimate);
  el.hidden=false;
  el.className=`disk-estimate${shortVolumes.length ? ' bad' : ''}`;
  const freeText=entries
    .map(([name, free]) => `${formatGiB(free)} GiB free on ${VOLUME_LABELS[name] || name}`)
    .join(' · ');
  el.textContent=`Estimated output ~${formatGiB(estimate)} GiB (base ISO + selected RPMs) · ${freeText}`
    + (shortVolumes.length
      ? ` — not enough space on the ${shortVolumes.map(([name]) => VOLUME_LABELS[name] || name).join(' and ')} volume(s); the build will be blocked until space is freed.`
      : '.');
}

function applySmuRecommendation(plan) {
  detectedPlatform = plan.platform || '';
  if (!packageListEdited) $('[name=pkglist]').value=(plan.selected || []).join('\n');
  // updatePlatformControls() force-checks "Skip USB image" for a platform
  // without USB capability - run it before computing the "Expected output"
  // field below so that field reflects the *new* platform's real USB
  // capability, not a stale checkbox state left over from a previous plan.
  updatePlatformControls();
  const blockers=plan.blockers || [];
  const blocked=plan.ready
    && (blockers.length > 0 || (plan.unsatisfied_dependencies || []).length > 0);
  const state=$('#smu-plan-state'); const title=$('#smu-auto-plan-title'); const message=$('#smu-plan-message');
  state.className=`pill ${blocked ? 'bad' : plan.ready ? 'success' : 'running'}`;
  state.textContent=blocked ? 'Blocked' : plan.ready ? 'Calculated' : 'Needs input';
  title.textContent=blocked ? 'Automatic selection found a problem'
    : plan.ready ? `${plan.selected.length} matching RPM${plan.selected.length === 1 ? '' : 's'} selected`
    : 'Automatic selection paused';
  message.textContent=plan.message;
  const details=$('#smu-plan-details'); details.replaceChildren();
  if (plan.ready) {
    const profile=platformProfiles.find(item=>item.id === plan.platform);
    const flow=document.createElement('div'); flow.className='smu-plan-flow';
    [['Base ISO',plan.iso],['Platform',String(plan.platform || '').toUpperCase()],
     ['Engine',profile ? profile.architecture.toUpperCase() : '—'],
     ['IOS XR',plan.release],['Selected',`${plan.selected.length} RPMs`],
     ['Expected output',expectedOutputText(plan.platform)]].forEach(([label,value],index)=>{
      if (index) { const arrow=document.createElement('span'); arrow.setAttribute('aria-hidden','true'); arrow.textContent='→'; flow.appendChild(arrow); }
      const step=document.createElement('span'); const small=document.createElement('small'); small.textContent=label; const strong=document.createElement('b'); strong.textContent=value;
      if (label === 'Expected output') strong.id='expected-output-value';
      step.append(small,strong); flow.appendChild(step);
    });
    details.appendChild(flow);
    const diskEstimate=document.createElement('p'); diskEstimate.id='disk-estimate'; diskEstimate.className='disk-estimate'; diskEstimate.hidden=true;
    details.appendChild(diskEstimate);
    if (plan.confidence) details.appendChild(confidenceGrid(plan.confidence));
    if (plan.package_groups?.length) {
      const groups=document.createElement('section'); groups.className='smu-groups';
      const heading=document.createElement('h4'); heading.textContent='SMU packages that belong together'; groups.appendChild(heading);
      const grid=document.createElement('div'); grid.className='csc-grid';
      plan.package_groups.forEach(group=>grid.appendChild(smuGroupCard(group)));
      groups.appendChild(grid); details.appendChild(groups);
    }
    if (plan.component_conflicts?.length) {
      const conflicts=document.createElement('div'); conflicts.className='smu-relationship-warning';
      const heading=document.createElement('b'); heading.textContent='Overlapping fixes detected'; conflicts.appendChild(heading);
      plan.component_conflicts.forEach(item=>{const row=document.createElement('p'); row.textContent=`${item.component}: ${item.cscs.join(' + ')}. ${item.reason}`; conflicts.appendChild(row);});
      details.appendChild(conflicts);
    }
    // Dependency problems are proven facts (read from the RPM headers and the
    // base image's own package list), not filename heuristics, so they lead
    // the blocker list and say what to do about each one.
    const dependencyBlockers=(plan.unsatisfied_dependencies || []).map(entry =>
      `${entry.requirement} is required by ${summarizeNames(entry.required_by || [])}`
      + (entry.base_image_has ? `, but the base image ships ${entry.base_image_has}` : '')
      + ' — download the Cisco SMU that provides it, or remove the package that needs it');
    const blockerList=compatibilityList('Fix before building', [...dependencyBlockers, ...blockers], 'fail');
    if (blockerList) details.appendChild(blockerList);
    if (plan.warnings?.length) {
      const warnings=document.createElement('div'); warnings.className='smu-relationship-warning';
      const heading=document.createElement('b'); heading.textContent='Review before building'; warnings.appendChild(heading);
      plan.warnings.forEach(text=>{const row=document.createElement('p'); row.textContent=text; warnings.appendChild(row);});
      details.appendChild(warnings);
    }
  }
  if (plan.excluded?.length) {
    const excluded=document.createElement('details'); const summary=document.createElement('summary'); summary.textContent=`${plan.excluded.length} incompatible RPM${plan.excluded.length === 1 ? '' : 's'} excluded automatically`;
    const list=document.createElement('ul');
    plan.excluded.forEach(item=>{
      const row=document.createElement('li'); row.className='excluded-package';
      row.dataset.search=`${item.name} ${item.reason}`.toLowerCase();
      row.textContent=`${item.name} — ${item.reason}`; list.appendChild(row);
    });
    excluded.append(summary,list); details.appendChild(excluded);
  }
  const reviewFilter=$('#smu-review-filter');
  const reviewItemCount=(plan.package_groups?.length || 0) + (plan.excluded?.length || 0);
  reviewFilter.hidden=reviewItemCount < 6;
  applySmuReviewFilter();
  renderDiskEstimate();
  updateBuildAvailability();
}

// selectedManualPackages(), syncManualPackageValue(), and renderManualPackages()
// are defined in manual-packages.js (loaded after this file) and attached to
// window, so calls to them below resolve there. That file's version is the
// only one that has ever executed: it uses opaque inventory IDs and groups
// duplicate basenames safely, unlike an earlier version of this logic that
// lived here and used box.value = file.path - a raw workspace path, exactly
// the "manual RPM path vs basename bug" this file's duplicate-handling
// regression tests exist to prevent. That dead code has been removed.

function smuGroupCard(group) {
  const card=document.createElement('article'); card.className=`csc-card ${group.count > 1 ? 'linked' : ''}`;
  card.dataset.search=[group.csc, ...group.components, ...group.files].join(' ').toLowerCase();
  const title=document.createElement('b'); title.textContent=group.csc;
  const status=document.createElement('small'); status.textContent=group.relationship;
  const components=document.createElement('p'); components.textContent=group.components.join(' · ');
  const files=document.createElement('details'); const summary=document.createElement('summary'); summary.textContent=`Show ${group.files.length} RPM filename${group.files.length === 1 ? '' : 's'}`;
  const list=document.createElement('ul'); group.files.forEach(name=>{const item=document.createElement('li'); item.textContent=name; list.appendChild(item);}); files.append(summary,list);
  card.append(title,status,components,files); return card;
}

function applySmuReviewFilter() {
  const filter=$('#smu-review-filter');
  const query=filter.value.trim().toLowerCase();
  document.querySelectorAll('#smu-plan-details .csc-card, #smu-plan-details .excluded-package').forEach(el => {
    el.hidden=Boolean(query) && !el.dataset.search.includes(query);
  });
}
$('#smu-review-filter').addEventListener('input', applySmuReviewFilter);

const CONFIDENCE_LABELS = {
  platform: 'Platform', release: 'IOS XR release', iso_architecture: 'ISO architecture',
  package_architecture: 'RPM architecture', csc_groups: 'CSC grouping',
  dependency_closure: 'Dependency closure',
};

function confidenceGrid(confidence) {
  const section=document.createElement('section'); section.className='confidence-section';
  const heading=document.createElement('h4'); heading.textContent='How sure are we?'; section.appendChild(heading);
  const grid=document.createElement('div'); grid.className='confidence-grid';
  Object.entries(CONFIDENCE_LABELS).forEach(([key,label])=>{
    const entry=confidence[key]; if (!entry) return;
    const badge=document.createElement('div'); badge.className=`confidence-badge ${entry.value.toLowerCase()}`;
    badge.title=entry.detail;
    const name=document.createElement('small'); name.textContent=label;
    const value=document.createElement('b'); value.textContent=entry.value;
    badge.append(name,value); grid.appendChild(badge);
  });
  section.appendChild(grid);
  const note=document.createElement('p'); note.className='confidence-note';
  note.textContent='VERIFIED means it was read from the file itself; INFERRED means it was guessed from a filename; MANUAL means the operator explicitly declared it without confirming the exact platform; UNKNOWN means it could not be determined here.';
  section.appendChild(note);
  return section;
}

async function refreshSmuRecommendation() {
  const iso=$('[name=iso_override]').value || $('[name=iso]').value;
  if (!iso) { applySmuRecommendation({ready:false,selected:[],excluded:[],message:'Upload or select one base ISO first.'}); return; }
  const button=$('#refresh-smu-plan'); button.disabled=true; button.textContent='Calculating…';
  try {
    const plan=await api('/api/smu/recommendation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({iso})});
    applySmuRecommendation(plan);
  } catch(error) { applySmuRecommendation({ready:false,selected:[],excluded:[],message:error.message}); }
  finally { button.disabled=false; button.textContent='Recalculate package set'; }
}

function updateBuildAvailability() {
  const yamlMode = $('[name=mode]:checked').value === 'yaml';
  const button = $('#start-build');
  if (yamlMode) {
    const ready = Boolean($('[name=yamlfile]').value.trim());
    button.disabled = !ready;
    button.textContent = ready ? 'Start build' : 'Waiting for a YAML file…';
    return;
  }
  const customFiles = ['xrconfig','ztp_ini','script','key_request','ownership_vouchers','ownership_certificate']
    .some(name => $(`[name=${name}]`).value.trim());
  const packageUpdates = selectedPackages().length > 0;
  const otherChanges = customFiles || packageUpdates || lines($('[name=bridging_fixes]').value).length > 0 ||
    lines($('[name=remove_packages]').value).length > 0;
  const hasIso = Boolean($('[name=iso_override]').value || $('[name=iso]').value);
  const ready = hasIso && otherChanges;
  button.disabled = !ready;
  // Naming exactly what's still missing, rather than always "an ISO and a
  // customization", matters once one of the two is already satisfied - an
  // operator who already uploaded an ISO and just needs to add a package
  // should not be told to wait for "an ISO" too.
  button.textContent = ready ? 'Start build'
    : !hasIso && !otherChanges ? 'Waiting for an ISO and a customization…'
    : !hasIso ? 'Waiting for an ISO…'
    : 'Waiting for a customization (packages, config files, or bridging fixes)…';
}

function fileRow(label, value) {
  const row = document.createElement('div'); row.className = 'file-item';
  const strong = document.createElement('b'); strong.textContent = label;
  const detail = document.createElement('small'); detail.textContent = value;
  row.append(strong, detail); return row;
}

async function loadInputs() {
  try { renderInputs(await api('/api/inputs')); }
  catch (error) { $('#error').textContent = error.message; }
}

async function loadPlatforms() {
  try {
    const select = $('[name=platform]');
    platformProfiles = await api('/api/platforms');
    platformProfiles.forEach(platform => {
      const option=document.createElement('option'); option.value=platform.id;
      option.textContent=`${platform.label} · ${platform.architecture.toUpperCase()}${platform.usb ? ' · USB' : ' · no automatic USB'}`;
      select.appendChild(option);
    });
    updatePlatformControls();
  } catch (error) { $('#error').textContent=error.message; }
}

async function checkCompatibility() {
  const button=$('#check-compatibility');
  const result=$('#compatibility-result');
  const packages=selectedPackages();
  const upgradeMode=$('[name=compatibility_mode]:checked').value === 'upgrade';
  const payload={iso:$('[name=iso_override]').value || $('[name=iso]').value,packages,
    matrix:upgradeMode ? $('[name=compatibility_matrix]').value : '',source_release:$('[name=source_release]').value,
    target_release:$('[name=target_release]').value,platform:$('[name=platform]').value};
  if (!payload.iso) { result.className='compatibility-result bad'; result.textContent='Select a base ISO first.'; return; }
  if (upgradeMode && (!payload.matrix || !payload.source_release || !payload.target_release || !payload.platform)) {
    result.className='compatibility-result bad'; result.textContent='For a router upgrade, select a matrix and platform and enter both releases.'; return;
  }
  button.disabled=true; result.className='compatibility-result'; result.textContent='Checking filenames and upgrade data…';
  try {
    const check=await api('/api/compatibility',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const good=check.smu.compatible && (!check.upgrade || (check.upgrade.permitted && !check.upgrade.missing_bridge_smus.length));
    const warning=good && check.smu.warnings.length > 0;
    result.className=`compatibility-result ${good ? (warning ? 'warning' : 'good') : 'bad'}`; result.replaceChildren();
    renderCompatibilityResult(result, check, payload);
  } catch(error) { result.className='compatibility-result bad'; result.textContent=error.message; }
  finally { button.disabled=false; }
}

function compatibilityMetric(icon, label, value, state) {
  const card=document.createElement('div'); card.className=`compatibility-metric ${state}`;
  const symbol=document.createElement('span'); symbol.className='compatibility-icon'; symbol.setAttribute('aria-hidden','true'); symbol.textContent=icon;
  const copy=document.createElement('span'); const strong=document.createElement('b'); strong.textContent=value;
  const small=document.createElement('small'); small.textContent=label; copy.append(strong,small); card.append(symbol,copy); return card;
}

function compatibilityList(title, items, state) {
  if (!items.length) return null;
  const section=document.createElement('section'); section.className=`compatibility-list ${state}`;
  const heading=document.createElement('h4'); heading.textContent=title; const list=document.createElement('ul');
  items.forEach(message=>{const item=document.createElement('li');item.textContent=message;list.appendChild(item);});
  section.append(heading,list); return section;
}

function renderCompatibilityResult(result, check, payload) {
  const summary=document.createElement('div'); summary.className='compatibility-summary';
  summary.append(
    compatibilityMetric(check.smu.compatible ? '✓' : '×','Package checks',check.smu.compatible ? 'Passed' : 'Blocked',check.smu.compatible ? 'pass' : 'fail'),
    compatibilityMetric('▦','RPM packages',String(check.smu.checked),'neutral'),
    compatibilityMetric('◆','CSC groups',String(check.smu.package_groups.length),'neutral'),
  );
  if (check.upgrade) summary.append(compatibilityMetric(check.upgrade.permitted ? '✓' : '×','Upgrade path',check.upgrade.permitted ? 'Permitted' : 'Not permitted',check.upgrade.permitted ? 'pass' : 'fail'));
  result.append(summary);

  if (check.upgrade) {
    const path=document.createElement('div'); path.className='upgrade-path'; path.setAttribute('aria-label',`Upgrade path from ${payload.source_release} to ${payload.target_release}`);
    const source=document.createElement('span'); source.append(document.createTextNode('Current ')); const sourceRelease=document.createElement('b'); sourceRelease.textContent=payload.source_release; source.append(sourceRelease);
    const arrow=document.createElement('span'); arrow.className='path-arrow'; arrow.setAttribute('aria-hidden','true'); arrow.textContent='→';
    const target=document.createElement('span'); target.append(document.createTextNode('Target ')); const targetRelease=document.createElement('b'); targetRelease.textContent=payload.target_release; target.append(targetRelease);
    path.append(source,arrow,target); result.append(path);
  }

  if (check.smu.package_groups.length) {
    const groups=document.createElement('section'); groups.className='csc-groups'; const heading=document.createElement('h4'); heading.textContent='Packages grouped by Cisco fix'; groups.appendChild(heading);
    const grid=document.createElement('div'); grid.className='csc-grid';
    check.smu.package_groups.forEach(group=>grid.appendChild(smuGroupCard(group)));
    groups.appendChild(grid); result.appendChild(groups);
  }

  const blockers=[...check.smu.issues];
  if (check.upgrade && !check.upgrade.permitted) blockers.push(check.upgrade.message);
  if (check.upgrade) blockers.push(...check.upgrade.missing_bridge_smus.map(item=>`Required bridge SMU is not selected: ${item}`));
  const cautions=[...check.smu.warnings];
  if (check.upgrade) cautions.push(...check.upgrade.caveats);
  const blockerList=compatibilityList('Fix before building',blockers,'fail'); if (blockerList) result.appendChild(blockerList);
  const cautionList=compatibilityList('Review before building',cautions,'warn'); if (cautionList) result.appendChild(cautionList);
  if (!blockers.length && !cautions.length) { const ready=document.createElement('p'); ready.className='compatibility-ready'; ready.textContent='No deterministic compatibility problems were found. Cisco gisobuild will perform the final dependency check.'; result.appendChild(ready); }
}

function updateCompatibilityMode() {
  const upgrade=$('[name=compatibility_mode]:checked').value === 'upgrade';
  $('#upgrade-compatibility-fields').hidden=!upgrade;
  $('#compatibility-result').className='compatibility-result';
  $('#compatibility-result').textContent=upgrade
    ? 'Select the matrix, releases and platform, then run the check.'
    : 'Ready to check the selected RPMs against the base ISO.';
}

function updatePackageSelectionMode() {
  const manual=$('[name=package_selection_mode]:checked').value === 'manual';
  $('#manual-package-override').hidden=!manual;
  if (manual && !packageListEdited) {
    packageListEdited=true;
    renderManualPackages(inputs, inputs.recommendation || {});
  }
  if (!manual) { packageListEdited=false; $('[name=pkglist_override]').value=''; }
  updateBuildAvailability();
}

function updatePlatformControls() {
  const platform=$('[name=platform]').value || detectedPlatform;
  const profile=platformProfiles.find(item=>item.id === platform);
  const controls=$('#lnt-controls');
  const unavailable=Boolean(profile && profile.architecture !== 'lnt');
  controls.hidden=unavailable;
  controls.querySelectorAll('input, textarea').forEach(control=>{
    control.disabled=unavailable;
    if (unavailable) control.type === 'checkbox' ? control.checked=false : control.value='';
  });
  $('#lnt-controls-help').textContent=profile
    ? profile.architecture === 'lnt' ? `${profile.label} uses IOS XR7/LNT; these controls are available.` : `${profile.label} uses eXR; LNT-only controls are disabled.`
    : 'Select a platform or base ISO to determine whether these controls apply.';
  const capabilityNames={
    script:'script',optimize:'optimize',x86_only:'x86_only',migration:'migration',full_iso:'full_iso',
    remove_packages:'remove_packages',only_support_pids:'only_support_pids',verbose_dep_check:'verbose_dependency_check',
    clear_bridging_fixes:'clear_bridging_fixes',ownership_vouchers:'ownership_vouchers',
    ownership_certificate:'ownership_certificate',clear_ownership_vouchers:'clear_ownership_vouchers',
    clear_ownership_certificate:'clear_ownership_certificate',key_request:'key_request',
    clear_key_request:'clear_key_request',no_buildinfo:'no_buildinfo'
  };
  Object.entries(capabilityNames).forEach(([name,capability])=>{
    const control=$(`[name=${name}]`); if (!control) return;
    const supported=!profile || profile.capabilities?.[capability] !== false;
    const wrapper=control.closest('label');
    if (wrapper) wrapper.hidden=!supported;
    control.disabled=!supported;
    if (!supported) control.type === 'checkbox' ? control.checked=false : control.value='';
  });
  const skipUsb=$('[name=skip_usb_image]');
  if (profile && !profile.capabilities?.usb_image) skipUsb.checked=true;
  updateBuildAvailability();
}

async function loadStorage() {
  try {
    const usage = await api('/api/storage');
    storageInfo = usage;
    const archiveGb = formatGiB(usage.archive_used_bytes);
    const quotaGb = (usage.archive_quota_bytes / 1073741824).toFixed(0);
    const freeGb = formatGiB(usage.disk_free_bytes);
    $('#storage-usage').textContent = `Archive: ${archiveGb} of ${quotaGb} GiB used · ${freeGb} GiB free on the upload volume`;
    renderDiskEstimate();
  } catch { /* Storage usage is diagnostic only; a missing line is not an error. */ }
}

function applyArchiveFilter() {
  const query = $('#archive-filter').value.trim().toLowerCase();
  document.querySelectorAll('#archive-list .archive-row').forEach(row => {
    row.hidden = Boolean(query) && !row.dataset.name.includes(query);
  });
}
$('#archive-filter').addEventListener('input', applyArchiveFilter);

async function loadArchive() {
  try {
    const items = await api('/api/archive');
    const list = $('#archive-list'); list.replaceChildren();
    const filter = $('#archive-filter');
    if (!items.length) {
      filter.hidden = true; filter.value = '';
      const empty=document.createElement('p'); empty.className='empty'; empty.textContent='No archived GISO images yet. Completed Golden ISO and USB boot artifacts appear here automatically after a successful build.'; list.appendChild(empty); return;
    }
    filter.hidden = items.length < 6;
    items.forEach(item => {
      const row=document.createElement('div'); row.className='archive-row';
      row.dataset.name=item.name.toLowerCase();
      const link=document.createElement('a'); link.href=item.url;
      const name=document.createElement('span'); name.textContent=item.name;
      const meta=document.createElement('small'); meta.textContent=`${new Date(item.created*1000).toLocaleString()} · ${(item.size/1073741824).toFixed(2)} GB ↓`;
      const remove=document.createElement('button'); remove.type='button'; remove.className='delete-archive'; remove.textContent='Delete';
      const isIso=item.name.toLowerCase().endsWith('.iso');
      name.textContent=`${isIso ? 'Golden ISO' : 'USB boot image'} · ${item.name}`;
      const guide=document.createElement('button'); guide.type='button'; guide.className='secondary small'; guide.textContent='Upgrade guide';
      guide.hidden=!isIso; guide.onclick=()=>openUpgradeGuide(item.name);
      const report=document.createElement('a'); report.className='secondary small'; report.textContent='Build report';
      report.href=`/archive/${encodeURIComponent(item.job_id)}/build-report.json`;
      report.hidden=!(isIso && item.has_report);
      const checksums=document.createElement('div'); checksums.className='checksums';
      const showChecksums=document.createElement('button'); showChecksums.type='button'; showChecksums.className='secondary small'; showChecksums.textContent='Show MD5 / SHA-256';
      showChecksums.onclick=async()=>{
        showChecksums.disabled=true; showChecksums.textContent='Calculating…';
        try {
          const sums=await api(`/api/archive/${encodeURIComponent(item.job_id)}/${encodeURIComponent(item.name)}/checksums`);
          checksums.replaceChildren(checksumRow('MD5',sums.md5),checksumRow('SHA-256',sums.sha256));
          showChecksums.remove();
        } catch(error){ showChecksums.disabled=false; showChecksums.textContent='Show MD5 / SHA-256'; await showNotice('Could not calculate checksums', error.message); }
      };
      remove.onclick=async()=>{
        if(!await showConfirmation('Delete archived artifact?', `${item.name}\n\nThis permanently deletes the selected GISO artifact and cannot be undone.`, 'Delete artifact', true)) return;
        try { await api(`/api/archive/${encodeURIComponent(item.job_id)}/${encodeURIComponent(item.name)}`,{method:'DELETE'}); await loadArchive(); }
        catch(error){ await showNotice('Could not delete artifact', error.message); }
      };
      const actions=document.createElement('div'); actions.className='archive-actions'; actions.append(guide,report,showChecksums,remove);
      link.append(name,meta); row.append(link,actions,checksums); list.appendChild(row);
    });
    applyArchiveFilter();
  } catch (error) { $('#archive-list').textContent=error.message; }
}

function checksumRow(label, value) {
  const row=document.createElement('div'); row.className='checksum-row';
  const name=document.createElement('b'); name.textContent=label;
  const code=document.createElement('code'); code.textContent=value;
  const copy=document.createElement('button'); copy.type='button'; copy.className='secondary small'; copy.textContent='Copy';
  copy.onclick=()=>copyText(value, copy, 'Copy');
  row.append(name,code,copy); return row;
}

function openUpgradeGuide(filename) {
  $('#upgrade-guide').dataset.filename=filename;
  $('#guide-md5').textContent=`show md5 file /harddisk:/${filename}`;
  updateGuideWorkflow();
  $('#upgrade-guide').showModal();
}

function updateGuideWorkflow() {
  const filename=$('#upgrade-guide').dataset.filename || 'GOLDEN-ISO.iso';
  const family=$('#guide-family').value;
  const install=$('#guide-install'), apply=$('#guide-apply'), note=$('#guide-workflow-note');
  const copy=$('#copy-guide');
  apply.hidden=true; apply.textContent='';
  copy.disabled=false; copy.textContent='Copy commands';
  if(family==='lnt') {
    install.textContent=`install package replace /harddisk:/${filename}`;
    apply.textContent='show install request\ninstall apply reload'; apply.hidden=false;
    note.textContent='Use show install request and the platform guide to determine whether reload or restart is required. Do not substitute restart merely to avoid a reload.';
  } else if(family==='legacy') {
    install.textContent=`install update source harddisk: ${filename} replace`;
    note.textContent='This is only a command pattern. Copy the exact legacy syntax and prerequisites from the installation guide for the source release.';
  } else if(family==='migration') {
    install.textContent='Do not use a normal GISO replacement command.';
    note.textContent='ASR 9000 32-bit to 64-bit migration requires Cisco’s dedicated migration procedure, a compatible migration TAR and potentially an intermediate release. Open the complete guide before continuing.';
    copy.disabled=true; copy.textContent='Migration commands require Cisco documentation';
  } else {
    install.textContent=`install replace /harddisk:/${filename}`;
    note.textContent='This workflow may apply changes and reload automatically. Confirm the exact command options in the platform and release guide, and avoid noprompt during a supervised change.';
  }
}

function updateRollbackWorkflow() {
  const family=$('#rollback-family').value;
  const inspect=$('#rollback-inspect'), abortStep=$('#rollback-abort-step'), commitStep=$('#rollback-commit-step');
  const command=$('#rollback-command'), apply=$('#rollback-apply'), note=$('#rollback-note');
  const copy=$('#copy-rollback-guide');
  copy.disabled=false; copy.textContent='Copy rollback commands'; apply.hidden=false; abortStep.hidden=false; commitStep.hidden=false;
  if(family==='lnt') {
    inspect.textContent='show install request\nshow install rollback list-ids\nshow install rollback id <TRANSACTION-ID> changes\nshow install history last transaction verbose';
    command.textContent='install package rollback <TRANSACTION-ID>';
    apply.textContent='show install request\ninstall apply reload';
    note.textContent='Use show install request and the platform guide to determine whether reload or restart is required. The immediate install rollback form may apply changes automatically on some releases.';
  } else if(family==='exr') {
    inspect.textContent='show install rollback ?\nshow install active summary\nshow install committed summary\nshow install history last transaction verbose';
    abortStep.hidden=true;
    command.textContent='install rollback to committed\n# or: install rollback to <ROLLBACK-POINT>';
    apply.hidden=true;
    note.textContent='These are command patterns. Available rollback points, execution mode and reload behavior vary by platform and release; confirm them with contextual help and Cisco documentation.';
  } else {
    inspect.textContent='show version\nshow platform\nshow install active summary\nshow install committed summary';
    abortStep.hidden=true; commitStep.hidden=true; apply.hidden=true;
    command.textContent='Do not use a generic rollback command.';
    note.textContent='Legacy IOS XR and ASR 9000 architecture migrations require the exact Cisco recovery or migration procedure. Use approved recovery media and contact Cisco TAC when the supported path is uncertain.';
    copy.disabled=true; copy.textContent='Commands require Cisco documentation';
  }
}

const READY_CHECK_LABELS = {
  docker: 'Docker is unavailable',
  tool: 'the gisobuild engine checkout is missing',
  storage: 'a required storage directory is missing',
  database: 'the job database is unavailable',
  disk: 'disk space is critically low',
};

async function health() {
  const pill = $('#health');
  try {
    // /api/health only proves the process itself is responding; /api/ready
    // (the same check the container's own HEALTHCHECK uses) also confirms
    // Docker, the mounted gisobuild checkout, storage, the job database and
    // disk space are actually usable - showing "System ready" from the
    // weaker check would be a false all-clear on a deployment that can
    // never actually complete a build. Fetched directly rather than through
    // api(): /api/ready legitimately answers "not ready" with HTTP 503 and
    // a body explaining why, but api() treats any non-2xx as a transport
    // failure and throws away the body - which would collapse every "not
    // ready" reason into the same generic "System unavailable".
    const state = await (await fetch('/api/ready')).json();
    if (state.ok) {
      pill.textContent = '✓ System ready';
      pill.className = 'pill ok';
      pill.removeAttribute('title');
      pill.removeAttribute('aria-label');
    } else {
      const failing = Object.entries(READY_CHECK_LABELS)
        .filter(([key]) => state[key] === false)
        .map(([, label]) => label);
      pill.textContent = failing.length === 1 ? `⚠ ${failing[0]}` : `⚠ System not ready (${failing.length} checks failing)`;
      pill.className = 'pill bad';
      // A hover title alone would hide the specific reasons from touch and
      // screen-reader users; aria-label gives them the same full list as
      // the sighted hover tooltip, on the same role="status" element that
      // already announces the pill's text on change.
      if (failing.length > 1) {
        pill.title = failing.join('; ');
        pill.setAttribute('aria-label', `System not ready: ${failing.join('; ')}`);
      } else {
        pill.removeAttribute('title');
        pill.removeAttribute('aria-label');
      }
    }
  } catch { pill.textContent = 'System unavailable'; pill.className = 'pill bad'; }
}

async function loadVersion() {
  try {
    const info = await api('/api/version');
    const engine = `${info.gisobuild_image}${info.gisobuild_commit ? ` @ ${info.gisobuild_commit}` : ''}`;
    $('#version-info').textContent = `Web UI ${info.app_version} · Build engine ${engine}`;
  } catch { /* Version info is diagnostic only; a missing line is not an error. */ }
}

async function previewFile(button) {
  const field = button.dataset.field;
  const input = document.querySelector(`[name="${field}"]`);
  const output = $('#file-preview-output');
  const path = input.value.trim();
  output.hidden = false;
  if (!path) { output.textContent = 'Enter or choose a file first.'; return; }
  output.textContent = 'Loading preview…';
  try {
    const data = await api(`/api/file-preview?path=${encodeURIComponent(path)}`);
    output.textContent = data.previewable
      ? `${path}:\n\n${data.text}`
      : `${path}: ${data.reason}`;
  } catch (err) { output.textContent = err.message; }
}
document.querySelectorAll('.preview-file').forEach(button => button.addEventListener('click', () => previewFile(button)));

document.querySelectorAll('[name=mode]').forEach(radio => radio.addEventListener('change', event => {
  const yaml = event.target.value === 'yaml';
  $('#form-mode').hidden = yaml; $('#yaml-mode').hidden = !yaml;
  updateBuildAvailability();
}));
$('[name=yamlfile]').addEventListener('input', updateBuildAvailability);
$('[name=iso_override]').addEventListener('input', updateBuildAvailability);
$('#form-mode').addEventListener('input', updateBuildAvailability);

$('#build-form').addEventListener('submit', async event => {
  event.preventDefault(); $('#error').textContent = '';
  const form = new FormData(event.target);
  const yamlMode = form.get('mode') === 'yaml';
  const payload = {
    iso: form.get('iso_override') || form.get('iso'),
    platform: form.get('platform') || '',
    yamlfile: yamlMode ? form.get('yamlfile') : '',
    label: form.get('label_override') || form.get('label'),
    pkglist: selectedPackages(),
    automatic_smu_selection: $('[name=package_selection_mode]:checked').value === 'automatic',
    repo: lines(form.get('repo') || ''), auto_repo: true,
    bridging_fixes: lines(form.get('bridging_fixes') || ''),
    remove_packages: lines(form.get('remove_packages') || ''),
    only_support_pids: lines(form.get('only_support_pids') || ''),
    xrconfig: form.get('xrconfig') || '', ztp_ini: form.get('ztp_ini') || '', script: form.get('script') || '',
    key_request: form.get('key_request') || '', ownership_vouchers: form.get('ownership_vouchers') || '',
    ownership_certificate: form.get('ownership_certificate') || ''
  };
  event.target.querySelectorAll('input[type=checkbox]').forEach(box => { payload[box.name] = box.checked; });
  const button = $('#start-build'); button.disabled = true; button.textContent = 'Starting…';
  try {
    const plan = await api('/api/build-plan', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    renderUnsatisfiedDependencies(plan);
    if (!plan.ready) {
      // A dependency problem gets the dedicated panel above (which names each
      // package and what the base image ships) rather than being flattened
      // into one long error line with everything else.
      if (plan.unsatisfied_dependencies?.length) {
        throw new Error('This build cannot succeed - see the missing dependencies listed above.');
      }
      throw new Error(`BuildPlan is blocked: ${plan.blockers.join('; ')}`);
    }
    const usbText = plan.expected_outputs.usb ? 'A USB boot image is expected.' : 'No USB boot image is expected for these settings.';
    const overrideWarnings = [];
    if (!payload.automatic_smu_selection) overrideWarnings.push('Manual package selection is active: automatic supersedence and CSC-group matching were bypassed for the packages you chose.');
    if (payload.platform && payload.platform !== detectedPlatform) overrideWarnings.push(`Platform was manually set to ${payload.platform.toUpperCase()}, overriding automatic detection.`);
    if (form.get('iso_override')) overrideWarnings.push('The base ISO was manually selected in Expert settings, overriding automatic detection.');
    const overrideText = overrideWarnings.length ? `⚠ ${overrideWarnings.join('\n⚠ ')}\n\n` : '';
    const message = `${overrideText}Start the verified plan with ${plan.selected_packages.length} updates?\n\nPlatform: ${String(plan.platform).toUpperCase()} · Engine: ${String(plan.engine).toUpperCase()} · Inventory: ${plan.inventory_revision}\nPlan: ${plan.fingerprint.slice(0, 16)}…\n\n${usbText}`;
    if (!await showConfirmation('Start Golden ISO build?', message, 'Start build', overrideWarnings.length > 0)) { updateBuildAvailability(); return; }
    payload.confirmed_plan_fingerprint = plan.fingerprint;
    const result = await api('/api/jobs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }); currentJob = result.id; poll();
  }
  catch (error) { $('#error').textContent = error.message; updateBuildAvailability(); }
});

function buildReportField(label, value) {
  const step=document.createElement('span'); const small=document.createElement('small'); small.textContent=label;
  const strong=document.createElement('b'); strong.textContent=value; step.append(small,strong); return step;
}

function renderBuildReport(job) {
  const report=$('#build-report'); const body=$('#build-report-body'); body.replaceChildren();
  const plan=job.build_plan;
  if (!plan) { report.hidden=true; return; }
  report.hidden=false;
  const flow=document.createElement('div'); flow.className='smu-plan-flow';
  [['Base ISO',plan.iso?.relative_path || '—'],['Platform',String(plan.platform||'').toUpperCase()],
   ['Engine',String(plan.engine||'').toUpperCase()],['IOS XR',plan.release||'—'],
   ['Packages',`${plan.selected_packages.length} RPM${plan.selected_packages.length===1?'':'s'}`]]
    .forEach(([label,value],index)=>{
      if (index) { const arrow=document.createElement('span'); arrow.setAttribute('aria-hidden','true'); arrow.textContent='→'; flow.appendChild(arrow); }
      flow.appendChild(buildReportField(label,value));
    });
  body.appendChild(flow);

  const meta=document.createElement('p'); meta.className='build-report-meta';
  meta.textContent=`Inventory revision ${plan.inventory_revision} · BuildPlan fingerprint ${plan.fingerprint.slice(0,16)}…`;
  body.appendChild(meta);

  // create_build_plan() has always computed plan.confidence (the same shape
  // Step 2's live review shows via confidenceGrid()), but nothing here ever
  // rendered it - the one permanent record of a completed build showed
  // every other confidence-bearing fact except how sure the system actually
  // was about them, including whether the platform was a real filename
  // match or an operator-declared generic eXR/LNT fallback (MANUAL).
  if (plan.confidence) body.appendChild(confidenceGrid(plan.confidence));

  if (plan.iso?.sha256 || plan.selected_packages?.length) {
    const checksums=document.createElement('details');
    const summary=document.createElement('summary'); summary.textContent='Show input checksums (SHA-256)';
    const list=document.createElement('ul');
    if (plan.iso?.sha256) { const row=document.createElement('li'); row.textContent=`${plan.iso.relative_path} — ${plan.iso.sha256}`; list.appendChild(row); }
    plan.selected_packages.forEach(item=>{ const row=document.createElement('li'); row.textContent=`${item.basename} — ${item.sha256}`; list.appendChild(row); });
    checksums.append(summary,list); body.appendChild(checksums);
  }

  if (job.command_preview) {
    const commandDetails=document.createElement('details');
    const summary=document.createElement('summary'); summary.textContent='Show generated gisobuild command';
    const pre=document.createElement('pre'); pre.className='command-preview'; pre.textContent=job.command_preview;
    const copy=document.createElement('button'); copy.type='button'; copy.className='secondary small';
    copy.textContent='Copy command'; copy.onclick=()=>copyText(job.command_preview, copy, 'Copy command');
    commandDetails.append(summary,pre,copy); body.appendChild(commandDetails);
  }

  if (plan.selected_csc_groups?.length) {
    const groups=document.createElement('section'); groups.className='smu-groups';
    const heading=document.createElement('h4'); heading.textContent='Fixes included'; groups.appendChild(heading);
    const grid=document.createElement('div'); grid.className='csc-grid';
    plan.selected_csc_groups.forEach(group=>grid.appendChild(smuGroupCard(group)));
    groups.appendChild(grid); body.appendChild(groups);
  }

  if (plan.excluded_packages?.length) {
    const excluded=document.createElement('details');
    const summary=document.createElement('summary'); summary.textContent=`${plan.excluded_packages.length} package${plan.excluded_packages.length===1?'':'s'} excluded`;
    const list=document.createElement('ul');
    plan.excluded_packages.forEach(item=>{ const row=document.createElement('li'); row.textContent=`${item.name} — ${item.reason}`; list.appendChild(row); });
    excluded.append(summary,list); body.appendChild(excluded);
  }

  if (plan.warnings?.length) {
    const warnings=document.createElement('div'); warnings.className='smu-relationship-warning';
    const heading=document.createElement('b'); heading.textContent='Reviewed warnings'; warnings.appendChild(heading);
    plan.warnings.forEach(text=>{ const row=document.createElement('p'); row.textContent=text; warnings.appendChild(row); });
    body.appendChild(warnings);
  }
}

function summarizeNames(names) {
  // A cumulative SMU set often has every selected package declaring the same
  // requirement, so printing all of them repeats one long list per line and
  // buries the requirement itself. Two names plus a count stays scannable;
  // the full list is in the build report.
  if (names.length <= 2) return names.join(', ');
  return `${names.slice(0, 2).join(', ')} and ${names.length - 2} more`;
}

function dependencyPanel(heading, intro, entries) {
  const panel = $('#missing-dependencies');
  if (!entries.length) { panel.hidden = true; panel.replaceChildren(); return; }
  panel.hidden = false;
  const title = document.createElement('h4'); title.textContent = heading;
  const lead = document.createElement('p'); lead.textContent = intro;
  const list = document.createElement('ul');
  entries.forEach(({requirement, required_by, base_image_has, prerequisite_smu, listed_by}) => {
    const item = document.createElement('li');
    const needed = Array.isArray(required_by) ? summarizeNames(required_by) : required_by;
    item.textContent = `${requirement} — required by ${needed}`
      + (base_image_has ? `; the base image ships ${base_image_has}` : '')
      + (prerequisite_smu ? `. Download ${prerequisite_smu} (listed as a prerequisite by ${listed_by})` : '');
    if (Array.isArray(required_by) && required_by.length > 2) item.title = required_by.join('\n');
    list.appendChild(item);
  });
  panel.replaceChildren(title, lead, list);
}

function renderMissingDependencies(job) {
  dependencyPanel(
    'Missing dependencies found by gisobuild',
    'The build failed its RPM dependency check. This usually means an additional Cisco SMU/fix package providing one of these is missing from your repository:',
    job.missing_dependencies || []);
}

function renderUnsatisfiedDependencies(plan) {
  // The same panel, used one step earlier: these are read from the selected
  // RPMs' own headers against the base image's own package list, so they are
  // known before gisobuild runs rather than reported by it afterwards.
  dependencyPanel(
    'Missing dependencies — this build cannot succeed',
    'A selected package needs another package version that neither the base image nor your selection provides. Download the Cisco SMU that supplies each of these, or remove the package that needs it:',
    plan.unsatisfied_dependencies || []);
}

async function poll() {
  if (!currentJob) return;
  clearTimeout(activityTimer);
  clearTimeout(pollTimer);
  try {
    const job = await api(`/api/jobs/${currentJob}`);
    const labels = {running:'Building', queued:'Waiting', cancelling:'Stopping', interrupted:'Interrupted', success:'Complete', failed:'Failed', cancelled:'Stopped'};
    $('#job-status').textContent = labels[job.status] || job.status;
    $('#job-status').className = `pill ${job.status}`;
    $('#cancel-build').hidden = !['running','queued'].includes(job.status);
    $('#log').textContent = job.log || 'The build is starting…';
    const progress = job.status === 'success' ? 100 : (job.progress || 0);
    $('#build-progress').value = progress;
    $('#build-percent').textContent = `${progress}%`;
    $('#build-phase').textContent = job.phase || 'Working';
    const seconds = Math.max(0, Math.floor(((job.finished || Date.now()/1000) - job.created)));
    $('#elapsed-time').textContent = `Elapsed time: ${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
    const friendlyStatusByJobStatus = {
      success: 'Your new image is ready. Download it using the green link below.',
      failed: 'The build could not be completed. Open the technical details to see why.',
      interrupted: 'The web service restarted before this build completed. Check Docker and the technical log before starting another build.',
      cancelled: 'The build was stopped. Your uploaded files are still saved.',
      queued: 'Waiting for the current build slot to free up. Only one build can run at a time.',
      cancelling: 'Stopping the build. This can take a few seconds while the build container shuts down.',
    };
    $('#friendly-status').textContent = friendlyStatusByJobStatus[job.status] || 'The build is running. You may leave this page open or return later.';
    renderMissingDependencies(job);
    const artifacts = $('#artifacts'); artifacts.replaceChildren();
    job.artifacts.forEach(artifact => {
      const link = document.createElement('a'); link.href = artifact.url || `/download/${encodeURIComponent(job.id)}/${artifact.path.split('/').map(encodeURIComponent).join('/')}`;
      const name = document.createElement('span'); name.textContent = artifact.path.endsWith('.iso') ? 'Download completed ISO image' : `Download ${artifact.path}`;
      const size = document.createElement('small'); size.textContent = `${(artifact.size/1048576).toFixed(1)} MB ↓`;
      link.append(name, size); artifacts.appendChild(link);
    });
    renderBuildReport(job);
    if (['running','queued','cancelling'].includes(job.status)) pollTimer = setTimeout(poll, 1500); else { await loadInputs(); await loadArchive(); await loadStorage(); }
  } catch (error) {
    $('#friendly-status').textContent = `Status temporarily unavailable: ${error.message}. Retrying…`;
    pollTimer = setTimeout(poll, 3000);
  }
}

async function pollActivity() {
  if (currentJob) return;
  clearTimeout(activityTimer);
  try {
    const activity = await api('/api/activity');
    $('#log').textContent = activity.log || 'Waiting for upload or build activity…';
  } catch (error) {
    $('#log').textContent = `Activity log temporarily unavailable: ${error.message}`;
  }
  activityTimer = setTimeout(pollActivity, 1500);
}

async function restoreJob() {
  try {
    const jobs = await api('/api/jobs');
    const job = jobs.find(item => ['running','queued','cancelling'].includes(item.status)) || jobs[0];
    if (job) { currentJob = job.id; poll(); } else { pollActivity(); }
  } catch { /* Starts clean if there is no previous job. */ }
}

const CHUNK = 16 * 1024 * 1024;
async function uploadFile(file) {
  currentJob = null; pollActivity();
  const row = document.createElement('div'); row.className = 'upload-row';
  const name = document.createElement('span'); name.textContent = file.name;
  const progress = document.createElement('progress'); progress.max = 100; progress.value = 0;
  progress.setAttribute('aria-label', `Upload progress for ${file.name}`);
  const status = document.createElement('small'); status.textContent = 'Starting…'; row.append(name, progress, status); $('#upload-list').appendChild(row);
  let upload = null;
  try {
    upload = await api('/api/uploads/init', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:file.name,size:file.size})});
    let offset = 0;
    while (offset < file.size) {
      const blob = file.slice(offset, Math.min(offset + CHUNK, file.size));
      await api(`/api/uploads/${upload.id}?offset=${offset}`, {method:'PUT', body:blob}); offset += blob.size;
      const percent = Math.round(offset / file.size * 100); progress.value = percent; status.textContent = `${percent}%`;
    }
    const done = await api(`/api/uploads/${upload.id}/complete`, {method:'POST'});
    row.classList.add('done'); status.textContent = done.extracted ? `Ready – ${done.extracted} files extracted` : 'Ready and saved';
    packageListEdited = false; await loadInputs();
  } catch (error) {
    if (upload) fetch(`/api/uploads/session/${upload.id}`, {method:'DELETE'}).catch(() => {});
    row.classList.add('upload-error'); status.textContent = error.message;
  }
}
async function uploadFiles(files) {
  activeUploads += 1;
  try { for (const file of files) await uploadFile(file); }
  finally { activeUploads -= 1; }
}

let ciscoSearchId = null;
let ciscoDownloadJob = null;

async function pollCiscoDownload() {
  if (!ciscoDownloadJob) return;
  try {
    const job = await api(`/api/cisco/downloads/${encodeURIComponent(ciscoDownloadJob)}`);
    const labels = {'eula-required':'Cisco agreement required',downloading:'Downloading from Cisco',verifying:'Verifying Cisco checksums',ready:'Cisco files are ready',failed:'Cisco download failed'};
    $('#cisco-status').textContent = `${labels[job.status] || job.status}${job.progress ? ` · ${job.progress}%` : ''}${job.error ? ` · ${job.error}` : ''}`;
    if (job.status === 'ready') { ciscoDownloadJob = null; await loadInputs(); return; }
    if (job.status === 'failed' || job.status === 'eula-required') return;
    setTimeout(pollCiscoDownload, 1500);
  } catch (error) { $('#cisco-status').textContent = error.message; }
}

async function startCiscoDownload(imageGuids) {
  const job = await api('/api/cisco/downloads', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({search_id:ciscoSearchId,image_guids:imageGuids})});
  ciscoDownloadJob = job.id;
  $('#cisco-results-form').hidden = true;
  if (job.status === 'eula-required') {
    $('#cisco-agreement').hidden = false;
    $('#cisco-eula-label').hidden = !job.agreement.eula;
    $('#cisco-commercial-label').hidden = !job.agreement.k9;
    $('#cisco-not-government-label').hidden = !job.agreement.k9;
    $('#cisco-status').textContent = 'Read and confirm the required Cisco agreement below.';
  } else { pollCiscoDownload(); }
}

function applyCiscoResultsFilter() {
  const query = $('#cisco-results-filter').value.trim().toLowerCase();
  document.querySelectorAll('#cisco-results label').forEach(label => {
    label.hidden = Boolean(query) && !label.dataset.name.includes(query);
  });
}
$('#cisco-results-filter').addEventListener('input', applyCiscoResultsFilter);

$('#cisco-search-form').addEventListener('submit', async event => {
  event.preventDefault();
  const submit = event.submitter; submit.disabled = true;
  const form = new FormData(event.target);
  $('#cisco-status').textContent = 'Authenticating and searching Cisco…';
  $('#cisco-results-form').hidden = true;
  $('#cisco-results-filter').hidden = true;
  $('#cisco-agreement').hidden = true;
  try {
    const result = await api('/api/cisco/search', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pid:form.get('pid'),current_release:form.get('current_release'),target_release:form.get('target_release')})});
    ciscoSearchId = result.id;
    const list = $('#cisco-results'); list.replaceChildren();
    result.images.forEach(image => {
      const label = document.createElement('label');
      label.dataset.name=image.name.toLowerCase();
      const input = document.createElement('input'); input.type='checkbox'; input.name='image_guid'; input.value=image.guid;
      const text = document.createElement('span'); text.textContent=`${image.name} · ${image.release || 'release not supplied'} · ${(image.size/1048576).toFixed(1)} MB${image.entitlement ? ' · contract required' : ''}`;
      label.append(input,text); list.appendChild(label);
    });
    $('#cisco-results-form').hidden = result.images.length === 0;
    const resultsFilter = $('#cisco-results-filter');
    resultsFilter.hidden = result.images.length < 6;
    resultsFilter.value = '';
    applyCiscoResultsFilter();
    $('#cisco-status').textContent = result.images.length ? `Found ${result.images.length} files. Select up to five.` : 'Cisco returned no matching files.';
  } catch (error) { $('#cisco-status').textContent = error.message; }
  finally { submit.disabled = false; }
});

$('#cisco-results-form').addEventListener('submit', async event => {
  event.preventDefault();
  const submit = event.submitter;
  const selected=[...event.target.querySelectorAll('[name=image_guid]:checked')].map(item=>item.value);
  if (!selected.length || selected.length > 5) { $('#cisco-status').textContent='Select between one and five files.'; return; }
  $('#cisco-status').textContent='Requesting authorized download links…';
  submit.disabled=true;
  try { await startCiscoDownload(selected); } catch (error) { $('#cisco-status').textContent=error.message; }
  finally { submit.disabled=false; }
});

$('#cisco-accept').onclick = async () => {
  const submit=$('#cisco-accept'); submit.disabled=true;
  const body={accept_eula:$('#cisco-eula').checked,commercial_or_civil:$('#cisco-commercial').checked,not_government_or_military:$('#cisco-not-government').checked};
  $('#cisco-status').textContent='Registering the agreement with Cisco…';
  try {
    await api(`/api/cisco/downloads/${encodeURIComponent(ciscoDownloadJob)}/accept`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    $('#cisco-agreement').hidden=true; pollCiscoDownload();
  } catch (error) { $('#cisco-status').textContent=error.message; }
  finally { submit.disabled=false; }
};

$('#choose-files').onclick = () => $('#file-upload').click();
$('#file-upload').onchange = event => uploadFiles(event.target.files);
const drop = $('#drop-zone');
['dragenter','dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add('drag'); }));
['dragleave','drop'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', event => uploadFiles(event.dataTransfer.files));
$('#refresh').onclick = loadInputs;
$('#refresh-archive').onclick = () => { loadArchive(); loadStorage(); };
$('#general-guide').onclick = () => openUpgradeGuide('GOLDEN-ISO.iso');
$('#rollback-guide-button').onclick = () => { updateRollbackWorkflow(); $('#rollback-guide').showModal(); };
$('#close-guide').onclick = () => $('#upgrade-guide').close();
$('#close-rollback-guide').onclick = () => $('#rollback-guide').close();
$('#guide-family').onchange = updateGuideWorkflow;
$('#rollback-family').onchange = updateRollbackWorkflow;
$('#copy-guide').onclick = async () => {
  const commands=[...$('#upgrade-guide').querySelectorAll('pre')].map(pre=>pre.textContent).join('\n\n');
  await copyText(commands, $('#copy-guide'), 'Copy commands');
};
$('#copy-rollback-guide').onclick = async () => {
  const commands=[...$('#rollback-guide').querySelectorAll('pre:not([hidden])')].map(pre=>pre.textContent).join('\n\n');
  await copyText(commands, $('#copy-rollback-guide'), 'Copy rollback commands');
};
$('#cleanup').onclick = async () => {
  if (!await showConfirmation('Clear workspace files?', 'Remove all uploaded source files, partial uploads, build working files, and raw output?\n\nCompleted ISO and USB files in the GISO Archive will be kept.', 'Clear workspace', true)) return;
  try {
    const result = await api('/api/cleanup', {method:'POST'});
    const mb = (result.removed_bytes / 1048576).toFixed(1);
    const areas = result.removed || {};
    $('#artifacts').replaceChildren();
    $('#job-status').textContent = 'Not started'; $('#job-status').className = 'pill neutral';
    $('#build-progress').value = 0; $('#build-percent').textContent = '0%';
    $('#build-phase').textContent = 'Ready to start'; $('#elapsed-time').textContent = 'Elapsed time: 0:00';
    $('#friendly-status').textContent = 'Workspace files and expired diagnostic links were cleared. Archived ISO and USB files are unchanged.';
    $('#cancel-build').hidden = true;
    await showNotice('Workspace cleanup complete', `${result.removed_items} items (${mb} MB) removed and ${result.cleared_artifacts || 0} expired download links cleared.\n\nUploads: ${areas.uploads || 0} · Work: ${areas.work || 0} · Raw output: ${areas.output || 0}\nCompleted archive files were kept.`);
    currentJob = null; pollActivity(); loadStorage();
  } catch (error) { await showNotice('Could not clear workspace', error.message); }
};
$('#copy-log').onclick = () => copyText($('#log').textContent, $('#copy-log'), 'Copy log');
$('#cancel-build').onclick = async () => {
  if (currentJob && await showConfirmation('Stop current build?', 'The active build will be stopped. Your uploaded source files will be kept.', 'Stop build', true)) {
    try { await api(`/api/jobs/${currentJob}`, {method:'DELETE'}); poll(); }
    catch (error) { await showNotice('Could not stop build', error.message); }
  }
};
$('#manual-package-list').addEventListener('change', () => { packageListEdited=true; syncManualPackageValue(); });
document.querySelectorAll('[name=package_selection_mode]').forEach(control=>control.addEventListener('change',updatePackageSelectionMode));
$('#refresh-smu-plan').onclick=refreshSmuRecommendation;
$('#use-automatic-packages').onclick=async()=>{
  packageListEdited=false; $('[name=pkglist_override]').value=''; $('[name=package_selection_mode][value=automatic]').checked=true; updatePackageSelectionMode();
  await refreshSmuRecommendation(); updateBuildAvailability();
};
$('[name=iso_override]').addEventListener('change',()=>{
  const match=$('[name=iso_override]').value.match(/-(\d+\.\d+\.\d+)(?:[-.]|$)/);
  updateAutomaticTargetRelease(match?.[1] || '');
  refreshSmuRecommendation();
});
$('[name=target_release]').addEventListener('input',()=>{ targetReleaseIsAutomatic=false; });
$('[name=platform]').addEventListener('change',()=>{ updatePlatformControls(); refreshExpectedOutput(); });
$('#check-compatibility').onclick=checkCompatibility;
document.querySelectorAll('[name=compatibility_mode]').forEach(control=>control.addEventListener('change', updateCompatibilityMode));
updateCompatibilityMode();
updatePackageSelectionMode();

api('/api/cisco/config').then(config => { $('#cisco-download').hidden = !config.enabled; }).catch(() => {});
health(); loadVersion(); loadStorage(); loadPlatforms(); loadInputs(); loadArchive(); restoreJob();
setTimeout(watchInventory, INVENTORY_WATCH_MS);
