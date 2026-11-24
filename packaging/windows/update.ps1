<#
.SYNOPSIS
Updates this folder to a newer version of Harvest Moon: Animal Parade from its GitHub release.
Actualiza esta carpeta a una versión más nueva de Harvest Moon: Animal Parade desde GitHub.

.DESCRIPTION
The launcher runs this when its Game tab's "Update to vX" is chosen (launcher\README.md). It does
not need to be run by hand.

  1. Downloads this computer's package of that version (x64 or arm64, as Launcher.exe is) to
     .update\, printing "progress <0..1>" lines that the launcher shows.
  2. Unzips it there and checks that it is that version (its version.txt).
  3. Prints "apply": the launcher closes. From here on nothing more is printed; what happens goes
     to UserData\Logs\update.log.
  4. When the launcher is closed, copies the new package over this folder. UserData (the saves, the
     settings and the controls) is not in the package, so it stays as it is.
  5. Opens the launcher again. Its Play prepares the game again, since the package changed.

When something fails before step 3 it prints "error <message>" and nothing here changed.

El launcher lo ejecuta cuando eliges "Actualizar a la vX" en la pestaña Juego; no hace falta
ejecutarlo a mano. Baja el paquete de esa versión para esta computadora a .update\, mostrando cuánto
lleva, lo descomprime, comprueba que sea esa versión y dice "apply": el launcher se cierra, el paquete
nuevo se copia encima de esta carpeta (UserData, con tus partidas y ajustes, no viene en el paquete y
se queda) y el launcher se abre otra vez. Si algo falla antes de "apply", dice "error <mensaje>" y
aquí no cambió nada.

.PARAMETER Version
The version to update to, as its release is tagged without the "v": 0.2.4.
La versión a la que actualizar, como se llama su release sin la "v": 0.2.4.

.PARAMETER LauncherPid
The launcher's process: the files are replaced only once it has closed.
El proceso del launcher: los archivos se reemplazan solo cuando se cerró.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Version,
    [int]$LauncherPid = 0
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

$root = $PSScriptRoot
$staging = Join-Path $root '.update'
$logs = Join-Path $root 'UserData\Logs'
$log = Join-Path $logs 'update.log'
$repository = 'RodoLy/HarvestMoonAnimalParadeRecomp'

# The launcher reads the lines as UTF-8 (the messages have accents).
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function Say([string]$Line) {
    # Straight to the output, so that each one is a line of its own. When the launcher is gone (it
    # was closed during the download) there is nobody to update for: stop.
    try {
        [Console]::Out.WriteLine($Line)
        [Console]::Out.Flush()
    } catch {
        exit 1
    }
}

function Write-Log([string]$Line) {
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    Add-Content -LiteralPath $log -Value ('{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $Line) -Encoding UTF8
}

function Get-Processor {
    <# x64 or arm64: what Launcher.exe (or the game) was built for, so the update is the same package. #>
    foreach ($file in @((Join-Path $root 'Launcher.exe'), (Join-Path $root 'Game\AnimalParade.exe'))) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        $stream = [IO.File]::OpenRead($file)
        try {
            $reader = New-Object IO.BinaryReader($stream)
            $stream.Position = 0x3C
            $stream.Position = $reader.ReadInt32() + 4
            switch ($reader.ReadUInt16()) {
                0x8664 { return 'x64' }
                0xAA64 { return 'arm64' }
            }
        } finally {
            $stream.Dispose()
        }
    }
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { return 'arm64' }
    return 'x64'
}

function Save-Package([string]$Url, [string]$Target) {
    <# Downloads with HttpClient, which tells the size as it goes; the system's proxy is used. #>
    Add-Type -AssemblyName System.Net.Http
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $client = New-Object Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromMinutes(30)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd('HarvestMoonAnimalParade-launcher')
    try {
        $answer = $client.GetAsync($Url, [Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        if ($answer.StatusCode -eq [Net.HttpStatusCode]::NotFound) {
            throw "v$Version has no package for this computer yet. / La v$Version todavía no tiene paquete para esta computadora."
        }
        [void]$answer.EnsureSuccessStatusCode()
        $total = $answer.Content.Headers.ContentLength
        $from = $answer.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $to = [IO.File]::Create($Target)
        try {
            $buffer = New-Object byte[] (1MB)
            $done = 0L
            $shown = -1
            while (($read = $from.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $to.Write($buffer, 0, $read)
                $done += $read
                if ($total) {
                    # The download is most of the time; unzipping is the last 5%.
                    $percent = [int][Math]::Floor(95 * $done / $total)
                    if ($percent -ne $shown) {
                        $shown = $percent
                        Say ('progress ' + ($percent / 100).ToString([Globalization.CultureInfo]::InvariantCulture))
                    }
                }
            }
        } finally {
            $to.Dispose()
            $from.Dispose()
        }
    } finally {
        $client.Dispose()
    }
}

function Find-Package([string]$Folder) {
    <# The unzipped package: the folder with version.txt (the zip has one folder inside). #>
    $file = Get-ChildItem -LiteralPath $Folder -Recurse -Depth 2 -Filter 'version.txt' -File | Select-Object -First 1
    if (-not $file) { return $null }
    return $file.DirectoryName
}

# ---------------------------------------------------------------------------------------------
# 1-3: download, unzip, check. Nothing in this folder changes yet.

try {
    if ($Version -notmatch '^\d+(\.\d+)+$') { throw "Not a version: $Version" }
    $processor = Get-Processor
    $asset = "HarvestMoonAnimalParade-windows-$processor.zip"
    $url = "https://github.com/$repository/releases/download/v$Version/$asset"

    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    $zip = Join-Path $staging $asset
    Write-Log "Downloading $url"
    Say 'progress 0'
    Save-Package $url $zip

    Write-Log 'Unzipping'
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $unzipped = Join-Path $staging 'package'
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $unzipped)
    Remove-Item -LiteralPath $zip -Force
    $package = Find-Package $unzipped
    if (-not $package) { throw 'The download is not a package of the game. / Lo que se bajó no es un paquete del juego.' }
    $got = (Get-Content -LiteralPath (Join-Path $package 'version.txt') -Raw).Trim()
    if ($got -ne "v$Version") { throw "The download is $got, not v$Version. / Lo que se bajó es la $got, no la v$Version." }
    if (-not (Test-Path -LiteralPath (Join-Path $package 'Launcher.exe') -PathType Leaf)) {
        throw 'The download has no Launcher.exe. / Lo que se bajó no trae Launcher.exe.'
    }
    Say 'progress 1'
} catch {
    $message = ($_.Exception.Message -replace '\s+', ' ').Trim()
    Write-Log "Failed: $message"
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue }
    Say "error $message"
    exit 1
}

# ---------------------------------------------------------------------------------------------
# 4-5: the launcher closes, the package goes over this folder, the launcher opens again. Whatever
# happens, it opens again at the end: with the new version, or with the old one if the copy failed.

Say 'apply'
Write-Log "Putting v$Version in place"
try {
    if ($LauncherPid) {
        $launcher = Get-Process -Id $LauncherPid -ErrorAction SilentlyContinue
        if ($launcher -and -not $launcher.WaitForExit(60000)) { throw 'The launcher did not close. / El launcher no se cerró.' }
    }
    # robocopy retries a file that is still in use for a moment, and keeps long paths working.
    & robocopy.exe $package $root /E /R:5 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy could not copy every file (exit code $LASTEXITCODE)." }
    Write-Log "Now at v$Version"
} catch {
    Write-Log "Failed: $($_.Exception.Message)"
} finally {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath (Join-Path $root 'Launcher.exe') -WorkingDirectory $root
}
