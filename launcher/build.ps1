<#
.SYNOPSIS
Builds Launcher.exe and puts it, with its page, in a package folder.
Compila Launcher.exe y lo pone, con su página, en la carpeta de un paquete.

.DESCRIPTION
Uses the llvm-mingw compiler that the package already carries (Toolkit\llvm-mingw), for the
package's own processor (x86-64 or ARM64). The result:

  <Package>\Launcher.exe        the window (host\launcher.cpp)
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

$loader = Join-Path $here 'third_party\OpenWebView2Loader'
& $compiler -std=c++17 -O2 -municode -mwindows `
    "-I$loader\Include" "-I$loader\Source" `
    (Join-Path $here 'host\launcher.cpp') (Join-Path $loader 'Source\WebView2Loader.cpp') `
    -static -lole32 -lversion -lcomdlg32 -lshell32 -luuid `
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
