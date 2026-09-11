let currentJob = null;
let inputs = { files: [], recommended: [] };
let packageListEdited = false;
const $ = selector => document.querySelector(selector);
const lines = value => value.split(/\n|,/).map(item => item.trim()).filter(Boolean);
const api = (url, options = {}) => fetch(url, options).then(async response => {
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'An unexpected error occurred');
  return body;
});

function setReadyCard(selector, ready, text) {
  const card = $(selector);
  card.className = `ready-card ${ready ? 'ready' : 'missing'}`;
  card.querySelector('.ready-icon').textContent = ready ? '✓' : '!';
  card.querySelector('p').textContent = text;
}

function renderInputs(data) {
  inputs = data;
  const isoFiles = data.files.filter(file => file.type === '.iso');
  const addOptions = (selector, files) => {
    const list = $(selector); list.replaceChildren();
    files.forEach(file => { const option = document.createElement('option'); option.value = file.path; list.appendChild(option); });
  };
  addOptions('#iso-files', isoFiles);
  const yamlFiles = data.files.filter(file => ['.yaml', '.yml'].includes(file.type));
  addOptions('#yaml-files', yamlFiles);
  addOptions('#all-files', data.files);

  const iso = isoFiles[0]?.path || '';
  $('[name=iso]').value = iso;
  if (!packageListEdited) $('[name=pkglist]').value = data.recommended.join('\n');
  setReadyCard('#iso-check', Boolean(iso), iso ? 'Found and ready' : 'Upload the Cisco base file');
  setReadyCard('#rpm-check', data.recommended.length > 0, data.recommended.length ? `${data.recommended.length} updates found` : 'Upload at least one SMU file');

  const library = $('#file-library'); library.replaceChildren();
  if (iso) library.appendChild(fileRow('Base image', iso));
  if (data.recommended.length) library.appendChild(fileRow('Updates', `${data.recommended.length} RPM files selected automatically`));
  if (!iso && !data.recommended.length) {
    const empty = document.createElement('p'); empty.textContent = 'No Cisco files have been found yet.'; empty.className = 'empty'; library.appendChild(empty);
  }
  updateBuildAvailability();
}

function updateBuildAvailability() {
  const yamlMode = $('[name=mode]:checked').value === 'yaml';
  const ready = yamlMode
    ? Boolean($('[name=yamlfile]').value.trim())
    : Boolean(($('[name=iso_override]').value || $('[name=iso]').value) && inputs.recommended.length);
  const button = $('#start-build'); button.disabled = !ready;
  button.textContent = ready ? 'Start build' : `Waiting for ${yamlMode ? 'a YAML file' : 'Cisco files'}…`;
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

async function loadArchive() {
  try {
    const items = await api('/api/archive');
    const list = $('#archive-list'); list.replaceChildren();
    if (!items.length) { const empty=document.createElement('p'); empty.className='empty'; empty.textContent='No archived GISO images yet.'; list.appendChild(empty); return; }
    items.forEach(item => {
      const row=document.createElement('div'); row.className='archive-row';
      const link=document.createElement('a'); link.href=item.url;
      const name=document.createElement('span'); name.textContent=item.name;
      const meta=document.createElement('small'); meta.textContent=`${new Date(item.created*1000).toLocaleString()} · ${(item.size/1073741824).toFixed(2)} GB ↓`;
      const remove=document.createElement('button'); remove.type='button'; remove.className='delete-archive'; remove.textContent='Delete';
      const isIso=item.name.toLowerCase().endsWith('.iso');
      name.textContent=`${isIso ? 'Golden ISO' : 'USB boot image'} · ${item.name}`;
      const guide=document.createElement('button'); guide.type='button'; guide.className='secondary small'; guide.textContent='Upgrade guide';
      guide.hidden=!isIso; guide.onclick=()=>openUpgradeGuide(item.name);
      const checksums=document.createElement('div'); checksums.className='checksums';
      const showChecksums=document.createElement('button'); showChecksums.type='button'; showChecksums.className='secondary small'; showChecksums.textContent='Show MD5 / SHA-256';
      showChecksums.onclick=async()=>{
        showChecksums.disabled=true; showChecksums.textContent='Calculating…';
        try {
          const sums=await api(`/api/archive/${encodeURIComponent(item.job_id)}/${encodeURIComponent(item.name)}/checksums`);
          checksums.replaceChildren(checksumRow('MD5',sums.md5),checksumRow('SHA-256',sums.sha256));
          showChecksums.remove();
        } catch(error){ showChecksums.disabled=false; showChecksums.textContent='Show MD5 / SHA-256'; alert(error.message); }
      };
      remove.onclick=async()=>{
        if(!confirm(`Permanently delete this GISO artifact?\n\n${item.name}\n\nThis cannot be undone.`)) return;
        try { await api(`/api/archive/${encodeURIComponent(item.job_id)}/${encodeURIComponent(item.name)}`,{method:'DELETE'}); await loadArchive(); }
        catch(error){ alert(error.message); }
      };
      const actions=document.createElement('div'); actions.className='archive-actions'; actions.append(guide,showChecksums,remove);
      link.append(name,meta); row.append(link,actions,checksums); list.appendChild(row);
    });
  } catch (error) { $('#archive-list').textContent=error.message; }
}

function checksumRow(label, value) {
  const row=document.createElement('div'); row.className='checksum-row';
  const name=document.createElement('b'); name.textContent=label;
  const code=document.createElement('code'); code.textContent=value;
  const copy=document.createElement('button'); copy.type='button'; copy.className='secondary small'; copy.textContent='Copy';
  copy.onclick=async()=>{await navigator.clipboard.writeText(value); copy.textContent='Copied'; setTimeout(()=>copy.textContent='Copy',1200);};
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
  apply.hidden=true; apply.textContent='';
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
  } else {
    install.textContent=`install replace /harddisk:/${filename}`;
    note.textContent='This workflow may apply changes and reload automatically. Confirm the exact command options in the platform and release guide, and avoid noprompt during a supervised change.';
  }
}

async function health() {
  try {
    const state = await api('/api/health');
    $('#health').textContent = state.docker ? '✓ System ready' : 'Docker is not ready';
    $('#health').className = `pill ${state.docker ? 'ok' : 'bad'}`;
  } catch { $('#health').textContent = 'System unavailable'; $('#health').className = 'pill bad'; }
}

document.querySelectorAll('[name=mode]').forEach(radio => radio.addEventListener('change', event => {
  const yaml = event.target.value === 'yaml';
  $('#form-mode').hidden = yaml; $('#yaml-mode').hidden = !yaml;
  updateBuildAvailability();
}));
$('[name=yamlfile]').addEventListener('input', updateBuildAvailability);
$('[name=iso_override]').addEventListener('input', updateBuildAvailability);

$('#build-form').addEventListener('submit', async event => {
  event.preventDefault(); $('#error').textContent = '';
  const form = new FormData(event.target);
  const yamlMode = form.get('mode') === 'yaml';
  const payload = {
    iso: form.get('iso_override') || form.get('iso'),
    yamlfile: yamlMode ? form.get('yamlfile') : '',
    label: form.get('label_override') || form.get('label'),
    pkglist: lines(form.get('pkglist_override') || form.get('pkglist') || ''),
    repo: lines(form.get('repo') || ''), auto_repo: true,
    bridging_fixes: lines(form.get('bridging_fixes') || ''),
    remove_packages: lines(form.get('remove_packages') || ''),
    only_support_pids: lines(form.get('only_support_pids') || ''),
    xrconfig: form.get('xrconfig') || '', ztp_ini: form.get('ztp_ini') || '', script: form.get('script') || '',
    key_request: form.get('key_request') || '', ownership_vouchers: form.get('ownership_vouchers') || '',
    ownership_certificate: form.get('ownership_certificate') || ''
  };
  event.target.querySelectorAll('input[type=checkbox]').forEach(box => { payload[box.name] = box.checked; });
  const message = `Start the build with ${payload.pkglist.length} updates?\n\nAfter a successful build, the verified Golden ISO and USB boot image will be kept. Uploaded source files and other build output will be permanently removed.`;
  if (!confirm(message)) return;
  const button = $('#start-build'); button.disabled = true; button.textContent = 'Starting…';
  try { const result = await api('/api/jobs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }); currentJob = result.id; poll(); }
  catch (error) { $('#error').textContent = error.message; button.disabled = false; button.textContent = 'Start build'; }
});

async function poll() {
  if (!currentJob) return;
  try {
    const job = await api(`/api/jobs/${currentJob}`);
    const labels = {running:'Building', queued:'Waiting', cancelling:'Stopping', success:'Complete', failed:'Failed', cancelled:'Stopped'};
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
    $('#friendly-status').textContent = job.status === 'success' ? 'Your new image is ready. Download it using the green link below.' : job.status === 'failed' ? 'The build could not be completed. Open the technical details to see why.' : job.status === 'cancelled' ? 'The build was stopped. Your uploaded files are still saved.' : 'The build is running. You may leave this page open or return later.';
    const artifacts = $('#artifacts'); artifacts.replaceChildren();
    job.artifacts.forEach(artifact => {
      const link = document.createElement('a'); link.href = artifact.url || `/download/${encodeURIComponent(job.id)}/${artifact.path.split('/').map(encodeURIComponent).join('/')}`;
      const name = document.createElement('span'); name.textContent = artifact.path.endsWith('.iso') ? 'Download completed ISO image' : `Download ${artifact.path}`;
      const size = document.createElement('small'); size.textContent = `${(artifact.size/1048576).toFixed(1)} MB ↓`;
      link.append(name, size); artifacts.appendChild(link);
    });
    if (['running','queued','cancelling'].includes(job.status)) setTimeout(poll, 1500); else { await loadInputs(); await loadArchive(); }
  } catch (error) { $('#friendly-status').textContent = error.message; }
}

async function restoreJob() {
  try {
    const jobs = await api('/api/jobs');
    const job = jobs.find(item => ['running','queued','cancelling'].includes(item.status)) || jobs[0];
    if (job) { currentJob = job.id; poll(); }
  } catch { /* Starts clean if there is no previous job. */ }
}

const CHUNK = 16 * 1024 * 1024;
async function uploadFile(file) {
  const row = document.createElement('div'); row.className = 'upload-row';
  const name = document.createElement('span'); name.textContent = file.name;
  const progress = document.createElement('progress'); progress.max = 100; progress.value = 0;
  progress.setAttribute('aria-label', `Upload progress for ${file.name}`);
  const status = document.createElement('small'); status.textContent = 'Starting…'; row.append(name, progress, status); $('#upload-list').appendChild(row);
  try {
    const upload = await api('/api/uploads/init', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:file.name,size:file.size})});
    let offset = 0;
    while (offset < file.size) {
      const blob = file.slice(offset, Math.min(offset + CHUNK, file.size));
      await api(`/api/uploads/${upload.id}?offset=${offset}`, {method:'PUT', body:blob}); offset += blob.size;
      const percent = Math.round(offset / file.size * 100); progress.value = percent; status.textContent = `${percent}%`;
    }
    const done = await api(`/api/uploads/${upload.id}/complete`, {method:'POST'});
    row.classList.add('done'); status.textContent = done.extracted ? `Ready – ${done.extracted} files extracted` : 'Ready and saved';
    packageListEdited = false; await loadInputs();
  } catch (error) { row.classList.add('upload-error'); status.textContent = error.message; }
}
async function uploadFiles(files) { for (const file of files) await uploadFile(file); }
$('#choose-files').onclick = () => $('#file-upload').click();
$('#file-upload').onchange = event => uploadFiles(event.target.files);
const drop = $('#drop-zone');
['dragenter','dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add('drag'); }));
['dragleave','drop'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', event => uploadFiles(event.dataTransfer.files));
$('#refresh').onclick = loadInputs;
$('#refresh-archive').onclick = loadArchive;
$('#general-guide').onclick = () => openUpgradeGuide('GOLDEN-ISO.iso');
$('#close-guide').onclick = () => $('#upgrade-guide').close();
$('#guide-family').onchange = updateGuideWorkflow;
$('#copy-guide').onclick = async () => {
  const commands=[...$('#upgrade-guide').querySelectorAll('pre')].map(pre=>pre.textContent).join('\n\n');
  await navigator.clipboard.writeText(commands); $('#copy-guide').textContent='Copied'; setTimeout(()=>$('#copy-guide').textContent='Copy commands',1200);
};
$('#cleanup').onclick = async () => {
  if (!confirm('Remove temporary upload fragments and build working files?\n\nUploaded Cisco files and completed images will be kept.')) return;
  try {
    const result = await api('/api/cleanup', {method:'POST'});
    const mb = (result.removed_bytes / 1048576).toFixed(1);
    alert(`Cleanup complete. ${result.removed_items} temporary items (${mb} MB) removed.\n\nUploads and completed images were kept.`);
  } catch (error) { alert(error.message); }
};
$('#copy-log').onclick = () => navigator.clipboard.writeText($('#log').textContent);
$('#cancel-build').onclick = async () => { if (currentJob && confirm('Stop the build? Your uploaded files will be kept.')) { await api(`/api/jobs/${currentJob}`, {method:'DELETE'}); poll(); } };
$('[name=pkglist_override]').addEventListener('input', () => { packageListEdited = true; });

health(); loadInputs(); loadArchive(); restoreJob();
