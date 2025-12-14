# Option A: Pytest Collection-Time Public/Hidden Split

This scaffold supports public/hidden selection at **pytest collection** time.

## Mechanism
- A `conftest.py` hook (provided in `conftest_injector.py`) filters collected tests based on:
  - `TA_SPLIT=public|hidden`
  - `.ta_split.json` at repo root, containing nodeids

## MVP integration
- The runner exports `TA_SPLIT=public` for SWE-bench harness runs.
- Your Test Author is instructed to **create/update `.ta_split.json`** as an intermediate artifact.

## Next step to complete D-benchmark
Add a second evaluation phase:
- run harness with `TA_SPLIT=hidden` and score hidden pass rate,
- compute Overfit Gap = public_pass - hidden_pass.
