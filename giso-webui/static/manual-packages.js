/* Manual package selection uses opaque inventory IDs. Workspace paths are
 * presentation-only and are never submitted as package identifiers.
 */
(() => {
  let manualSelectionInitialized = false;

  const basename = value => String(value || '').split('/').pop();

  function logicalRpms(files) {
    const groups = new Map();
    files.filter(file => file.type === '.rpm').forEach(file => {
      const key = file.basename || basename(file.path);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(file);
    });
    return [...groups.entries()].flatMap(([name, matches]) => {
      const hashes = new Set(matches.map(file => file.sha256));
      if (hashes.size > 1) return matches.map(file => ({...file, name, conflict: true}));
      return [{...matches[0], name, provenance: matches.map(file => file.relative_path || file.path),
        identicalCopies: matches.length}];
    });
  }

  function appendPackage(section, file, options = {}) {
    const reason = options.reason || (file.conflict
      ? 'Blocked: another RPM has the same filename but different content. Remove the unwanted copy.'
      : 'Compatible RPM without a detected CSC group');
    const label = document.createElement('label');
    label.className = `manual-package-option${options.reason || file.conflict ? ' incompatible' : ''}`;
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.className = 'manual-rpm-checkbox';
    box.value = file.id;
    if (options.csc) box.dataset.csc = options.csc;
    box.disabled = Boolean(options.reason || file.conflict);
    box.checked = !box.disabled && options.checked;
    const copy = document.createElement('span');
    const strong = document.createElement('b');
    strong.textContent = file.name;
    const small = document.createElement('small');
    const provenance = file.provenance || [file.relative_path || file.path];
    const identity = `SHA-256 ${file.sha256.slice(0, 12)}…`;
    small.textContent = file.conflict
      ? `${reason} ${identity}; source: ${file.relative_path || file.path}`
      : file.identicalCopies > 1
        ? `${file.identicalCopies} identical copies deduplicated; sources: ${provenance.join(', ')}; ${identity}`
        : `${reason}; source: ${provenance[0]}; ${identity}`;
    copy.append(strong, small);
    label.append(box, copy);
    section.appendChild(label);
  }

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
    const previous = new Set(lines(document.querySelector('[name=pkglist_override]').value));
    const recommended = new Set((plan.selected || data.recommended || []).map(basename));
    const excluded = new Map((plan.excluded || []).map(item => [basename(item.name), item.reason]));
    const rpms = logicalRpms(data.files);

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

    const byName = new Map();
    rpms.forEach(file => {
      if (!byName.has(file.name)) byName.set(file.name, []);
      byName.get(file.name).push(file);
    });
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

      members.forEach(name => byName.get(name).forEach(file => appendPackage(section, file, {
        csc: group.csc,
        checked: usePrevious ? previous.has(file.id) : recommended.has(name),
      })));
      list.appendChild(section);
    });

    const other = rpms.filter(file => !groupedNames.has(file.name));
    if (other.length) {
      const section = document.createElement('fieldset');
      section.className = 'manual-csc-group';
      const legend = document.createElement('legend');
      legend.textContent = 'Other RPM packages';
      section.appendChild(legend);
      other.forEach(file => {
        const reason = excluded.get(file.name);
        appendPackage(section, file, {reason,
          checked: usePrevious ? previous.has(file.id) : recommended.has(file.name)});
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
