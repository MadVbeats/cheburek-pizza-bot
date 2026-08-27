import json
from pathlib import Path

_path = Path(__file__).parent / "menu.json"
MENU: dict = json.loads(_path.read_text(encoding="utf-8"))
CATEGORIES: list[str] = list(MENU)


def get_item(ci: int, ii: int) -> tuple[str, dict]:
    cat = CATEGORIES[ci]
    return cat, MENU[cat][ii]
