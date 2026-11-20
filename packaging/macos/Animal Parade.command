#!/bin/bash
# Double click to open the launcher (it opens in your browser). The first time macOS may ask:
# right click > Open.
# Doble clic para abrir el launcher (se abre en tu navegador). La primera vez macOS puede
# preguntar: clic derecho > Abrir.
cd "$(dirname "$0")"
# The package's own programs are not signed; the mark of the download comes off them.
xattr -dr com.apple.quarantine . 2>/dev/null
exec ./AnimalParadeLauncher
