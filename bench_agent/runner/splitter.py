from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

SPLIT_FILE = ".ta_split.json"

@dataclass
class SplitSpec:
    public: list[str]
    hidden: list[str]

    def to_json(self) -> str:
        return json.dumps({"public": self.public, "hidden": self.hidden}, indent=2)

def make_split(nodeids: list[str], failing_nodeids: list[str], public_ratio: float, seed: int = 0) -> SplitSpec:
    rng = random.Random(seed)
    all_set = list(dict.fromkeys(nodeids))
    failing = [n for n in failing_nodeids if n in all_set]
    remaining = [n for n in all_set if n not in set(failing)]
    rng.shuffle(remaining)

    target_public = int(round(public_ratio * len(all_set)))
    pub = list(failing)
    needed = max(0, target_public - len(pub))
    pub += remaining[:needed]
    hid = [n for n in all_set if n not in set(pub)]
    return SplitSpec(public=pub, hidden=hid)

def write_split(repo_root: Path, spec: SplitSpec) -> Path:
    fp = repo_root / SPLIT_FILE
    fp.write_text(spec.to_json() + "\n", encoding="utf-8")
    return fp
