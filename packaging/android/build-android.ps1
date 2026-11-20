<#
.SYNOPSIS
Builds the Android version of Harvest Moon: Animal Parade from your own disc.
Compila la versión de Android de Harvest Moon: Animal Parade desde tu propio disco.

.DESCRIPTION
Needs the Windows package, already used once to prepare the game (play.cmd or the launcher), and the
Android add-on unpacked into the same folder (it brings the Android\ folder and this script).

  1. The translator turns your main.dol into C++ again, for the Android build
     (Android\BuildWorkspace\generated, under a minute).
  2. The Android NDK's compiler that comes in the add-on compiles it together with WiiCompiled's
     runtime and aurora for 64-bit ARM (Android\BuildWorkspace\build; the first time takes a while).
  3. ApkPack puts it in the app with the game's files and signs it with a key of your own
     (UserData\android-signing.pfx, made the first time; keep it, so the next build installs over
     this one and keeps the saves). The app is AnimalParade.apk, next to this script.
  4. With a phone or tablet connected over USB with USB debugging on, it installs the app and copies
     your disc's files to it (once). Otherwise copy them yourself: see README-Android.txt.

Hace falta el paquete de Windows, ya usado una vez para preparar el juego, y el complemento de
Android descomprimido en la misma carpeta. El script traduce tu main.dol otra vez, lo compila con el
NDK de Android para ARM de 64 bits, arma la app (AnimalParade.apk) firmada con una llave tuya que se
guarda en UserData\android-signing.pfx, y si hay un teléfono o tableta conectado por USB con la
depuración USB activada, instala la app y le copia los archivos de tu disco.

.PARAMETER Rebuild
Translate and compile again even if nothing changed.
Traducir y compilar otra vez aunque nada haya cambiado.

.PARAMETER NoInstall
Only make AnimalParade.apk; do not install it on a connected device.
Solo hacer AnimalParade.apk; no instalarlo en un dispositivo conectado.
#>
[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoInstall
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

$root = $PSScriptRoot
$toolkit = Join-Path $root 'Toolkit'
$android = Join-Path $root 'Android'
$workspace = Join-Path $android 'BuildWorkspace'
$userData = Join-Path $root 'UserData'
$project = 'projects\animal-parade\recomp.yml'
$packageName = 'io.github.hmaprecomp.animalparade'
$apk = Join-Path $root 'AnimalParade.apk'

. (Join-Path $root 'BuildWorkspace\NativeBuildFlags.ps1')

function Write-Step([string]$English, [string]$Spanish) {
    Write-Host ''
    Write-Host "== $English" -ForegroundColor Cyan
    Write-Host "   $Spanish" -ForegroundColor DarkCyan
}

function Find-DiscRoot([string]$Folder) {
    foreach ($candidate in @($Folder, (Join-Path $Folder 'DATA'))) {
        if ((Test-Path -LiteralPath (Join-Path $candidate 'sys\main.dol') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $candidate 'files') -PathType Container)) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

# ---------------------------------------------------------------- what is needed

if (-not (Test-Path -LiteralPath (Join-Path $workspace 'runtime\CMakeLists.txt') -PathType Leaf)) {
    throw 'The Android add-on is not in this folder (Android\BuildWorkspace is missing). Unzip it next to play.cmd. ' +
        '/ El complemento de Android no está en esta carpeta. Descomprímelo junto a play.cmd.'
}
$addonVersion = Join-Path $android 'version.txt'
$packageVersion = Join-Path $root 'version.txt'
if ((Test-Path -LiteralPath $addonVersion) -and (Test-Path -LiteralPath $packageVersion) -and
    ((Get-Content -LiteralPath $addonVersion -Raw).Trim() -ne (Get-Content -LiteralPath $packageVersion -Raw).Trim())) {
    Write-Warning ("The Android add-on is $((Get-Content -LiteralPath $addonVersion -Raw).Trim()) and the package " +
        "$((Get-Content -LiteralPath $packageVersion -Raw).Trim()); use the add-on of the same version. " +
        '/ El complemento y el paquete son de versiones distintas.')
}

# The disc the computer version was prepared from (play.ps1 remembers it in UserData\disc.txt).
$discRoot = $null
$remembered = Join-Path $userData 'disc.txt'
if (Test-Path -LiteralPath $remembered -PathType Leaf) {
    $disc = (Get-Content -LiteralPath $remembered -Raw).Trim()
    if (Test-Path -LiteralPath $disc -PathType Leaf) {
        $discRoot = Find-DiscRoot (Join-Path $root 'Disc\DATA')
    } elseif (Test-Path -LiteralPath $disc -PathType Container) {
        $discRoot = Find-DiscRoot $disc
    }
}
if (-not $discRoot) {
    throw 'Prepare the game on this computer first (play.cmd or the launcher): the Android build uses the same disc. ' +
        '/ Prepara primero el juego en esta computadora (play.cmd o el launcher): la versión de Android usa el mismo disco.'
}
$mainDol = Join-Path $discRoot 'sys\main.dol'
Write-Host "Disc / Disco: $discRoot"

Get-ChildItem -LiteralPath $android -Recurse -File | Where-Object { $_.Extension -in '.exe', '.dll' } | Unblock-File

$workspace = Get-MkwBuildSafePath $workspace 'android-workspace' 'runtime\CMakeLists.txt'
$ndk = Get-MkwBuildSafePath (Join-Path $android 'ndk') 'android-ndk' 'build\cmake\android.toolchain.cmake'
$toolkit = Get-MkwBuildSafePath $toolkit 'toolchain' 'CMake\bin\cmake.exe'
$translator = Join-Path $toolkit 'Translator\Translator.Cli.exe'
$cmake = Join-Path $toolkit 'CMake\bin\cmake.exe'
$ninja = Join-Path $toolkit 'Ninja\ninja.exe'
$strip = Join-Path $ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-strip.exe'
$apkPack = Join-Path $android 'ApkPack\ApkPack.exe'
$shell = Join-Path $android 'AnimalParade-shell.apk'
$adb = Join-Path $android 'platform-tools\adb.exe'
foreach ($required in @($translator, $cmake, $ninja, $strip, $apkPack, $shell)) { Assert-File $required 'Package file' }

$generated = Join-Path $workspace 'generated'
$functions = Join-Path $generated 'functions'
$metadata = Join-Path $generated 'base_translation_metadata.json'
$sources = Join-Path $generated 'base_translation_sources.bin'
$shards = Join-Path $generated 'build_shards'
$build = Join-Path $workspace 'build'
$stamp = Join-Path $generated 'translated-from.txt'
$dolSha = Get-MkwFileSha256 $mainDol

$memoryGiB = [math]::Max(1, [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB))
$translatorThreads = [math]::Max(1, [math]::Min([Environment]::ProcessorCount, 16))
$translatedJobs = [math]::Max(1, [math]::Min([Environment]::ProcessorCount, [math]::Floor(($memoryGiB - 2) / 0.5)))
$globalJobs = [math]::Max($translatedJobs, [Environment]::ProcessorCount)

# ---------------------------------------------------------------- the build

$oldPath = $env:PATH
$env:PATH = (@((Join-Path $toolkit 'CMake\bin'), (Join-Path $toolkit 'Ninja'),
    (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';')
$env:RECOMP_RBIEE9_DOL = $mainDol
Push-Location $workspace
try {
    $translated = (Test-Path -LiteralPath (Join-Path $shards 'shards.cmake') -PathType Leaf) -and
        (Test-Path -LiteralPath $stamp -PathType Leaf) -and
        ((Get-Content -LiteralPath $stamp -Raw).Trim() -eq $dolSha)
    if ($Rebuild -or -not $translated) {
        Write-Step 'Translating your main.dol into C++' 'Traduciendo tu main.dol a C++'
        if (Test-Path -LiteralPath $stamp) { Remove-Item -LiteralPath $stamp -Force }
        [IO.Directory]::CreateDirectory($generated) | Out-Null
        Invoke-Checked $translator @(
            'translate-recursive', '0x80004050', '--project', $project,
            '--outdir', $functions, '--output-metadata', $metadata,
            '--production-source-bundle', $sources, '--no-function-files', '--prune-stale',
            '--threads', $translatorThreads
        ) 'Translating the game' -TimeoutSeconds 1800
        Invoke-Checked $translator @('generate-data-init', '--project', $project) `
            'Writing the game data initializer' -TimeoutSeconds 1800
        Invoke-Checked $translator @(
            'emit-build-shards', '--project', $project, '--base-metadata', $metadata,
            '--base-functions-dir', $functions,
            '--native-source-dir', (Join-Path $workspace 'projects\animal-parade\native'), '--out', $shards
        ) 'Preparing the build shards' -TimeoutSeconds 1800
        Set-Content -LiteralPath $stamp -Value $dolSha -Encoding ASCII
    } else {
        Write-Step 'The translation is current' 'La traducción está al día'
    }

    if ($Rebuild -and (Test-Path -LiteralPath $build)) { Remove-Item -LiteralPath $build -Recurse -Force }
    if (-not (Test-Path -LiteralPath (Join-Path $build 'CMakeCache.txt') -PathType Leaf)) {
        Write-Step 'Configuring the Android build' 'Configurando la compilación de Android'
        # The dependencies' sources come with the add-on (Android\BuildWorkspace\Dependencies), so
        # nothing is downloaded.
        $configure = @(
            '-S', (Join-Path $workspace 'runtime'), '-B', $build, '-G', 'Ninja',
            "-DCMAKE_MAKE_PROGRAM=$ninja",
            "-DCMAKE_TOOLCHAIN_FILE=$(Join-Path $ndk 'build\cmake\android.toolchain.cmake')",
            '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-30', '-DANDROID_STL=c++_static',
            '-DCMAKE_BUILD_TYPE=Release',
            "-DFETCHCONTENT_BASE_DIR=$(Join-Path $workspace 'Dependencies')", '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
            "-DMKW_ANDROID_NOD_DIR=$(Join-Path $android 'nod')",
            "-DMKW_TRANSLATED_COMPILE_JOBS=$translatedJobs"
        ) + (Get-Content -LiteralPath (Join-Path $android 'configure-flags.txt') | Where-Object { $_.Trim() })
        Invoke-Checked $cmake $configure 'Configuring'
    }

    Write-Step 'Compiling for Android (the first time takes a while)' 'Compilando para Android (la primera vez tarda un rato)'
    Invoke-Checked $cmake @('--build', $build, '--target', 'WiiCompiled', '--parallel', $globalJobs) 'Compiling'
} finally {
    Pop-Location
    $env:PATH = $oldPath
}

# ---------------------------------------------------------------- the app

Write-Step 'Making the app (AnimalParade.apk)' 'Armando la app (AnimalParade.apk)'
$stage = Join-Path $build 'apk'
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
$gameFiles = Join-Path $stage 'game'
[IO.Directory]::CreateDirectory($gameFiles) | Out-Null
# The files the game reads from its own folder, as on the computer (play.ps1).
foreach ($name in @('dsp_coef.bin', 'initial_pipeline_cache.db', 'cacert.pem', 'noshaders.zip')) {
    $file = Join-Path $build $name
    if (Test-Path -LiteralPath $file -PathType Leaf) { Copy-Item -LiteralPath $file -Destination $gameFiles -Force }
}
foreach ($name in @('config', 'wii_bootstrap')) {
    $directory = Join-Path $build $name
    if (Test-Path -LiteralPath $directory -PathType Container) { Copy-Item -LiteralPath $directory -Destination $gameFiles -Recurse -Force }
}
# The game without its debugging information, which the phone has no use for.
$library = Join-Path $stage 'libmain.so'
Invoke-Checked $strip @('--strip-unneeded', '-o', $library, (Join-Path $build 'libmain.so')) 'Stripping the game'
[IO.Directory]::CreateDirectory($userData) | Out-Null
Invoke-Checked $apkPack @('--shell', $shell, '--lib', "arm64-v8a=$library", '--assets', $gameFiles,
    '--key', (Join-Path $userData 'android-signing.pfx'), '--out', $apk) 'Making the app'
Write-Host "Done / Listo: $apk" -ForegroundColor Green

# ---------------------------------------------------------------- the device

if ($NoInstall) { return }
if (-not (Test-Path -LiteralPath $adb -PathType Leaf)) { return }
# adb leaves its server running in the background: start it here, so the commands below do not
# wait for it to end.
& $adb start-server 2>&1 | Out-Null
$devices = @(& $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match '\tdevice$' })
if ($devices.Count -eq 0) {
    Write-Host ''
    Write-Host 'No device connected with USB debugging: install AnimalParade.apk and copy the disc yourself (README-Android.txt).'
    Write-Host 'No hay un dispositivo conectado con la depuración USB: instala AnimalParade.apk y copia el disco tú (README-Android.txt).'
    return
}
if ($devices.Count -gt 1) {
    Write-Host 'More than one device is connected; leave only one. / Hay más de un dispositivo conectado; deja solo uno.'
    return
}
Write-Step 'Installing the app on the device' 'Instalando la app en el dispositivo'
Invoke-Checked $adb @('install', '-r', $apk) 'Installing the app' -WaitForProcessTree $false
# The app makes its folder the first time it opens; the disc goes in it.
& $adb shell am start -n "$packageName/.SetupActivity" | Out-Null
Start-Sleep -Seconds 3
$deviceFolder = "/sdcard/Android/data/$packageName/files"
$present = (& $adb shell "test -f $deviceFolder/Disc/DATA/sys/main.dol && echo yes") -join ''
if ($present.Trim() -ne 'yes') {
    Write-Step 'Copying your disc to the device (once; a few minutes)' 'Copiando tu disco al dispositivo (una sola vez; unos minutos)'
    & $adb shell "mkdir -p $deviceFolder/Disc" | Out-Null
    Invoke-Checked $adb @('push', $discRoot, "$deviceFolder/Disc/") 'Copying the disc' -TimeoutSeconds 7200
    if ((Split-Path -Leaf $discRoot) -ne 'DATA') {
        & $adb shell "mv '$deviceFolder/Disc/$(Split-Path -Leaf $discRoot)' $deviceFolder/Disc/DATA" | Out-Null
    }
}
& $adb shell am start -n "$packageName/.SetupActivity" | Out-Null
Write-Host ''
Write-Host 'The game is on the device. / El juego está en el dispositivo.' -ForegroundColor Green
