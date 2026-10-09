"""Build static/vendor/lucide/icons.svg from a lucide-static package.

Usage: python scripts/build_icon_sprite.py /path/to/lucide-static/package
The icon list is apps/ui/icons.py ICON_NAMES. The sprite holds only those
icons, as <symbol id="name"> elements, plus the Lucide ISC licence comment.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "static" / "vendor" / "lucide"


def icon_names() -> list[str]:
    tree = ast.parse((ROOT / "apps" / "ui" / "icons.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            return sorted(ast.literal_eval(node))
    raise SystemExit("ICON_NAMES not found")


def inner_svg(path: Path) -> str:
    text = path.read_text()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    match = re.search(r"<svg[^>]*>(.*)</svg>", text, flags=re.S)
    if match is None:
        raise SystemExit(f"Not an SVG: {path}")
    return " ".join(match.group(1).split())


def main() -> int:
    package = Path(sys.argv[1])
    version = json.loads((package / "package.json").read_text())["version"]
    symbols = []
    for name in icon_names():
        source = package / "icons" / f"{name}.svg"
        if not source.exists():
            raise SystemExit(f"Unknown Lucide icon: {name}")
        symbols.append(
            f'<symbol id="{name}" viewBox="0 0 24 24">{inner_svg(source)}</symbol>'
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sprite = (
        f"<!-- Lucide {version} (ISC licence, see LICENSE). Built by "
        "scripts/build_icon_sprite.py from apps/ui/icons.py. -->\n"
        '<svg xmlns="http://www.w3.org/2000/svg">\n' + "\n".join(symbols) + "\n</svg>\n"
    )
    (OUT_DIR / "icons.svg").write_text(sprite)
    shutil.copy(package / "LICENSE", OUT_DIR / "LICENSE")
    (OUT_DIR / "VERSION").write_text(version + "\n")
    print(f"{len(symbols)} icons, Lucide {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
