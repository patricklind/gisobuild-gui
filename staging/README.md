# Safe staging rehearsal

This isolated simulator validates the order and safety gates of the staged IOS
XR7 upgrade and rollback workflow. It never connects to, configures, or reloads
a router and is not proof that a release is compatible with real hardware.

```bash
docker compose -f staging/compose.yaml build
docker compose -f staging/compose.yaml run --rm xr-simulator <<'EOF'
show version
show platform
show install request
install package replace /harddisk:/staging-giso.iso
install apply reload
install commit
install package rollback 1
install apply rollback reload
install commit
EOF

python3 staging/rehearse.py
```

Before production, repeat the runbook in a lab router matching the production
PID, route processor, source release, target release, ROMMON and package set.
The validation levels and reporting language are defined in
[`docs/testing.md`](../docs/testing.md).
