from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CONFTEXT = '"""\nAuto-injected by Test-Aware SWE-bench MVP (Option A).\n\nThis conftest enables **public/hidden** test selection at pytest collection time,\nwithout changing the upstream test command.\n\nUsage:\n  - Public run:  export TA_SPLIT=public\n  - Hidden run:  export TA_SPLIT=hidden\n  - Default:     TA_SPLIT=public\n\nSplit spec is stored in `.ta_split.json` at the repository root:\n  {\n    "public": ["tests/test_x.py::test_y", ...],\n    "hidden": ["tests/test_x.py::test_z", ...]\n  }\n\nIf `.ta_split.json` is missing or empty for the requested split, all tests are collected.\n"""\nfrom __future__ import annotations\n\nimport json\nimport os\nfrom pathlib import Path\nfrom typing import Set\n\nimport pytest\n\nSPLIT_ENV = "TA_SPLIT"\nSPLIT_FILE = ".ta_split.json"\n\ndef _load_split(root: Path) -> dict[str, Set[str]]:\n    fp = root / SPLIT_FILE\n    if not fp.exists():\n        return {"public": set(), "hidden": set()}\n    data = json.loads(fp.read_text(encoding="utf-8"))\n    return {\n        "public": set(data.get("public", [])),\n        "hidden": set(data.get("hidden", [])),\n    }\n\ndef pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:\n    split = os.environ.get(SPLIT_ENV, "public").strip().lower()\n    if split not in ("public", "hidden"):\n        return\n\n    root = Path(str(config.rootpath))\n    spec = _load_split(root)\n    target = spec.get(split, set())\n    if not target:\n        return\n\n    keep: list[pytest.Item] = []\n    deselected: list[pytest.Item] = []\n    for item in items:\n        key = item.nodeid\n        if key in target:\n            keep.append(item)\n        else:\n            deselected.append(item)\n\n    if deselected:\n        config.hook.pytest_deselected(items=deselected)\n        items[:] = keep\n'

@dataclass
class InjectResult:
    changed: bool
    path: Path

def inject_conftest(repo_root: Path, *, force: bool = False) -> InjectResult:
    """
    Inject (or update) a repository-level conftest.py that supports TA_SPLIT filtering.
    If conftest.py exists and already contains 'TA_SPLIT', leave it unless force=True.
    """
    dst = repo_root / "conftest.py"
    marker = "TA_SPLIT"
    payload = CONFTEXT.strip() + "\n"
    if not dst.exists():
        dst.write_text(payload, encoding="utf-8")
        return InjectResult(True, dst)

    existing = dst.read_text(encoding="utf-8", errors="ignore")
    if (marker in existing) and not force:
        return InjectResult(False, dst)

    appended = existing.rstrip() + "\n\n# === Test-Aware Split Support (auto-injected) ===\n" + payload
    dst.write_text(appended, encoding="utf-8")
    return InjectResult(True, dst)
