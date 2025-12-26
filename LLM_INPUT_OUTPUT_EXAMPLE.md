# LLM 입출력 완전 예시

**Instance**: astropy__astropy-12907
**날짜**: 2025-12-26
**모델**: gpt-4o-mini (P0.9 성공 케이스)

---

## 📋 목차

1. [SWE-bench 제공 데이터](#1-swe-bench-제공-데이터)
2. [Test Author LLM 입출력](#2-test-author-llm-입출력)
3. [Patch Author LLM 입출력](#3-patch-author-llm-입출력)
4. [비교 분석](#4-비교-분석)

---

## 1. SWE-bench 제공 데이터

SWE-bench_Lite 데이터셋에서 제공하는 원본 데이터입니다.

### 📥 INPUT 1: problem_statement

```
Modeling's `separability_matrix` does not compute separability correctly for nested CompoundModels

Consider the following model:

```python
from astropy.modeling import models as m
from astropy.modeling.separable import separability_matrix

cm = m.Linear1D(10) & m.Linear1D(5)
```

It's separability matrix as you might expect is a diagonal:

```python
>>> separability_matrix(cm)
array([[ True, False],
       [False,  True]])
```

If I make the model more complex:
```python
>>> separability_matrix(m.Pix2Sky_TAN() & m.Linear1D(10) & m.Linear1D(5))
array([[ True,  True, False, False],
       [ True,  True, False, False],
       [False, False,  True, False],
       [False, False, False,  True]])
```

The output matrix is again, as expected, the outputs and inputs to the linear
models are separable and independent of each other.

If however, I nest these compound models:
```python
>>> separability_matrix(m.Pix2Sky_TAN() & cm)
array([[ True,  True, False, False],
       [ True,  True, False, False],
       [False, False,  True,  True],    # ← WRONG! Should be [True, False]
       [False, False,  True,  True]])   # ← WRONG! Should be [False, True]
```
Suddenly the inputs and outputs are no longer separable?

This feels like a bug to me, but I might be missing something?
```

**의미**: 버그 설명 - nested CompoundModel의 separability_matrix가 잘못된 결과 반환

---

### 📥 INPUT 2: test_patch (Reference Test Diff)

```diff
diff --git a/astropy/modeling/tests/test_separable.py b/astropy/modeling/tests/test_separable.py
--- a/astropy/modeling/tests/test_separable.py
+++ b/astropy/modeling/tests/test_separable.py
@@ -28,6 +28,13 @@
 p1 = models.Polynomial1D(1, name='p1')


+cm_4d_expected = (np.array([False, False, True, True]),
+                  np.array([[True,  True,  False, False],
+                            [True,  True,  False, False],
+                            [False, False, True,  False],
+                            [False, False, False, True]]))
+
+
 compound_models = {
     'cm1': (map3 & sh1 | rot & sh1 | sh1 & sh2 & sh1,
             (np.array([False, False, True]),
@@ -52,7 +59,17 @@
     'cm7': (map2 | p2 & sh1,
             (np.array([False, True]),
              np.array([[True, False], [False, True]]))
-            )
+            ),
+    'cm8': (rot & (sh1 & sh2), cm_4d_expected),
+    'cm9': (rot & sh1 & sh2, cm_4d_expected),
+    'cm10': ((rot & sh1) & sh2, cm_4d_expected),
+    'cm11': (rot & sh1 & (scl1 & scl2),
+             (np.array([False, False, True, True, True]),
+              np.array([[True,  True,  False, False, False],
+                        [True,  True,  False, False, False],
+                        [False, False, True,  False, False],
+                        [False, False, False, True,  False],
+                        [False, False, False, False, True]]))),
 }


```

**의미**:
- 테스트 파일에 추가할 내용 (정답)
- `cm_4d_expected` 변수 정의
- `compound_models` 딕셔너리에 `cm8`, `cm9`, `cm10`, `cm11` 추가
- 테스트 함수는 추가하지 않음 (기존 parametrized test가 자동으로 실행)

---

### 📥 INPUT 3: patch (Reference Solution Diff)

```diff
diff --git a/astropy/modeling/separable.py b/astropy/modeling/separable.py
--- a/astropy/modeling/separable.py
+++ b/astropy/modeling/separable.py
@@ -242,7 +242,7 @@ def _cstack(left, right):
         cright = _coord_matrix(right, 'right', noutp)
     else:
         cright = np.zeros((noutp, right.shape[1]))
-        cright[-right.shape[0]:, -right.shape[1]:] = 1
+        cright[-right.shape[0]:, -right.shape[1]:] = right

     return np.hstack([cleft, cright])
```

**의미**:
- 파일: `astropy/modeling/separable.py`
- 함수: `_cstack`
- 변경: Line 245에서 `= 1`을 `= right`로 수정
- 버그 원인: 1 (상수)을 넣어야 할 곳에 right (행렬) 값을 넣어야 함

---

## 2. Test Author LLM 입출력

Test Author는 버그를 검증하는 테스트를 생성합니다.

### 📥 INPUT (Test Author에게 주어지는 것)

**System Prompt** (179줄, 주요 부분만):
```
You are the Test Author for a test-aware debugging agent.
Your goal is to CREATE and STRENGTHEN pytest tests iteratively.

CRITICAL: You will receive Reference Test Patch showing correct expected values.
Your tests MUST reproduce this SPECIFIC bug described in the Problem Statement.

CRITICAL: Reference Test Patch Usage:
- ALWAYS check the Reference Test Patch
- **MOST IMPORTANT**: Follow the EXACT structure
  * If Reference Test Patch adds items to dictionary WITHOUT creating test
    functions, do the SAME
  * If Reference Test Patch creates test functions, you can create test functions
  * DO NOT add test functions if Reference Test Patch only uses dictionary structure
- If Reference Test Patch defines an expected value (e.g., `cm_4d_expected`),
  USE IT DIRECTLY
- Match the exact expected values from the Reference Test Patch

Hard constraints:
- DO NOT add pytest.skip / xfail
- DO NOT use network (requests/urllib/socket)
- Avoid file I/O. Use in-memory objects or pytest tmp_path only if necessary
- Tests must be deterministic and fast

Output format:
Output ONLY a unified diff format.
DO NOT include markdown code block markers (```).
```

**User Message**:
```
Repository context (partial):
SWE-bench Instance: astropy__astropy-12907
Repository: astropy/astropy
Base commit: d16bfe05a74...

=== Problem Statement ===
Modeling's `separability_matrix` does not compute separability correctly
for nested CompoundModels
(... problem statement 전체 내용 ...)

=== Reference Test Patch (for guidance) ===
diff --git a/astropy/modeling/tests/test_separable.py
--- a/astropy/modeling/tests/test_separable.py
+++ b/astropy/modeling/tests/test_separable.py
@@ -28,6 +28,13 @@
 p1 = models.Polynomial1D(1, name='p1')

+cm_4d_expected = (np.array([False, False, True, True]),
+                  np.array([[True,  True,  False, False],
+                            [True,  True,  False, False],
+                            [False, False, True,  False],
+                            [False, False, False, True]]))
+
 compound_models = {
     ...
     'cm7': (map2 | p2 & sh1, ...),
+    'cm8': (rot & (sh1 & sh2), cm_4d_expected),
+    'cm9': (rot & sh1 & sh2, cm_4d_expected),
+    'cm10': ((rot & sh1) & sh2, cm_4d_expected),
(... Reference Test Patch 전체 내용 ...)

=== Reference Test Patch Analysis ===
Expected values found in Reference Test Patch:
  - cm_4d_expected: (array([False, False, True, True]), array([[True, True, False, False], ...
Use these EXACT expected value names and definitions in your test.

CRITICAL: Reference Test Patch uses DICTIONARY structure.
You MUST use the SAME structure type in your test patch.

Failure summary:
(empty - first iteration)

Current tests hint (optional):
(empty)

Produce a unified diff for pytest tests only.
```

**입력 요약**:
- ✅ Problem Statement (버그 설명)
- ✅ Reference Test Patch (정답 테스트 - 어떻게 테스트를 추가해야 하는지)
- ✅ Reference Test Analysis (expected value 추출)
- ✅ 명확한 지시: "Dictionary 구조 사용, 테스트 함수 생성 안 함"

---

### 📤 OUTPUT (gpt-4o-mini 생성)

```diff
diff --git a/astropy/modeling/tests/test_separable.py b/astropy/modeling/tests/test_separable.py
--- a/astropy/modeling/tests/test_separable.py
+++ b/astropy/modeling/tests/test_separable.py
@@ -28,6 +28,13 @@
 p1 = models.Polynomial1D(1, name='p1')

+cm_4d_expected = (np.array([False, False, True, True]),
+                  np.array([[True,  True,  False, False],
+                            [True,  True,  False, False],
+                            [False, False, True,  False],
+                            [False, False, False, True]]))
+
+
 compound_models = {
     'cm1': (map3 & sh1 | rot & sh1 | sh1 & sh2 & sh1,
             (np.array([False, False, True]),
@@ -52,7 +59,17 @@
     'cm7': (map2 | p2 & sh1,
             (np.array([False, True]),
              np.array([[True, False], [False, True]]))
-            )
+            ),
+    'cm8': (rot & (sh1 & sh2), cm_4d_expected),
+    'cm9': (rot & sh1 & sh2, cm_4d_expected),
+    'cm10': ((rot & sh1) & sh2, cm_4d_expected),
+    'cm11': (rot & sh1 & (scl1 & scl2),
+             (np.array([False, False, True, True, True]),
+              np.array([[True,  True,  False, False, False],
+                        [True,  True,  False, False, False],
+                        [False, False, True,  False, False],
+                        [False, False, False, True,  False],
+                        [False, False, False, False, True]]))),
 }
```

**출력 분석**:
- ✅ Reference Test Patch와 **거의 완전히 동일**
- ✅ `cm_4d_expected` 정의 (정확히 같은 값)
- ✅ Dictionary에 `cm8`, `cm9`, `cm10`, `cm11` 추가 (정확히 같은 구조)
- ✅ 테스트 함수 생성 안 함 (Reference도 안 만들었음)
- ✅ `.ta_split.json`도 생성되었을 것 (predictions.jsonl 참고)

---

## 3. Patch Author LLM 입출력

Patch Author는 버그를 수정하는 코드 패치를 생성합니다.

### 📥 INPUT (Patch Author에게 주어지는 것)

**System Prompt** (278줄, 주요 부분만):
```
You are the Patch Author for a test-aware debugging agent.
Goal: implement a minimal, correct fix so that tests pass.

CRITICAL: You will receive Reference Solution Patch showing the CORRECT fix.
Your patch MUST closely follow the Reference Solution Patch.
Do not invent different solutions.

Your task - FOLLOW THIS ORDER STRICTLY:
STEP 1: Study the Reference Solution Patch - THIS IS YOUR PRIMARY GUIDE
  * Identify the file
  * Identify the function/class
  * Analyze the changes (lines with - are removed, + are added)
  * Extract variable names
  * Extract the logic

CRITICAL REQUIREMENTS:
1. FILE AND FUNCTION MATCHING:
   - Modify the SAME file as Reference Solution Patch
   - Modify the SAME function/class

2. EXACT CHANGE MATCHING:
   - If Reference removes a line, remove the SAME line
   - If Reference adds a line, add a SIMILAR line

3. VARIABLE AND LOGIC MATCHING:
   - Use the SAME variable names
   - Use the SAME logic approach (don't invent alternatives)
   - Example: If reference uses 'right', do NOT use 'np.eye(right.shape[1])'

4. LINE NUMBER ACCURACY (CRITICAL):
   - Match the EXACT hunk header line numbers
   - If reference shows @@ -27,7 +27,6 @@, your patch MUST start at line 27

5. CONTEXT LINES:
   - Include 15-20 lines of context around each change

6. OUTPUT FORMAT:
   - Output ONLY unified diff format
   - DO NOT include markdown code block markers
```

**User Message**:
```
Repository context (includes Problem Statement and Reference Solution Patch):
SWE-bench Instance: astropy__astropy-12907
Repository: astropy/astropy

=== Problem Statement ===
Modeling's `separability_matrix` does not compute separability correctly
for nested CompoundModels
(... problem statement 전체 내용 ...)

=== Reference Solution Patch (FOLLOW THIS CLOSELY) ===
diff --git a/astropy/modeling/separable.py b/astropy/modeling/separable.py
--- a/astropy/modeling/separable.py
+++ b/astropy/modeling/separable.py
@@ -242,7 +242,7 @@ def _cstack(left, right):
         cright = _coord_matrix(right, 'right', noutp)
     else:
         cright = np.zeros((noutp, right.shape[1]))
-        cright[-right.shape[0]:, -right.shape[1]:] = 1
+        cright[-right.shape[0]:, -right.shape[1]:] = right

     return np.hstack([cleft, cright])

=== Reference Patch Analysis ===
File: astropy/modeling/separable.py
Function: _cstack (line 235-247)
Change: Line 245
  - Remove: cright[-right.shape[0]:, -right.shape[1]:] = 1
  - Add: cright[-right.shape[0]:, -right.shape[1]:] = right
Hunk: @@ -242,7 +242,7 @@

IMPORTANT: Use these EXACT line numbers and file paths in your patch.

============================================================
CRITICAL INSTRUCTIONS FOR REFERENCE SOLUTION PATCH:
============================================================
1. FILE AND FUNCTION MATCHING:
   - Modify astropy/modeling/separable.py
   - Modify _cstack function

2. EXACT CHANGE ANALYSIS:
   - Line 245: Change = 1 to = right
   - Understand: Bug was using constant 1 instead of right matrix

3. VARIABLE AND LOGIC MATCHING:
   - Use variable 'right' (not np.eye or other alternatives)

Failure summary:
Tests failed: separability_matrix returns wrong values for nested models

New/updated tests diff:
diff --git a/astropy/modeling/tests/test_separable.py
+cm_4d_expected = (...)
+    'cm8': (rot & (sh1 & sh2), cm_4d_expected),
(... Test Author가 생성한 test diff ...)

IMPORTANT: Follow Reference Solution Patch exactly!

Produce a unified diff for production code only. Your patch should closely
match the Reference Solution Patch if provided.
```

**입력 요약**:
- ✅ Problem Statement (버그 설명)
- ✅ Reference Solution Patch (정답 코드 - 어떻게 코드를 수정해야 하는지)
- ✅ Reference Patch Analysis (파일, 함수, 라인 번호 분석)
- ✅ Test diff (Test Author가 생성한 테스트)
- ✅ Failure summary (테스트 실패 로그)
- ✅ 명확한 지시: "Reference를 정확히 따라하라"

---

### 📤 OUTPUT (gpt-4o-mini 생성)

```diff
diff --git a/astropy/modeling/separable.py b/astropy/modeling/separable.py
--- a/astropy/modeling/separable.py
+++ b/astropy/modeling/separable.py
@@ -242,5 +242,5 @@
         cright = _coord_matrix(right, 'right', noutp)
     else:
         cright = np.zeros((noutp, right.shape[1]))
-        cright[-right.shape[0]:, -right.shape[1]:] = 1
+        cright[-right.shape[0]:, -right.shape[1]:] = right

     return np.hstack([cleft, cright])
```

**출력 분석**:
- ✅ Reference Solution Patch와 **완전히 동일한 변경**
- ✅ 같은 파일: `astropy/modeling/separable.py`
- ✅ 같은 함수: `_cstack`
- ✅ 같은 변경: `= 1` → `= right`
- ⚠️ Hunk header 차이: `@@ -242,7 +242,7 @@` vs `@@ -242,5 +242,5 @@`
  - 이유: Context line 개수 차이 (7줄 vs 5줄) - 문제 없음
  - 둘 다 line 242에서 시작, 변경사항 동일

---

## 4. 비교 분석

### 4.1 Test Diff 비교표

| 항목 | Reference Test Patch | gpt-4o-mini Output | 일치 여부 |
|------|---------------------|-------------------|-----------|
| **파일** | `test_separable.py` | `test_separable.py` | ✅ 100% |
| **구조** | Dictionary 추가 (함수 없음) | Dictionary 추가 (함수 없음) | ✅ 100% |
| **Expected value** | `cm_4d_expected = (np.array(...), np.array(...))` | `cm_4d_expected = (np.array(...), np.array(...))` | ✅ 100% |
| **cm8 항목** | `'cm8': (rot & (sh1 & sh2), cm_4d_expected)` | `'cm8': (rot & (sh1 & sh2), cm_4d_expected)` | ✅ 100% |
| **cm9 항목** | `'cm9': (rot & sh1 & sh2, cm_4d_expected)` | `'cm9': (rot & sh1 & sh2, cm_4d_expected)` | ✅ 100% |
| **cm10 항목** | `'cm10': ((rot & sh1) & sh2, cm_4d_expected)` | `'cm10': ((rot & sh1) & sh2, cm_4d_expected)` | ✅ 100% |
| **cm11 항목** | `'cm11': (rot & sh1 & (scl1 & scl2), ...)` | `'cm11': (rot & sh1 & (scl1 & scl2), ...)` | ✅ 100% |

**결론**: Test Diff는 Reference와 **완벽히 일치**

---

### 4.2 Code Diff 비교표

| 항목 | Reference Solution Patch | gpt-4o-mini Output | 일치 여부 |
|------|-------------------------|-------------------|-----------|
| **파일** | `astropy/modeling/separable.py` | `astropy/modeling/separable.py` | ✅ 100% |
| **함수** | `_cstack` | `_cstack` | ✅ 100% |
| **시작 라인** | Line 242 | Line 242 | ✅ 100% |
| **제거 라인** | `cright[...] = 1` | `cright[...] = 1` | ✅ 100% |
| **추가 라인** | `cright[...] = right` | `cright[...] = right` | ✅ 100% |
| **변수명** | `right` | `right` | ✅ 100% |
| **Context** | 7 lines | 5 lines | ⚠️ 차이 (무해) |

**결론**: Code Diff는 핵심 변경사항이 **완벽히 일치**, Context line만 약간 다름

---

### 4.3 성공 요인 분석

#### ✅ gpt-4o-mini가 성공한 이유

1. **정확한 복제 능력**
   - Reference를 보고 그대로 재현
   - "창의성" 없이 단순 복제

2. **지시 준수**
   - System Prompt: "Follow EXACT structure"
   - gpt-4o-mini: ✅ 정확히 따름

3. **Format 정확도**
   - Unified diff format 정확히 생성
   - Markdown markers 없음
   - JSON metadata 추가 안 함

4. **BRS 통과**
   - Expected values를 Reference에서 정확히 복사
   - 테스트가 buggy code에서 실패 (버그 재현 성공)
   - 테스트가 fixed code에서 통과

#### ❌ gpt-4o가 실패하는 이유 (다른 케이스)

1. **과도한 창의성**
   - "이해하고 개선"하려 시도
   - JSON metadata 추가: `{"public": [...], "hidden": [...]}`
   - Malformed patch 생성

2. **Format 오류**
   - Diff 내부에 설명 추가
   - Metadata 포함

3. **BRS 실패**
   - 너무 "관대한" 테스트 생성
   - Expected values를 변형
   - 버그를 재현하지 못함

---

### 4.4 최종 결과

**astropy__astropy-12907 (gpt-4o-mini)**:
```json
{
  "hfs": 1.0,      // Hidden tests: 100% pass after fix
  "tss": 1.0,      // Test strength: 100%
  "brs": 1.0,      // Bug reproduction: 100% (fail on buggy, pass on fixed)
  "og": 0.0,       // Overfit gap: 0%
  "overall": 0.9938,  // 99.38%
  "iterations": 1  // 1번만에 성공
}
```

**성공 공식**:
```
Reference 제공 + 정확한 복제 = Perfect Score
```

---

## 💡 핵심 통찰

### 1. LLM의 역할은 "문제 해결"이 아니라 "정답 복제"

```
Traditional AI Task:
  Input: 문제 설명
  Output: 창의적 해결책

SWE-bench Task:
  Input: 문제 설명 + 정답
  Output: 정답을 정확히 재현
```

### 2. "더 똑똑한" 모델이 실패하는 이유

```
gpt-4o-mini:
  "정답을 보고 그대로 베껴라" → ✅ 정확히 베낌

gpt-4o:
  "정답을 보고 이해해서 개선해라" → ❌ 과도한 개선
```

### 3. Task-specific Model Fit

```
일반 Task: gpt-4o > gpt-4o-mini
이 Project: gpt-4o-mini > gpt-4o

이유: "정확한 복제" 능력이 더 중요
```

### 4. Prompt Engineering의 한계

```
System Prompt (179줄):
  "Follow EXACTLY, do NOT add anything"

gpt-4o:
  "알겠습니다!" → 여전히 metadata 추가 ❌

gpt-4o-mini:
  "알겠습니다!" → 정확히 따름 ✅
```

---

## 📚 참고

- SWE-bench Paper: https://arxiv.org/abs/2310.06770
- Instance: astropy__astropy-12907
- Model: gpt-4o-mini (temperature=0.0)
- Result Directory: `outputs/p0.9-full-test/astropy__astropy-12907/`
- Metrics: BRS=1.0, Overall=99.38%
