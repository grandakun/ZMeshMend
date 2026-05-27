@echo off
REM =============================================
REM ZMeshMend CGAL Core - One-Click Build Script
REM =============================================
REM
REM Prerequisites (one-time setup):
REM   1. Visual Studio 2019/2022 with "Desktop C++" workload
REM   2. CMake 3.16+ (auto-detected; or place on PATH)
REM   3. vcpkg with CGAL installed:
REM        cd C:\path\to\vcpkg
REM        .\bootstrap-vcpkg.bat
REM        .\vcpkg install cgal:x64-windows
REM
REM Then just run: build.bat
REM =============================================

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set BUILD_DIR=%SCRIPT_DIR%build
set OUTPUT_NAME=zmeshmend_core.exe

echo.
echo ============================================
echo  ZMeshMend CGAL Core Build
echo ============================================
echo.

REM ----- Find CMake -----
set CMAKE_BIN=
where cmake >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set CMAKE_BIN=cmake
    echo [OK] CMake found on PATH
) else (
    REM Try common install locations
    for %%d in (
        "C:\Program Files\CMake\bin"
    ) do (
        if exist "%%~d\cmake.exe" (
            set "CMAKE_BIN=%%~d\cmake.exe"
            echo [OK] CMake found at %%~d
            goto :cmake_ok
        )
    )
    echo [ERROR] CMake not found!
    echo   Download from: https://cmake.org/download/
    echo   Or install via: winget install Kitware.CMake
    exit /b 1
)
:cmake_ok

REM ----- Find vcpkg -----
set VCPKG_TOOLCHAIN=
for %%d in (
    "C:\vcpkg"
    "C:\dev\vcpkg"
    "C:\tools\vcpkg"
    "%USERPROFILE%\Desktop\vcpkg\vcpkg-master"
    "%USERPROFILE%\vcpkg"
) do (
    if exist "%%~d\scripts\buildsystems\vcpkg.cmake" (
        set "VCPKG_TOOLCHAIN=%%~d\scripts\buildsystems\vcpkg.cmake"
        set "VCPKG_ROOT=%%~d"
        echo [OK] vcpkg found at %%~d
        goto :vcpkg_ok
    )
)
echo [ERROR] vcpkg not found!
echo   Setup vcpkg:
echo     1. git clone https://github.com/microsoft/vcpkg.git C:\vcpkg
echo     2. cd C:\vcpkg ^&^& bootstrap-vcpkg.bat
echo     3. vcpkg install cgal:x64-windows
exit /b 1
:vcpkg_ok

REM ----- Check CGAL -----
if not exist "%VCPKG_ROOT%\installed\x64-windows\include\CGAL\" (
    echo [WARN] CGAL not yet installed via vcpkg.
    echo   Installing CGAL now...
    call "%VCPKG_ROOT%\vcpkg.exe" install cgal:x64-windows
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install CGAL.
        echo   Try manually: vcpkg install cgal:x64-windows
        exit /b 1
    )
    echo [OK] CGAL installed successfully.
) else (
    echo [OK] CGAL headers found
)

REM ----- Clean -----
if exist "%BUILD_DIR%" (
    echo [CLEAN] Removing previous build...
    rmdir /s /q "%BUILD_DIR%"
)

REM ----- Configure -----
echo.
echo [CONFIGURE] Running CMake...
set CMAKE_ARGS=-S "%SCRIPT_DIR%" -B "%BUILD_DIR%" -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE="%VCPKG_TOOLCHAIN%"
"%CMAKE_BIN%" %CMAKE_ARGS%

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] CMake configuration failed.
    exit /b 1
)

REM ----- Build -----
echo.
echo [BUILD] Compiling...
"%CMAKE_BIN%" --build "%BUILD_DIR%" --config Release --parallel

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed.
    exit /b 1
)

REM ----- Output -----
set EXE_PATH=%BUILD_DIR%\Release\%OUTPUT_NAME%
if exist "%EXE_PATH%" (
    copy /y "%EXE_PATH%" "%SCRIPT_DIR%%OUTPUT_NAME%" >nul
    echo.
    echo ============================================
    echo   BUILD SUCCESS!
    echo   Output: %SCRIPT_DIR%%OUTPUT_NAME%
    echo ============================================
    echo   Plugin will auto-detect this EXE on next load.
) else (
    echo [ERROR] Build succeeded but executable not found at:
    echo   %EXE_PATH%
    exit /b 1
)

endlocal
