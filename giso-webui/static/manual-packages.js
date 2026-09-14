/* Manual package selection fixes layered on top of app.js.
 * Keep package values as RPM basenames because the build backend accepts
 * package names, not extracted workspace paths.
 */
(() => {
  let manualSelectionInitialized = false;

  const basename = value => String(value || '').split('/').pop();

  window.selectedManualPackages = function selectedManualPackages() {
    return [...document.querySelectorAll('#manual-package-list .manual-rpm-checkbox:checked')]
      .map(box => box.value);
  };

  window.syncManualPackageValue = function syncManualPackageValue() {
    const selected = window.selectedManualPackages();
    const all = [...document.querySelectorAll('#manual-package-list .manual-rpm-checkbox')];
    document.querySelector('[name=pkglist_override]').value = selected.join('\n');
    document.querySelector('#manual-package-summary').textContent =
      `${selected.length} of ${all.length} RPM packages selected.`;

    document.querySelectorAll('#manual-package-list .manual-csc-checkbox').forEach(groupBox => {
      const members = [...document.querySelectorAll(
        `#manual-package-list .manual-rpm-checkbox[data-csc="${CSS.escape(groupBox.dataset.csc)}"]`
      )];
      const checked = members.filter(box => box.checked).length;
      groupBox.checked = members.length > 0 && checked === members.length;
      groupBox.indeterminate = checked > 0 && checked < members.length;
    });
    updateBuildAvailability();
  };

  window.renderManualPackages = function renderManualPackages(data, plan) {
    const list = document.querySelector('#manual-package-list');
    const previous = new Set(lines(document.querySelector('[name=pkglist_override]').value).map(basename));
    const recommended = new Set((plan.selected || data.recommended || []).map(basename));
    const excluded = new Map((plan.excluded || []).map(item => [basename(item.name), item.reason]));
    const rpms = data.files.filter(file => file.type === '.rpm');

    if (!packageListEdited) manualSelectionInitialized = false;
    list.replaceChildren();

    if (!rpms.length) {
      const empty = document.createElement('div');
      empty.className = 'manual-package-empty';
      const message = document.createElement('p');
      message.textContent = 'No RPM files are available in the workspace. Upload individual .rpm files or a Cisco .tar/.tgz SMU bundle first.';
      const upload = document.createElement('button');
      upload.type = 'button';
      upload.className = 'secondary small';
      upload.textContent = 'Upload RPM / SMU files';
      upload.onclick = () => document.querySelector('#file-upload').click();
      empty.append(message, upload);
      list.appendChild(empty);
      document.querySelector('#manual-package-summary').textContent = 'No RPM packages available.';
      document.querySelector('[name=pkglist_override]').value = '';
      updateBuildAvailability();
      return;
    }

    const byName = new Map(rpms.map(file => [basename(file.path), file]));
    const groupedNames = new Set();
    const usePrevious = manualSelectionInitialized;

    (plan.package_groups || []).forEach(group => {
      const members = group.files.map(basename).filter(name => byName.has(name));
      if (!members.length) return;
      members.forEach(name => groupedNames.add(name));

      const section = document.createElement('fieldset');
      section.className = 'manual-csc-group';
      const legend = document.createElement('legend');
      const groupLabel = document.createElement('label');
      const groupBox = document.createElement('input');
      groupBox.type = 'checkbox';
      groupBox.className = 'manual-csc-checkbox';
      groupBox.dataset.csc = group.csc;
      const title = document.createElement('span');
      title.textContent = `${group.csc} — ${group.relationship}`;
      groupLabel.append(groupBox, title);
      legend.appendChild(groupLabel);
      section.appendChild(legend);

      members.forEach(name => {
        const file = byName.get(name);
        const label = document.createElement('label');
        label.className = 'manual-package-option';
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.className = 'manual-rpm-checkbox';
        box.value = name;
        box.dataset.csc = group.csc;
        box.checked = usePrevious ? previous.has(name) : recommended.has(name);
        const copy = document.createElement('span');
        const strong = document.createElement('b');
        strong.textContent = name;
        const small = document.createElement('small');
        small.textContent = file.path === name ? 'Uploaded RPM' : `Extracted from ${file.path.slice(0, -name.length).replace(/\/$/, '')}`;
        copy.append(strong, small);
        label.append(box, copy);
        section.appendChild(label);
      });
      list.appendChild(section);
    });

    const other = rpms.filter(file => !groupedNames.has(basename(file.path)));
    if (other.length) {
      const section = document.createElement('fieldset');
      section.className = 'manual-csc-group';
      const legend = document.createElement('legend');
      legend.textContent = 'Other RPM packages';
      section.appendChild(legend);
      other.forEach(file => {
        const name = basename(file.path);
        const reason = excluded.get(name);
        const label = document.createElement('label');
        label.className = `manual-package-option${reason ? ' incompatible' : ''}`;
        const box = document.createElement('input');
        box.type = 'checkbox';
        box.className = 'manual-rpm-checkbox';
        box.value = name;
        box.disabled = Boolean(reason);
        box.checked = !reason && (usePrevious ? previous.has(name) : recommended.has(name));
        const copy = document.createElement('span');
        const strong = document.createElement('b');
        strong.textContent = name;
        const small = document.createElement('small');
        small.textContent = reason || 'Compatible RPM without a detected CSC group';
        copy.append(strong, small);
        label.append(box, copy);
        section.appendChild(label);
      });
      list.appendChild(section);
    }

    manualSelectionInitialized = true;
    window.syncManualPackageValue();
  };

  document.querySelector('#manual-package-list').addEventListener('change', event => {
    if (!event.target.classList.contains('manual-csc-checkbox')) return;
    const csc = event.target.dataset.csc;
    document.querySelectorAll(
      `#manual-package-list .manual-rpm-checkbox[data-csc="${CSS.escape(csc)}"]`
    ).forEach(box => { if (!box.disabled) box.checked = event.target.checked; });
    packageListEdited = true;
    manualSelectionInitialized = true;
    window.syncManualPackageValue();
  });

  document.querySelector('#use-automatic-packages').addEventListener('click', () => {
    manualSelectionInitialized = false;
  });
})();
