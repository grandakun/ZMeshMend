$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$buildDir  = Join-Path $scriptDir 'build'

$cmakeCmd = Get-Command cmake -ErrorAction SilentlyContinue
if ($cmakeCmd) {
    $cmake = $cmakeCmd.Source
} else {
    $cmakeCandidates = @(
        'C:\Program Files\CMake\bin\cmake.exe',
        'C:\tools\cmake\bin\cmake.exe'
    )
    $cmake = $cmakeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $cmake -or -not (Test-Path $cmake)) {
    throw 'cmake.exe not found. Please install CMake or add it to PATH.'
}

$vcpkgCandidates = @()
if ($env:VCPKG_ROOT) { $vcpkgCandidates += $env:VCPKG_ROOT }
$vcpkgCandidates += @(
    'C:\vcpkg',
    'C:\dev\vcpkg',
    'C:\tools\vcpkg',
    (Join-Path $env:USERPROFILE 'vcpkg'),
    (Join-Path $env:USERPROFILE 'Desktop\vcpkg\vcpkg-master')
)

$toolchain = $null
foreach ($candidate in $vcpkgCandidates) {
    if (-not $candidate) { continue }
    $candidateToolchain = Join-Path $candidate 'scripts\buildsystems\vcpkg.cmake'
    if (Test-Path $candidateToolchain) {
        $toolchain = $candidateToolchain
        break
    }
}

if (-not $toolchain) {
    throw 'vcpkg toolchain not found. Please install vcpkg and set VCPKG_ROOT, or place it in a common location such as C:\vcpkg.'
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
