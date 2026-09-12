param(
  [Parameter(Position=0, Mandatory=$true)][ValidateSet('status','claim','done','release')][string]$Command,
  [Parameter(Position=1)][string]$Module,
  [Parameter(Position=2)][string]$Note
)
$ErrorActionPreference = 'Stop'
$root = (git rev-parse --show-toplevel).Trim()
$board = if ($env:GISO_COORD_DIR) { $env:GISO_COORD_DIR } else { Join-Path (Split-Path $root) '.gisobuild-coordination' }
$claims = Join-Path $board 'claims'
New-Item -ItemType Directory -Force -Path $claims | Out-Null
if ($Command -eq 'status') {
  $items = Get-ChildItem $claims -Directory
  if (-not $items) { Write-Output 'No active module claims.' }
  foreach ($item in $items) {
    $owner = Get-Content (Join-Path $item.FullName 'owner') -ErrorAction SilentlyContinue | Select-Object -First 1
    $state = Get-Content (Join-Path $item.FullName 'state') -ErrorAction SilentlyContinue | Select-Object -First 1
    $noteText = Get-Content (Join-Path $item.FullName 'note') -ErrorAction SilentlyContinue | Select-Object -First 1
    '{0,-24} {1,-10} {2,-24} {3}' -f $item.Name,$state,$owner,$noteText
  }
  exit
}
if ($Module -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') { throw 'Invalid module name.' }
$target = Join-Path $claims $Module
if ($Command -eq 'claim') {
  if (-not $Note) { throw 'A short note is required.' }
  New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null
  "$env:USERNAME@$env:COMPUTERNAME`:$(git branch --show-current)" | Set-Content (Join-Path $target 'owner')
  $Note | Set-Content (Join-Path $target 'note')
  'claimed' | Set-Content (Join-Path $target 'state')
} elseif ($Command -eq 'done') {
  if (-not (Test-Path $target)) { throw "Module '$Module' is not claimed." }
  'done' | Set-Content (Join-Path $target 'state')
} else {
  if (-not (Test-Path $target)) { throw "Module '$Module' is not claimed." }
  Remove-Item -Recurse -Force $target
}
