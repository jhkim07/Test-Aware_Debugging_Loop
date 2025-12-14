# 프로젝트 개요: Test-Aware Debugging Loop

## 📋 목적 (Purpose)

이 프로젝트는 **Test-Aware Debugging Loop** 방식으로 SWE-bench 벤치마크의 버그 수정 과제를 해결하는 AI 에이전트를 구현합니다.

### 핵심 개념

**Test-Aware Debugging**은 다음과 같은 순환 과정을 통해 버그를 수정합니다:

1. **테스트 생성/강화**: 버그를 재현하는 테스트를 생성하거나 기존 테스트를 강화
2. **코드 패치 생성**: 생성된 테스트를 통과하도록 코드를 수정
3. **평가 및 피드백**: 테스트 통과 여부를 확인하고 실패 시 다시 반복

이 방식의 장점:
- ✅ **Overfitting 방지**: Public 테스트만 맞추는 편법 방지 (Hidden 테스트로 검증)
- ✅ **버그 재현 검증**: BRS (Bug Reproduction Strength)를 통해 버그 있는 코드에서 테스트가 실패하는지 확인
- ✅ **점진적 개선**: 반복적인 테스트-패치 사이클로 점진적으로 해결책 개선

---

## 🎯 목표 (Goals)

### 1. 버그 수정 성공률 향상
- Public 테스트와 Hidden 테스트 모두 통과하는 패치 생성
- SWE-bench 평가 기준에 부합하는 품질의 패치 생성

### 2. Overfitting 방지
- Public 테스트만 맞추는 편법 패치 방지
- Hidden 테스트 통과율과 Public 테스트 통과율의 차이 (Overfit Gap) 최소화

### 3. 버그 재현 검증 (BRS)
- 생성된 테스트가 버그 있는 코드에서 실패하는지 확인
- 올바른 테스트가 생성되었는지 검증

### 4. 반복적 개선
- 최대 8회까지 반복하며 테스트와 패치를 점진적으로 개선
- 각 반복마다 Controller가 "tests", "patch", "both" 중 집중 영역 결정

---

## 🏗️ 아키텍처 (Architecture)

### 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    run_mvp.py (Main Loop)                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │   SWE-bench Harness (평가 환경)        │
        │   - Docker 컨테이너 내에서 실행        │
        │   - Public/Hidden 테스트 분리         │
        └───────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │         Test-Aware Debugging Loop      │
        │                                         │
        │  ┌─────────────────────────────────┐   │
        │  │  1. Controller (의사결정)       │   │
        │  │     - focus: tests/patch/both   │   │
        │  │     - hypotheses 생성           │   │
        │  └─────────────────────────────────┘   │
        │              │                          │
        │      ┌───────┴───────┐                │
        │      ▼               ▼                │
        │  ┌─────────┐    ┌──────────┐         │
        │  │  Test   │    │  Patch   │         │
        │  │ Author  │    │  Author  │         │
        │  │  (LLM)  │    │  (LLM)   │         │
        │  └─────────┘    └──────────┘         │
        │      │               │                │
        │      └───────┬───────┘                │
        │              ▼                        │
        │  ┌──────────────────────────┐         │
        │  │  Protocol Layer          │         │
        │  │  - diff_validator        │         │
        │  │  - diff_cleaner          │         │
        │  │  - patch_builder         │         │
        │  │  - policy (정책 검증)    │         │
        │  └──────────────────────────┘         │
        │              │                        │
        │              ▼                        │
        │  ┌──────────────────────────┐         │
        │  │  Runner Layer            │         │
        │  │  - swebench_runner       │         │
        │  │  - splitter (test split) │         │
        │  │  - report_parser         │         │
        │  │  - error_analyzer        │         │
        │  └──────────────────────────┘         │
        └───────────────────────────────────────┘
```

### 주요 컴포넌트

#### 1. **Agent Layer** (`bench_agent/agent/`)

**Controller** (`controller.py`):
- 각 반복마다 전략 결정
- `focus`: "tests" (테스트 강화), "patch" (코드 수정), "both" (균형)
- Problem Statement와 실패 로그를 분석하여 hypotheses 생성

**Test Author** (`test_author.py`):
- LLM을 사용하여 버그를 재현하는 테스트 생성
- Reference test patch 분석 및 학습
- BRS (버그 있는 코드에서 실패) 확보

**Patch Author** (`patch_author.py`):
- LLM을 사용하여 코드 패치 생성
- Reference solution patch 분석 및 학습
- 테스트를 통과하도록 코드 수정

**LLM Client** (`llm_client.py`):
- OpenAI API 클라이언트
- 프롬프트 관리 및 응답 처리

#### 2. **Protocol Layer** (`bench_agent/protocol/`)

**Diff Validator** (`diff_validator.py`):
- Unified diff 형식 검증
- Hunk header의 line number 정확도 검증 및 수정
- Multi-hunk 패치의 line number 보정

**Diff Cleaner** (`diff_cleaner.py`):
- LLM 출력에서 markdown 코드 블록 제거
- conftest.py 관련 diff 제거
- Diff 형식 정규화

**Patch Builder** (`patch_builder.py`):
- Test diff와 Code diff를 결합
- Unified diff 형식으로 변환
- conftest.py 주입 관리 (필요 시)

**Policy** (`policy.py`):
- 테스트 정책 검증:
  - `forbid_skip`: pytest.skip() 사용 금지
  - `forbid_xfail`: pytest.xfail() 사용 금지
  - `forbid_network`: 네트워크 호출 금지
  - `restrict_file_io`: 파일 I/O 제한 (tmp_path 사용 권장)

**Reference Analyzers**:
- `reference_patch_analyzer.py`: Reference solution patch 구조 분석
- `reference_test_analyzer.py`: Reference test patch 구조 분석

#### 3. **Runner Layer** (`bench_agent/runner/`)

**SWE-bench Runner** (`swebench_runner.py`):
- SWE-bench harness와 통합
- Docker 컨테이너 내에서 테스트 실행
- Public/Hidden 테스트 분리 실행

**Splitter** (`splitter.py`):
- 테스트를 Public/Hidden으로 분할
- 전략: `keep_failing_public_then_random`
- Public ratio: 0.7 (70% Public, 30% Hidden)

**Report Parser** (`report_parser.py`):
- SWE-bench harness 리포트 파싱
- Pytest 출력 파싱
- 테스트 통과/실패 통계 추출

**Error Analyzer** (`error_analyzer.py`):
- 패치 적용 오류 분석
- 테스트 실패 오류 분석
- LLM 피드백용 구조화된 오류 메시지 생성

**Conftest Injector** (`conftest_injector.py`):
- pytest conftest.py 파일 주입
- 테스트 분할 메커니즘 구현

#### 4. **Main Script** (`scripts/run_mvp.py`)

메인 실행 루프:
```python
for instance_id in instance_ids:
    for iteration in range(1, max_iters + 1):
        # 1. 현재 패치로 테스트 실행
        result = run_swebench_eval(...)
        
        # 2. Controller가 전략 결정
        decision = decide(failure, history, problem_statement)
        
        # 3. Test Author 또는 Patch Author 실행
        if focus == "tests" or "both":
            test_diff = propose_tests(...)
        if focus == "patch" or "both":
            code_diff = propose_patch(...)
        
        # 4. Diff 검증 및 결합
        combined_patch = combine_diffs(test_diff, code_diff)
        
        # 5. 다음 반복 또는 종료
```

---

## 🔄 실행 플로우 (Execution Flow)

### 1. 초기화
- 설정 파일 로드 (`configs/mvp.yaml`)
- SWE-bench 데이터셋 로드
- LLM 클라이언트 초기화

### 2. 각 인스턴스별 처리

**반복 루프 (최대 8회 또는 시간 제한까지)**:

```
Iteration N:
├─ 1. 현재 패치로 Public 테스트 실행
│  └─ SWE-bench harness 실행
│
├─ 2. 결과 분석
│  ├─ 테스트 통과율 확인
│  ├─ 실패 로그 분석
│  └─ Error Analyzer로 구조화된 피드백 생성
│
├─ 3. Controller 의사결정
│  ├─ Problem Statement 분석
│  ├─ 실패 로그 분석
│  ├─ 이전 반복 히스토리 검토
│  └─ focus 결정: tests/patch/both
│
├─ 4. Test Author (필요 시)
│  ├─ Reference test patch 분석
│  ├─ 버그 재현 테스트 생성
│  ├─ BRS 검증 (버그 있는 코드에서 실패)
│  └─ Test diff 생성
│
├─ 5. Patch Author (필요 시)
│  ├─ Reference solution patch 분석
│  ├─ 코드 수정 패치 생성
│  ├─ Line number 정확도 보장
│  └─ Code diff 생성
│
├─ 6. Diff 검증 및 결합
│  ├─ Diff Validator로 형식 검증
│  ├─ Diff Cleaner로 정제
│  ├─ Policy 검증
│  └─ Combined patch 생성
│
├─ 7. 종료 조건 확인
│  ├─ Public 테스트 모두 통과?
│  ├─ 최대 반복 횟수 도달?
│  └─ 시간 제한 도달?
│
└─ 8. Hidden 테스트 평가 (Public 통과 시)
   └─ Overfitting 검증
```

### 3. 최종 평가

- **Public Pass Rate**: Public 테스트 통과율
- **Hidden Pass Rate**: Hidden 테스트 통과율
- **Overfit Gap**: Public - Hidden (0에 가까울수록 좋음)
- **BRS**: Bug Reproduction Strength (버그 있는 코드에서 테스트 실패 여부)

---

## 📊 평가 메트릭 (Metrics)

### 1. HFS (Hidden Fix Score)
- Hidden 테스트 통과율
- 목표: 1.0 (100%)

### 2. TSS (Test Strength Score)
- 테스트 강도
- BRS와 Public Pass Rate의 조합

### 3. BRS (Bug Reproduction Strength)
- 버그 있는 코드에서 테스트 실패 여부
- 목표: `fail_on_buggy = True`

### 4. Overall Score
- 종합 점수 (HFS, TSS, BRS의 가중 평균)
- 목표: 최대한 높게

---

## 🔍 Public 테스트 vs Hidden 테스트

### 정의

#### Public 테스트
- **정의**: 에이전트가 **반복 과정에서 볼 수 있는** 테스트 집합
- **용도**: 패치 생성 및 개선을 위한 피드백 제공
- **실행 시점**: 각 반복마다 실행 (패치 적용 후)
- **환경 변수**: `TA_SPLIT=public`

#### Hidden 테스트
- **정의**: 에이전트가 **반복 과정에서 볼 수 없는** 테스트 집합
- **용도**: Overfitting 검증 및 최종 평가
- **실행 시점**: Public 테스트가 모두 통과한 후 최종 평가 시에만 실행
- **환경 변수**: `TA_SPLIT=hidden`

### 분할 전략 (Split Strategy)

프로젝트는 **`keep_failing_public_then_random`** 전략을 사용합니다:

```
1. 모든 테스트 nodeid 수집
2. 실패하는 테스트(failing tests)는 항상 Public에 포함
   → 에이전트가 버그를 수정하도록 유도
3. 나머지 테스트 중 public_ratio(예: 0.7)만큼을 Public에 할당
4. 나머지 테스트는 Hidden에 할당
```

**예시**:
- 전체 테스트: 100개
- 실패하는 테스트: 10개
- public_ratio: 0.7

분할 결과:
- **Public**: 실패하는 10개 + (100-10) × 0.7 = 10 + 63 = **73개**
- **Hidden**: 100 - 73 = **27개**

### 차이점 요약

| 구분 | Public 테스트 | Hidden 테스트 |
|------|--------------|---------------|
| **접근성** | 에이전트가 볼 수 있음 | 에이전트가 볼 수 없음 |
| **실행 빈도** | 매 반복마다 실행 | 최종 평가 시에만 실행 |
| **목적** | 패치 개선을 위한 피드백 | Overfitting 검증 |
| **포함 내용** | 실패 테스트 + 랜덤 샘플 | 나머지 테스트 |
| **환경 변수** | `TA_SPLIT=public` | `TA_SPLIT=hidden` |
| **파일 위치** | `.ta_split.json`의 `public` 키 | `.ta_split.json`의 `hidden` 키 |

### 구현 메커니즘

#### 1. Split 파일 생성
`.ta_split.json` 파일이 저장소 루트에 생성됩니다:

```json
{
  "public": [
    "tests/test_modeling.py::test_separability_matrix",
    "tests/test_io.py::test_rst_format",
    ...
  ],
  "hidden": [
    "tests/test_modeling.py::test_compound_model",
    "tests/test_io.py::test_ascii_reader",
    ...
  ]
}
```

#### 2. Conftest Injection
`conftest.py`가 자동으로 주입되어 pytest collection 시점에 테스트를 필터링합니다:

```python
# conftest.py (자동 주입)
def pytest_collection_modifyitems(config, items):
    split = os.environ.get("TA_SPLIT", "public")
    # .ta_split.json을 읽어서 해당 split에 속한 테스트만 선택
    target = spec.get(split, set())
    # 나머지 테스트는 deselected
```

#### 3. 실행 흐름

```
반복 과정:
├─ 1. 현재 패치 적용
├─ 2. TA_SPLIT=public으로 Public 테스트만 실행
├─ 3. 결과 분석 및 패치 개선
└─ 4. Public 테스트 통과 시 다음 반복, 실패 시 재시도

최종 평가:
├─ 1. Public 테스트 모두 통과 확인
├─ 2. TA_SPLIT=hidden으로 Hidden 테스트 실행
├─ 3. Overfit Gap 계산 = Public Pass Rate - Hidden Pass Rate
└─ 4. Overfit Gap이 0에 가까울수록 좋음 (Overfitting 없음)
```

### Overfitting 방지

**Overfitting**이란 Public 테스트만 맞추는 편법 패치를 의미합니다.

예시:
- ❌ **편법 패치**: Public 테스트의 특정 조건만 확인하는 하드코딩
- ✅ **올바른 패치**: 근본적인 버그를 수정하여 모든 테스트 통과

**Overfit Gap**:
```
Overfit Gap = Public Pass Rate - Hidden Pass Rate
```

- **0에 가까울수록 좋음**: Public과 Hidden 모두 비슷한 성능 (Overfitting 없음)
- **큰 값은 나쁨**: Public은 높지만 Hidden은 낮음 (Overfitting 존재)

**목표**: Overfit Gap을 최소화하여 일반화된 패치 생성

### 실제 사용 예시

```python
# splitter.py의 make_split 함수
def make_split(nodeids, failing_nodeids, public_ratio=0.7, seed=0):
    # 1. 모든 테스트 nodeid 수집
    all_set = list(dict.fromkeys(nodeids))
    
    # 2. 실패하는 테스트 추출
    failing = [n for n in failing_nodeids if n in all_set]
    
    # 3. 나머지 테스트 추출
    remaining = [n for n in all_set if n not in set(failing)]
    
    # 4. Public에 할당할 테스트 수 계산
    target_public = int(round(public_ratio * len(all_set)))
    
    # 5. 실패 테스트는 항상 Public에 포함
    pub = list(failing)
    
    # 6. 나머지에서 필요한 만큼 추가
    needed = max(0, target_public - len(pub))
    pub += remaining[:needed]
    
    # 7. Hidden에는 나머지 모두
    hid = [n for n in all_set if n not in set(pub)]
    
    return SplitSpec(public=pub, hidden=hid)
```

### 설정

`configs/mvp.yaml`에서 분할 비율을 설정합니다:

```yaml
split:
  strategy: keep_failing_public_then_random
  public_ratio: 0.7  # 70% Public, 30% Hidden
  seed: 0            # 재현성을 위한 랜덤 시드
```

이 설정은:
- 실패하는 테스트는 항상 Public에 포함
- 나머지 테스트의 70%를 Public에, 30%를 Hidden에 할당
- 동일한 시드로 재현 가능한 분할 보장

---

## 🔧 주요 설정 (Configuration)

### `configs/mvp.yaml` 구조

```yaml
runner:
  mode: swebench_harness
  dataset_name: princeton-nlp/SWE-bench_Lite

instances:
  list:
    - astropy__astropy-12907
    - sympy__sympy-20590
    # ...

split:
  strategy: keep_failing_public_then_random
  public_ratio: 0.7  # 70% Public, 30% Hidden
  seed: 0

limits:
  max_iters: 8        # 최대 반복 횟수
  time_limit_minutes: 30  # 인스턴스당 시간 제한

llm:
  enabled: true
  model: gpt-4o-mini

policy:
  forbid_skip: true      # pytest.skip() 금지
  forbid_xfail: true     # pytest.xfail() 금지
  forbid_network: true   # 네트워크 호출 금지
  restrict_file_io: true # 파일 I/O 제한
```

---

## 📁 디렉토리 구조

```
test_aware_swebench_mvp_v2/
├── bench_agent/              # 핵심 에이전트 코드
│   ├── agent/                # LLM 에이전트 (Controller, Test Author, Patch Author)
│   ├── protocol/             # Diff 처리, 검증, 정책
│   └── runner/               # SWE-bench 실행, 리포트 파싱
│
├── scripts/                  # 실행 스크립트
│   ├── run_mvp.py           # 메인 실행 루프
│   ├── run_mvp_nohup.sh     # 백그라운드 실행
│   ├── analyze_performance.py # 성능 분석
│   └── ...
│
├── configs/                  # 설정 파일
│   └── mvp.yaml             # 메인 설정
│
├── outputs/                  # 실행 결과
│   └── {run-id}/
│       └── {instance-id}/
│           ├── run.jsonl    # 반복 로그
│           ├── predictions.jsonl  # 최종 패치
│           ├── final_patch.diff
│           ├── final_tests.diff
│           └── metrics.json
│
├── logs/                     # 실행 로그
│   └── {run-id}.log
│
└── 00-README.md             # 프로젝트 README
```

---

## 🚀 실행 방법

### 일반 실행
```bash
python scripts/run_mvp.py --config configs/mvp.yaml --run-id mvp-001 --max-workers 1
```

### 장시간 실행 (백그라운드)
```bash
./scripts/run_mvp_nohup.sh configs/mvp.yaml mvp-001 1
```

### 성능 분석
```bash
python scripts/analyze_performance.py mvp-001
```

---

## 🔍 핵심 특징

### 1. Reference Patch 활용
- Reference solution patch와 test patch를 분석하여 LLM에 제공
- 올바른 파일, 함수, line number를 학습하도록 유도

### 2. Iterative Improvement
- Controller가 각 반복마다 전략 결정
- 실패 시 Error Analyzer로 구조화된 피드백 제공
- 최대 8회까지 점진적 개선

### 3. Overfitting 방지
- Public/Hidden 테스트 분리
- Overfit Gap 모니터링
- Hidden 테스트 통과율 추적

### 4. 정책 검증
- 편법 패치 방지 (skip, xfail 금지)
- 보안 정책 준수 (네트워크, 파일 I/O 제한)

### 5. Robust Diff 처리
- Diff Validator로 line number 정확도 보장
- Diff Cleaner로 LLM 출력 정제
- Multi-hunk 패치 자동 수정

---

## 📈 현재 성과

최신 실행 결과 (`mvp-20251215-013151`):
- **성공률**: 50% (4개 중 2개 성공)
- **Overall Score**: 58.91%
- **Overfit Gap**: 0.00% (모든 인스턴스)
- **BRS 성공률**: 75% (4개 중 3개)

자세한 분석은 `FINAL_ANALYSIS_REPORT.md`를 참조하세요.

---

*이 문서는 프로젝트의 목적, 목표, 아키텍처를 종합적으로 설명합니다.*

