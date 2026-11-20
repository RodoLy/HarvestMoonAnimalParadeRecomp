<#
.SYNOPSIS
Builds Launcher.exe and puts it, with its page, in a package folder.
Compila Launcher.exe y lo pone, con su página, en la carpeta de un paquete.

.DESCRIPTION
Uses the llvm-mingw compiler that the package already carries (Toolkit\llvm-mingw), for the
package's own processor (x86-64 or ARM64). The result:

  <Package>\Launcher.exe        the window (host\launcher.cpp, with host\launcher_core.cpp)
  <Package>\Launcher\           its page (web\: index.html, launcher.js, the animals, the fonts)

Usa el compilador llvm-mingw que ya trae el paquete, para su procesador (x86-64 o ARM64).

.PARAMETER Package
The package folder (the one with play.ps1 and Toolkit\).

.PARAMETER Processor
x86_64 or aarch64. By default, the processor the package's compiler is for.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Package,
    [ValidateSet('x86_64', 'aarch64')] [string]$Processor
)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$bin = Join-Path $Package 'Toolkit\llvm-mingw\bin'

if (-not $Processor) {
    # The compiler's own folder has one target prefix per processor; the package carries the one
    # for its processor first. Without a hint, take the computer's.
    $Processor = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64' } else { 'x86_64' }
}
$compiler = Join-Path $bin "$Processor-w64-mingw32-clang++.exe"
if (-not (Test-Path -LiteralPath $compiler)) { throw "No compiler at $compiler." }

# The version: the package's version.txt (v1.2.3), or the repository's VERSION when building from it.
$version = '0.0.0'
foreach ($candidate in @((Join-Path $Package 'version.txt'), (Join-Path $here '..\VERSION'))) {
    if (Test-Path -LiteralPath $candidate) {
        $version = (Get-Content -LiteralPath $candidate -Raw).Trim().TrimStart('v')
        break
    }
}
$numbers = (@($version.Split('.') | ForEach-Object { [int]($_ -replace '\D', '') }) + @(0, 0, 0, 0))[0..3] -join ','

# The icon and the version resource (host\launcher.rc), as an object file the compiler links in.
$resources = Join-Path ([IO.Path]::GetTempPath()) "launcher-resources-$Processor"
New-Item -ItemType Directory -Force $resources | Out-Null
@"
1 VERSIONINFO
FILEVERSION $numbers
PRODUCTVERSION $numbers
FILEFLAGSMASK 0x3fL
FILEFLAGS 0x0L
FILEOS 0x40004L
FILETYPE 0x1L
FILESUBTYPE 0x0L
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0"
        BEGIN
            VALUE "CompanyName", "HarvestMoonAnimalParadeRecomp (https://github.com/RodoLy/HarvestMoonAnimalParadeRecomp)"
            VALUE "FileDescription", "Harvest Moon: Animal Parade native PC port - launcher"
            VALUE "FileVersion", "$version"
            VALUE "InternalName", "Launcher"
            VALUE "LegalCopyright", "See LICENSE. Not affiliated with the game's publishers."
            VALUE "OriginalFilename", "Launcher.exe"
            VALUE "ProductName", "Harvest Moon: Animal Parade native port"
            VALUE "ProductVersion", "$version"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1200
    END
END
"@ | Set-Content -LiteralPath (Join-Path $resources 'launcher_version.rc') -Encoding ASCII
$windres = Join-Path $bin "$Processor-w64-mingw32-windres.exe"
$icon = Join-Path $resources 'launcher-resources.o'
& $windres (Join-Path $here 'host\launcher.rc') "--include-dir=$resources" -O coff -o $icon
if ($LASTEXITCODE -ne 0) { throw "The launcher's icon did not compile (exit code $LASTEXITCODE)." }

# -s leaves out the debugging information the linked libraries bring along: the player has no use
# for it, and with it several antivirus engines took Magical Melody's launcher, built the same
# way, for a trojan (BitDefender's Gen:Variant.Lazy and the engines that use it); without it they
# did not.
$loader = Join-Path $here 'third_party\OpenWebView2Loader'
& $compiler -std=c++17 -O2 -municode -mwindows `
    "-I$loader\Include" "-I$loader\Source" `
    (Join-Path $here 'host\launcher.cpp') (Join-Path $here 'host\launcher_core.cpp') `
    (Join-Path $loader 'Source\WebView2Loader.cpp') $icon `
    -static -s -lole32 -lversion -lcomdlg32 -lshell32 -luuid `
    -o (Join-Path $Package 'Launcher.exe')
if ($LASTEXITCODE -ne 0) { throw "Launcher.exe did not compile (exit code $LASTEXITCODE)." }

$page = Join-Path $Package 'Launcher'
if (Test-Path -LiteralPath $page) { Remove-Item -LiteralPath $page -Recurse -Force }
Copy-Item (Join-Path $here 'web') $page -Recurse

$licenses = Join-Path $Package 'licenses'
New-Item -ItemType Directory -Force $licenses | Out-Null
Copy-Item (Join-Path $loader 'LICENSE.md') (Join-Path $licenses 'openwebview2loader.txt')
Copy-Item (Join-Path $loader 'Include\LICENSE.txt') (Join-Path $licenses 'webview2-headers.txt')
Write-Host "Launcher.exe ($Processor) and its page are in $Package"
