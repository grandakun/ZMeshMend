$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcTxt = Join-Path $repoRoot 'ZMeshMend\ZMeshMend_ZScript.txt'

$zbRoot = 'D:\Program Files\Pixologic\ZBrush 2022\ZStartup\ZPlugs64'
$dstTxt = Join-Path $zbRoot 'ZMeshMend_ZScript.txt'
$dstTxtBak = Join-Path $zbRoot 'ZMeshMend_ZScript.txt.bak'
$dstDataDir = Join-Path $zbRoot 'ZMeshMendData'
$dstCfg = Join-Path $dstDataDir 'zmeshmend_config.txt'
$dstCfgBak = Join-Path $dstDataDir 'zmeshmend_config.txt.bak'
$dstZsc = Join-Path $zbRoot 'ZMeshMend_ZScript.zsc'

if (-not (Test-Path $srcTxt)) {
    throw "Source file not found: $srcTxt"
}

if (-not (Test-Path $dstDataDir)) {
    throw "Target folder not found: $dstDataDir"
}

if (Test-Path $dstTxt) {
    Copy-Item $dstTxt $dstTxtBak -Force
}

Copy-Item $srcTxt $dstTxt -Force

$cfgLines = @(
    'fillDensity=1.0'
    'maskSharpenPasses=1'
    'maskGrowRings=1'
    'removeSmallFragments=1'
    'fragmentMinFraction=0.01'
    'fragmentMinFaces=50'
    'smoothBorder=0'
    'relaxWireframe=0'
    'smoothIterations=2'
    'smoothRings=3'
    'relaxIterations=3'
    'relaxFactor=1.0'
)

if (Test-Path $dstCfg) {
    Copy-Item $dstCfg $dstCfgBak -Force
}

[System.IO.File]::WriteAllText($dstCfg, ($cfgLines -join "`r`n") + "`r`n", [System.Text.Encoding]::ASCII)

Write-Host 'Deploy complete.' -ForegroundColor Green
Write-Host "Patched TXT: $dstTxt"
Write-Host "Backup TXT:  $dstTxtBak"
Write-Host "Clean CFG:   $dstCfg"
Write-Host "Backup CFG:  $dstCfgBak"

if (Test-Path $dstZsc) {
    Write-Host ''
    Write-Host "Compiled file still exists: $dstZsc" -ForegroundColor Yellow
    Write-Host 'If ZBrush still loads the old behavior, delete that .zsc and reload ZMeshMend_ZScript.txt once.'
}
