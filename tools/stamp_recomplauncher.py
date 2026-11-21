"""Puts recomplauncher.json in a package folder, with the release's version in its setup step.

RecompLauncher (https://recomplauncher.com) builds the game on the player's PC with the setup step
in packaging/recomplauncher.json ("prepare"). It runs that step again only when "prepare.version"
changes, and every release changes the game's code, so each package carries the version in VERSION
there. Usage, from the repository's top folder:

    python tools/stamp_recomplauncher.py PACKAGE_FOLDER

Pone recomplauncher.json en la carpeta de un paquete, con la versión del release en su paso de
preparación: RecompLauncher solo vuelve a compilar el juego cuando "prepare.version" cambia.
"""

import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    package = Path(sys.argv[1])
    version = (REPOSITORY / "VERSION").read_text(encoding="utf-8").strip()
    profile = json.loads((REPOSITORY / "packaging" / "recomplauncher.json").read_text(encoding="utf-8"))
    profile["prepare"]["version"] = version
    text = json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    (package / "recomplauncher.json").write_text(text, encoding="utf-8", newline="\n")
    print(f"recomplauncher.json: setup step version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
