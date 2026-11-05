"""Paths and identifiers of this project, in one place.

Rutas e identificadores del proyecto, en un solo lugar.

Every default path is built from the repository root, so the tools work the
same whichever folder they are run from.

Todas las rutas por defecto parten de la raíz del repositorio, así que las
herramientas funcionan igual desde cualquier carpeta.
"""

from pathlib import Path

GAME_ID = "RBIEE9"  # Harvest Moon: Animal Parade (USA), revision 1

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISC_DIRECTORY = REPOSITORY_ROOT / "orig" / GAME_ID  # the user's extracted disc
MAIN_DOL_PATH = DISC_DIRECTORY / "sys" / "main.dol"
SCRIPT_DIRECTORY = DISC_DIRECTORY / "files" / "script"  # the compiled .opb event scripts
CONFIG_DIRECTORY = REPOSITORY_ROOT / "config" / GAME_ID
SYMBOLS_PATH = CONFIG_DIRECTORY / "symbols.txt"
BUILD_DIRECTORY = REPOSITORY_ROOT / "build"
