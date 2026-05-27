$ErrorActionPreference = 'Stop'
$scriptDir = 'c:\Users\Administrator\Desktop\ZMeshMend\ZMeshMend\ZMeshMendData'
$buildDir  = Join-Path $scriptDir 'build'
$cmake     = 'C:\Users\Administrator\cmake\cmake-4.3.2-windows-x86_64\bin\cmake.exe'
if (-not (Test-Path $cmake)) {
    $cmake = 'C:\tools\cmake\cmake-4.3.3-windows-x86_64\bin\cmake.exe'
}
$vcpkg     = 'C:\Users\Administrator\Desktop\vcpkg'
$toolchain = Join-Path $vcpkg 'scripts\buildsystems\vcpkg.cmake'

if (-not (Test-Path $toolchain)) {
    Write-Host "toolchain not at $toolchain, searching..."
    $found = Get-ChildItem -Path $vcpkg -Recurse -Filter 'vcpkg.cmake' -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'buildsystems' } | Select-Object -First 1
    if ($found) { $toolchain = $found.FullName; Write-Host "found at $toolchain" }
}

Write-Host "Using cmake: $cmake"
Write-Host "Using toolchain: $toolchain"

if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }

$cfgArgs = @(
    '-S', $scriptDir,
    '-B', $buildDir,
    '-DCMAKE_BUILD_TYPE=Release',
    "-DCMAKE_TOOLCHAIN_FILE=$toolchain"
)
& $cmake @cfgArgs
if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }

# No --parallel: avoids MSBuild Access violation seen on cmake 4.3.3 + VS17.4
& $cmake --build $buildDir --config Release
if ($LASTEXITCODE -ne 0) { throw "cmake build failed" }

$src = Join-Path $buildDir 'Release\zmeshmend_core.exe'
$dst = Join-Path $scriptDir 'zmeshmend_core.exe'
Copy-Item -Force $src $dst
Write-Host "OK -> $dst ($((Get-Item $dst).Length) bytes)"
