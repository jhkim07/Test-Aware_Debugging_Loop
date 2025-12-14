# Test-Aware Debugging Loop (SWE-bench + pytest) — MVP Scaffold

This repository is a **minimal, runnable scaffold** for a "Test-Aware Debugging Loop Benchmark" on **SWE-bench** instances:
- Each iteration **must** produce a **test diff** (intermediate artifact) and a **code patch diff**.
- The runner evaluates:
  - whether the generated tests reproduce the bug (**BRS**)
  - whether the combined patch passes the repository tests (public)
  - optional hidden/holdout evaluation hooks (stubbed for MVP)

It is designed for **Ubuntu 22.04 + conda + Docker**.

## 0) Prerequisites
- Docker installed and usable by your user (Linux post-install steps).
- Conda environment with Python 3.11+ recommended.
- OpenAI API key exported as `OPENAI_API_KEY`.

## 1) Install
```bash
conda create -n ta-swebench python=3.11 -y
conda activate ta-swebench
pip install -U pip
pip install swebench pyyaml openai rich
```

SWE-bench harness uses Docker (required). See SWE-bench evaluation guide. citeturn0search5

## 2) Configure instances
Edit `configs/mvp.yaml` and add **10–50** SWE-bench instance IDs (Lite/Verified/etc).

Example instance IDs:
- `astropy__astropy-14539`
- `sympy__sympy-20590`

## 3) Run (single or batch)

### 일반 실행 (Cursor 창을 닫으면 종료될 수 있음)
```bash
python scripts/run_mvp.py --config configs/mvp.yaml --run-id mvp-001 --max-workers 2
```

### 장시간 실행 (Cursor 창을 닫아도 계속 실행됨) ⭐ 권장
```bash
./scripts/run_mvp_nohup.sh configs/mvp.yaml mvp-001 1
```

### 실행 중인 실험 확인
```bash
# 실험 상태 확인 (다음 Cursor 세션에서 실행)
./scripts/check_experiment.sh

# 또는 로그 확인
tail -f logs/<run-id>.log
```

**💡 팁**: 다음 Cursor 세션에서 실행 중인 실험을 확인하려면 프로젝트를 열고 `./scripts/check_experiment.sh`를 실행하세요.

The runner will create:
- `outputs/<run-id>/<instance-id>/` with:
  - `run.jsonl` (iteration logs)
  - `predictions.jsonl` (latest patch for swebench harness)
  - `final_patch.diff`, `final_tests.diff`
  - `metrics.json`

## Notes on "public/hidden" split (MVP)
This scaffold implements the **protocol** and produces the required artifacts, and includes a **hook** for hidden evaluation.

To fully implement a public/hidden split for pytest you typically need either:
1) a controlled split of test files and a way to run hidden tests separately, or
2) a separate harness run using a custom test command.

The `bench_agent/runner/hidden_eval.py` file is a **stub** where you can integrate your preferred approach.

## Policy guards (enforced heuristically)
- no `pytest.skip` / `xfail` additions
- no obvious network calls in tests (`requests`, `urllib`, `socket`)
- file I/O is restricted (heuristics; adjust for your repo needs)

## References
- `python -m swebench.harness.run_evaluation ...` CLI usage. citeturn0search1turn0search5
