<#
.SYNOPSIS
Builds Harvest Moon: Animal Parade from your own disc and starts it.
Compila Harvest Moon: Animal Parade desde tu propio disco y lo inicia.

.DESCRIPTION
The package has no game code in it. This script makes the game on your computer, the way
WiiCompiled does for Mario Kart Wii:

  1. The translator turns your main.dol into C++ (BuildWorkspace\generated, under a minute).
  2. The compiler that comes with the package (llvm-mingw) compiles that C++ together with
     WiiCompiled's runtime (BuildWorkspace\native-build; the first time takes a while).
  3. The game goes to Game\, its settings to UserData\Config.toml, and it starts.

The next time only what changed is compiled again, so it starts much sooner.

El paquete no trae código del juego. Este script hace el juego en tu computadora, como hace
WiiCompiled con Mario Kart Wii: el traductor convierte tu main.dol en C++, el compilador que viene en
el paquete lo compila junto con el runtime de WiiCompiled, y el juego queda en Game\, con su
configuración en UserData\Config.toml. La siguiente vez solo se compila lo que cambió.

.PARAMETER Disc
Your disc image (.rvz, .iso, .wbfs, .wia or .ciso), as Dolphin plays it. The script extracts it
once to Disc\ with nodtool, the same tool WiiCompiled uses. A folder already extracted by Dolphin
(the one with sys\main.dol, sys\fst.bin and files\) works too. Asked for if left out, and
remembered after that.
Tu imagen del disco (.rvz, .iso, .wbfs, .wia o .ciso), la misma con la que juegas en Dolphin. El
script la extrae una vez a Disc\ con nodtool, la herramienta que usa WiiCompiled. También sirve una
carpeta ya extraída con Dolphin (la que tiene sys\main.dol, sys\fst.bin y files\).

.PARAMETER Rebuild
Translate and compile again even if nothing changed.
Traducir y compilar otra vez aunque nada haya cambiado.

.PARAMETER NoStart
Build the game but do not start it.
Compilar el juego pero no iniciarlo.
#>
[CmdletBinding()]
param(
    [string]$Disc,
    [switch]$Rebuild,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

$root = $PSScriptRoot
$toolkit = Join-Path $root 'Toolkit'
$workspace = Join-Path $root 'BuildWorkspace'
$game = Join-Path $root 'Game'
$userData = Join-Path $root 'UserData'
$rememberedDisc = Join-Path $userData 'disc.txt'
$extracted = Join-Path $root 'Disc'
$project = 'projects\animal-parade\recomp.yml'
$gameId = 'RBIEE9'

# WiiCompiled's own helpers: Invoke-Checked, the configure flags, the precompiled package check.
. (Join-Path $workspace 'NativeBuildFlags.ps1')

function Write-Step([string]$English, [string]$Spanish) {
    Write-Host ''
    Write-Host "== $English" -ForegroundColor Cyan
    Write-Host "   $Spanish" -ForegroundColor DarkCyan
}

function Find-DiscRoot([string]$Folder) {
    <# The folder itself, or the DATA folder inside it: Dolphin writes a Wii disc both ways. #>
    foreach ($candidate in @($Folder, (Join-Path $Folder 'DATA'))) {
        if ((Test-Path -LiteralPath (Join-Path $candidate 'sys\main.dol') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $candidate 'sys\fst.bin') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $candidate 'files') -PathType Container)) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

function Read-DiscId([string]$DiscRoot) {
    $bootBin = Join-Path $DiscRoot 'sys\boot.bin'
    if (-not (Test-Path -LiteralPath $bootBin -PathType Leaf)) { return '' }
    $bytes = [IO.File]::ReadAllBytes($bootBin)
    return [Text.Encoding]::ASCII.GetString($bytes, 0, 6)
}

function Select-DiscImage {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = 'Harvest Moon: Animal Parade (RBIEE9) - disc image / imagen del disco'
    $dialog.Filter = 'Wii disc images (*.rvz;*.iso;*.wbfs;*.wia;*.ciso)|*.rvz;*.iso;*.wbfs;*.wia;*.ciso|All files (*.*)|*.*'
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        throw 'No disc image was chosen. / No se eligió la imagen del disco.'
    }
    return $dialog.FileName
}

function Expand-DiscImage([string]$Image) {
    <#
    Extracts the image's data partition to Disc\DATA once. Disc\extracted-from.txt records which
    image (path, size, date) it came from, so the same image is not extracted again; a half-finished
    extraction has no record and is redone.
    #>
    # Not $image: PowerShell names are not case sensitive, so that would be the [string] parameter
    # $Image, and the file would turn back into a string.
    $imageFile = Get-Item -LiteralPath $Image
    $source = "$($imageFile.FullName)|$($imageFile.Length)|$($imageFile.LastWriteTimeUtc.ToString('o'))"
    $record = Join-Path $extracted 'extracted-from.txt'
    $dataRoot = Join-Path $extracted 'DATA'
    if ((Test-Path -LiteralPath $record -PathType Leaf) -and ((Get-Content -LiteralPath $record -Raw).Trim() -eq $source) -and
        (Find-DiscRoot $dataRoot)) {
        return $dataRoot
    }
    Write-Step 'Extracting the disc image (once; a few minutes)' 'Extrayendo la imagen del disco (una sola vez; unos minutos)'
    if (Test-Path -LiteralPath $extracted) { Remove-Item -LiteralPath $extracted -Recurse -Force }
    [IO.Directory]::CreateDirectory($extracted) | Out-Null
    $nodTool = Join-Path $toolkit 'nodtool.exe'
    Assert-File $nodTool 'Disc tool'
    Invoke-Checked $nodTool @('extract', $imageFile.FullName, $dataRoot, '-q') 'Extracting the disc image'
    Set-Content -LiteralPath $record -Value $source -Encoding UTF8
    return $dataRoot
}

# ---------------------------------------------------------------- the package's programs

# Windows marks every file unzipped from a download as coming from the internet, and App Control
# (Smart App Control) then may refuse to start a program that is not signed, like this package's
# translator. They are the package's own programs, so the mark comes off them and their libraries.
# Windows marca cada archivo descomprimido de una descarga como venido de internet, y el Control de
# aplicaciones puede negarse a abrir un programa sin firma, como el traductor del paquete.
Get-ChildItem -LiteralPath $toolkit, (Join-Path $workspace 'Dependencies') -Recurse -File |
    Where-Object { $_.Extension -in '.exe', '.dll' } | Unblock-File

# ---------------------------------------------------------------- the disc

[IO.Directory]::CreateDirectory($userData) | Out-Null
if (-not $Disc -and (Test-Path -LiteralPath $rememberedDisc -PathType Leaf)) {
    $Disc = (Get-Content -LiteralPath $rememberedDisc -Raw).Trim()
}
if (-not $Disc) { $Disc = Select-DiscImage }
if (-not (Test-Path -LiteralPath $Disc)) {
    throw "$Disc does not exist. / $Disc no existe."
}
$Disc = [IO.Path]::GetFullPath($Disc)
if (Test-Path -LiteralPath $Disc -PathType Leaf) {
    $discRoot = Find-DiscRoot (Expand-DiscImage $Disc)
} else {
    $discRoot = Find-DiscRoot $Disc
}
if (-not $discRoot) {
    throw "$Disc is not a disc image nor a folder with sys\main.dol, sys\fst.bin and files\. " +
        "/ $Disc no es una imagen de disco ni una carpeta con sys\main.dol, sys\fst.bin y files\."
}
$discId = Read-DiscId $discRoot
if ($discId -and $discId -ne $gameId) {
    throw "This disc is $discId; the package is for $gameId (Harvest Moon: Animal Parade, USA). " +
        "/ Este disco es $discId; el paquete es para $gameId."
}
Set-Content -LiteralPath $rememberedDisc -Value $Disc -Encoding UTF8
$mainDol = Join-Path $discRoot 'sys\main.dol'
Write-Host "Disc / Disco: $discRoot"

# ---------------------------------------------------------------- the build

# CMake, Ninja and clang do not all quote paths the same way; WiiCompiled gives an unusual folder
# name a plain alias. Long paths are the other risk, so the package is best unzipped near the drive.
$workspace = Get-MkwBuildSafePath $workspace 'workspace' 'runtime\CMakeLists.txt'
$toolkit = Get-MkwBuildSafePath $toolkit 'toolchain' 'CMake\bin\cmake.exe'
if ($workspace.Length -gt 60) {
    Write-Warning ("The package is in a long path ($($workspace.Length) characters). If the build stops on a " +
        'missing file, move the folder to something short like C:\HMAP. / La ruta es larga; si la ' +
        'compilación se detiene por un archivo que no encuentra, mueve la carpeta a algo corto como C:\HMAP.')
}

$translator = Join-Path $toolkit 'Translator\Translator.Cli.exe'
$cmake = Join-Path $toolkit 'CMake\bin\cmake.exe'
$ninja = Join-Path $toolkit 'Ninja\ninja.exe'
$toolchainBin = Join-Path $toolkit 'llvm-mingw\bin'
$cc = Join-Path $toolchainBin 'x86_64-w64-mingw32-clang.exe'
$cxx = Join-Path $toolchainBin 'x86_64-w64-mingw32-clang++.exe'
$windres = Join-Path $toolchainBin 'x86_64-w64-mingw32-windres.exe'
foreach ($required in @($translator, $cmake, $ninja, $cc, $cxx, $windres)) { Assert-File $required 'Package file' }

$generated = Join-Path $workspace 'generated'
$functions = Join-Path $generated 'functions'
$metadata = Join-Path $generated 'base_translation_metadata.json'
$sources = Join-Path $generated 'base_translation_sources.bin'
$shards = Join-Path $generated 'build_shards'
$build = Join-Path $workspace 'native-build'
$stamp = Join-Path $generated 'translated-from.txt'
$dolSha = Get-MkwFileSha256 $mainDol

# The same three knobs as WiiCompiled's LocalBuild.ps1: a translated file takes about half a GB in
# clang, so the compile jobs are capped by memory as well as by processors.
$memoryGiB = [math]::Max(1, [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB))
$translatorThreads = [math]::Max(1, [math]::Min([Environment]::ProcessorCount, 16))
$translatedJobs = [math]::Max(1, [math]::Min([Environment]::ProcessorCount, [math]::Floor(($memoryGiB - 2) / 0.5)))
$globalJobs = [math]::Max($translatedJobs, [Environment]::ProcessorCount)
# Windows on ARM runs this x86-64 build through its emulator, which is safest without AVX2.
$cpuProfile = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { 'v2' } else { 'v3' }

$oldPath = $env:PATH
$env:PATH = Get-MkwToolchainPath $toolkit
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
    if (-not (Select-String -LiteralPath (Join-Path $shards 'shards.cmake') -Pattern 'MKW_TRANSLATED_GUEST_REGION 3' -Quiet)) {
        throw 'The translation was not made for a foreign game (region 3); the translator patch is missing.'
    }

    if ($Rebuild -and (Test-Path -LiteralPath $build)) { Remove-Item -LiteralPath $build -Recurse -Force }
    # The precompiled runtime is only used while the runtime's sources are the ones it was built from,
    # and CMake decides that when it configures. A runtime file newer than the last configuration (a
    # fix copied into BuildWorkspace\runtime) therefore configures again; what was compiled is kept.
    $cache = Join-Path $build 'CMakeCache.txt'
    if (Test-Path -LiteralPath $cache -PathType Leaf) {
        $configured = (Get-Item -LiteralPath $cache).LastWriteTimeUtc
        $changed = Get-ChildItem -LiteralPath (Join-Path $workspace 'runtime') -Recurse -File |
            Where-Object { $_.LastWriteTimeUtc -gt $configured } | Select-Object -First 1
        if ($changed) {
            Write-Host "Runtime changed ($($changed.Name)); configuring again / El runtime cambió; se configura otra vez"
            Remove-Item -LiteralPath $cache -Force
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $build 'CMakeCache.txt') -PathType Leaf)) {
        Write-Step 'Configuring the build' 'Configurando la compilación'
        $dependencies = Join-Path $workspace 'Dependencies'
        $prebuilt = Resolve-MkwNativePrebuiltDirectory $dependencies $toolchainBin `
            (Join-Path $workspace 'aurora-main') (Join-Path $workspace 'runtime\third_party')
        $configure = Get-MkwNativeConfigureArguments `
            -SourceDirectory (Join-Path $workspace 'runtime') -BuildDirectory $build `
            -Ninja $ninja -CCompiler $cc -CxxCompiler $cxx -ResourceCompiler $windres `
            -DependenciesDirectory $dependencies -NativePrebuiltDirectory $prebuilt `
            -AdditionalArguments @("-DMKW_TRANSLATED_COMPILE_JOBS=$translatedJobs", "-DMKW_X86_CPU_PROFILE=$cpuProfile")
        Invoke-Checked $cmake $configure 'Configuring'
    }

    Write-Step 'Compiling (the first time takes a while)' 'Compilando (la primera vez tarda un rato)'
    Invoke-Checked $cmake @('--build', $build, '--target', 'WiiCompiled', '--parallel', $globalJobs) 'Compiling'
} finally {
    Pop-Location
    $env:PATH = $oldPath
}

# ---------------------------------------------------------------- the game folder

Write-Step 'Copying the game to Game\' 'Copiando el juego a Game\'
[IO.Directory]::CreateDirectory($game) | Out-Null
Copy-Item -LiteralPath (Join-Path $build 'WiiCompiled.exe') -Destination (Join-Path $game 'AnimalParade.exe') -Force
# The same files WiiCompiled's LocalBuild.ps1 puts next to the game.
foreach ($name in @('dxcompiler.dll','dxil.dll','libc++.dll','libpng16.dll','libunwind.dll','libz.dll','libzlib1.dll',
                    'SDL3.dll','sqlite3.dll','webgpu_dawn.dll','z.dll','noshaders.zip','dsp_coef.bin','initial_pipeline_cache.db')) {
    $file = Join-Path $build $name
    if (Test-Path -LiteralPath $file -PathType Leaf) { Copy-Item -LiteralPath $file -Destination $game -Force }
}
$redist = Join-Path $toolkit 'Redist'
if (Test-Path -LiteralPath $redist -PathType Container) {
    Get-ChildItem -LiteralPath $redist -Filter '*.dll' -File | Copy-Item -Destination $game -Force
}
foreach ($name in @('config', 'wii_bootstrap')) {
    $directory = Join-Path $build $name
    if (Test-Path -LiteralPath $directory -PathType Container) {
        Copy-Item -LiteralPath $directory -Destination $game -Recurse -Force
    }
}

# portable.txt next to this script makes the runtime keep its settings, saves and logs in UserData\
# instead of %LOCALAPPDATA%\WiiCompiled, which Mario Kart Wii would share.
$config = Join-Path $userData 'Config.toml'
$tomlPath = $discRoot.Replace('\', '\\')
if (Test-Path -LiteralPath $config -PathType Leaf) {
    $text = Get-Content -LiteralPath $config -Raw
    if ($text -match '(?m)^\s*dvd_root\s*=') {
        $text = [regex]::Replace($text, '(?m)^\s*dvd_root\s*=.*$', "dvd_root = `"$tomlPath`"")
    } elseif ($text -match '(?m)^\[paths\]\s*$') {
        $text = [regex]::Replace($text, '(?m)^\[paths\]\s*$', "[paths]`r`ndvd_root = `"$tomlPath`"")
    } else {
        $text = $text.TrimEnd() + "`r`n`r`n[paths]`r`ndvd_root = `"$tomlPath`"`r`n"
    }
} else {
    $text = "[paths]`r`ndvd_root = `"$tomlPath`"`r`n"
}
# UTF-8 without the byte order mark that Windows PowerShell's Set-Content would put first.
[IO.File]::WriteAllText($config, $text, (New-Object Text.UTF8Encoding $false))

Write-Host ''
Write-Host "Done / Listo: $(Join-Path $game 'AnimalParade.exe')" -ForegroundColor Green
if (-not $NoStart) {
    Start-Process -FilePath (Join-Path $game 'AnimalParade.exe') -WorkingDirectory $game
}
