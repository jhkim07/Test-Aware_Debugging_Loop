# 최종 실험 분석 리포트

**실행 ID**: `mvp-20251215-013151`  
**실행 완료**: 2025-12-15 01:52:52  
**설정 파일**: `configs/mvp.yaml`

---

## 📊 실행 요약

### 전체 통계

| 지표 | 값 |
|------|-----|
| 총 인스턴스 | 4개 |
| 완료된 인스턴스 | 4개 (100%) |
| 성공한 인스턴스 (Public Pass Rate > 0%) | 2개 |
| **성공률** | **50.0%** |
| 평균 반복 횟수 | 2.8회 |

### 평균 메트릭

| 메트릭 | 값 |
|--------|-----|
| Public Pass Rate | 50.00% |
| Hidden Pass Rate | 50.00% |
| Overfit Gap | 0.00% |
| 평균 Iterations | 2.8회 |

### 평균 점수

| 점수 | 값 |
|------|-----|
| HFS (Hidden Fix Score) | 50.00% |
| TSS (Test Strength Score) | 62.50% |
| BRS Score | 75.00% |
| **Overall Score** | **58.91%** |

---

## ✅ 성공한 인스턴스 (2개)

### 1. `sympy__sympy-20590` - 🎯 완벽 성공

**결과**:
- ✅ Public Pass Rate: **100.00%**
- ✅ Hidden Pass Rate: **100.00%**
- ✅ Overfit Gap: **0.00%**
- ✅ BRS: **Tests fail on buggy code** ✅
- Iterations: **1회** (효율적으로 해결)
- Overall Score: **99.37%**

**분석**: 첫 번째 반복에서 바로 성공적으로 패치를 생성하고 모든 테스트를 통과했습니다. BRS도 올바르게 작동하여 버그 있는 코드에서 테스트가 실패합니다.

### 2. `astropy__astropy-12907` - 🎯 완벽 성공

**결과**:
- ✅ Public Pass Rate: **100.00%**
- ✅ Hidden Pass Rate: **100.00%**
- ✅ Overfit Gap: **0.00%**
- ✅ BRS: **Tests fail on buggy code** ✅
- Iterations: **1회** (효율적으로 해결)
- Overall Score: **99.37%**

**분석**: 마찬가지로 첫 번째 반복에서 성공적으로 해결되었습니다. Public과 Hidden 테스트 모두 통과했고, Overfitting 없이 올바른 패치를 생성했습니다.

---

## ❌ 실패한 인스턴스 (2개)

### 1. `astropy__astropy-14182` - 패치 적용 실패

**결과**:
- ❌ Public Pass Rate: **0.00%**
- ❌ Hidden Pass Rate: **0.00%**
- Overfit Gap: **0.00%**
- ✅ BRS: **Tests fail on buggy code** ✅
- Iterations: **8회** (최대 반복까지 시도)
- Overall Score: **22.50%**

**실패 원인 분석**:

1. **패치 적용 오류 (Hunk Failed)**:
   ```
   Patch apply error: Hunk #1 failed at line 2
   ```
   - 패치의 hunk header에서 지정한 line number가 실제 파일의 line number와 일치하지 않음
   - `diff_validator`가 여러 번 수정 시도했지만 (`Corrected old_count: 7 → 10`, `7 → 13` 등) 여전히 실패
   - Context lines가 부족하거나 실제 파일과 일치하지 않음

2. **테스트 실행되지 않음**:
   - Public tests: `passed: 0, failed: 0, total: 0`
   - 패치가 적용되지 않아 테스트 자체가 실행되지 않음

3. **반복적 시도**:
   - 8번의 반복 동안 계속 패치 적용에 실패
   - 각 반복마다 동일한 패턴의 오류 발생

**제안된 해결책**:
- Reference patch를 더 자세히 분석하여 정확한 line number 확인
- 더 많은 context lines (20줄 이상) 포함
- 실제 파일의 현재 상태를 정확히 확인 후 패치 생성

### 2. `astropy__astropy-14365` - 테스트 정책 위반

**결과**:
- ❌ Public Pass Rate: **0.00%**
- ❌ Hidden Pass Rate: **0.00%**
- Overfit Gap: **0.00%**
- ❌ BRS: **Tests pass on buggy code** ❌
- Iterations: **1회** (정책 위반으로 조기 종료)
- Overall Score: **14.38%**

**실패 원인 분석**:

1. **테스트 정책 위반**:
   ```
   Test diff rejected by policy:
   - file I/O patterns found: ['\\bopen\\('] (consider removing or using tmp_path carefully)
   ```
   - 생성된 테스트 diff에 `open()` 함수 사용이 포함되어 있음
   - SWE-bench 정책에서 file I/O를 제한하는데, 이를 위반하여 테스트가 거부됨

2. **BRS 실패**:
   - BRS: `fail_on_buggy: false`
   - 버그 있는 코드에서 테스트가 통과함 (버그 재현 실패)

**제안된 해결책**:
- Test Author 프롬프트에 file I/O 제한을 더 명확히 강조
- `tmp_path` 사용 방법에 대한 예시 제공
- Reference test patch에서 file I/O 사용 패턴 확인 및 학습

---

## 🔍 주요 인사이트

### 긍정적인 측면

1. **성공률 50%**: 절반의 인스턴스에서 완벽하게 성공 (Public/Hidden 모두 100%)
2. **Overfitting 없음**: 모든 인스턴스에서 Overfit Gap이 0.00%
3. **BRS 성공률 75%**: 4개 중 3개에서 버그 재현 테스트가 올바르게 작동
4. **효율성**: 성공한 인스턴스들은 모두 1회 반복으로 해결
5. **TSS 점수 양호**: Test Strength Score가 62.50%로 양호한 수준

### 개선이 필요한 측면

1. **패치 적용 실패** (`astropy-14182`):
   - Line number 정확도 문제
   - Context line 부족 또는 불일치
   - Reference patch 분석 강화 필요

2. **정책 위반** (`astropy-14365`):
   - File I/O 사용 규칙 위반
   - Test Author 프롬프트 개선 필요
   - 정책 검증 강화 필요

3. **평균 Overall Score**: 58.91%로 개선 여지 있음
4. **성공률**: 50%에서 향상 가능

---

## 📈 성능 비교

### 인스턴스별 Overall Score 순위

| 순위 | 인스턴스 | Overall Score | 상태 |
|------|----------|---------------|------|
| 1 | `sympy__sympy-20590` | 99.37% | ✅ 성공 |
| 1 | `astropy__astropy-12907` | 99.37% | ✅ 성공 |
| 3 | `astropy__astropy-14182` | 22.50% | ❌ 실패 |
| 4 | `astropy__astropy-14365` | 14.38% | ❌ 실패 |

### 반복 횟수 분석

- **성공한 인스턴스**: 평균 1.0회 반복 (매우 효율적)
- **실패한 인스턴스**: 평균 4.5회 반복
  - `astropy-14182`: 8회 (최대 반복까지 시도)
  - `astropy-14365`: 1회 (정책 위반으로 조기 종료)

---

## 🎯 구체적인 개선 전략

### 1. 패치 적용 정확도 향상

**문제**: `astropy-14182`에서 hunk line number 불일치

**전략**:
- Reference patch의 정확한 line number를 더 세밀하게 분석
- 실제 파일의 현재 상태를 먼저 확인 후 패치 생성
- Context lines를 20줄 이상 포함하도록 강제
- Patch Author 프롬프트에 line number 검증 단계 추가

### 2. 테스트 정책 준수 강화

**문제**: `astropy-14365`에서 file I/O 사용으로 정책 위반

**전략**:
- Test Author 프롬프트에 정책 위반 사례 명확히 명시
- `tmp_path` 사용 예시 제공
- 정책 검증을 diff 생성 전에 수행
- Reference test patch 분석 시 정책 준수 패턴 학습

### 3. 반복 전략 개선

**현재**: 실패 시 계속 시도하지만 동일한 패턴의 오류 반복

**전략**:
- 패치 적용 실패 시 더 구체적인 에러 피드백 제공
- 특정 유형의 실패 (예: line number 오류) 감지 시 다른 접근 시도
- Reference patch를 더 자세히 분석하도록 유도

---

## 📝 결론

### 전체 평가

**성공률 50%**는 개선 여지가 있지만, 성공한 2개 인스턴스는 **완벽한 성능**(Public/Hidden 모두 100%, Overfit Gap 0%)을 보였습니다. 

**주요 강점**:
- ✅ Overfitting이 전혀 없음 (모든 인스턴스에서 Overfit Gap 0%)
- ✅ 성공한 인스턴스는 1회 반복으로 효율적으로 해결
- ✅ BRS 성공률 75% (버그 재현 테스트가 잘 작동)

**주요 약점**:
- ❌ 패치 적용 정확도 문제 (line number 불일치)
- ❌ 테스트 정책 위반 (file I/O 사용)
- ❌ 평균 Overall Score 58.91%로 향상 필요

### 다음 단계

1. **즉시 적용 가능한 개선**:
   - Test Author 프롬프트에 정책 위반 경고 강화
   - Patch Author 프롬프트에 line number 검증 단계 추가
   - Context lines 최소 20줄 포함 강제

2. **중기 개선**:
   - 패치 적용 실패 시 더 구체적인 피드백 메커니즘
   - Reference patch 분석 강화
   - 정책 검증 로직 강화

3. **장기 개선**:
   - 패치 생성 품질 향상을 위한 프롬프트 엔지니어링
   - 다양한 인스턴스 유형에 대한 일반화

---

## 📎 참고 자료

- **성능 리포트 JSON**: `outputs/mvp-20251215-013151/performance_report.json`
- **로그 파일**: `logs/mvp-20251215-013151.log`
- **결과 디렉토리**: `outputs/mvp-20251215-013151/`
- **각 인스턴스 상세 결과**: `outputs/mvp-20251215-013151/{instance_id}/`

---

*리포트 생성 시간: 2025-12-15*

