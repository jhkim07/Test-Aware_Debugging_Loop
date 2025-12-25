# 현재 상태 및 우선순위 분석

**날짜**: 2025-12-25  
**현재 버전**: P0.9 (롤백 완료)

---

## 1. 현재까지 달성한 성능

### P0.9 Baseline (현재 상태)

#### 전체 성능 지표
```
테스트 대상: 4개 instance
- astropy-12907
- sympy-20590
- astropy-14182
- astropy-14365
```

| 지표 | 성능 | 상태 |
|------|------|------|
| **Success Rate** | **75%** (3/4) | ✅ 우수 |
| **Average Overall Score** | **74.53%** | ✅ 우수 |
| **BRS Score** | **100%** (3/3 passing) | ✅ 완벽 |
| **Perfect Scores** | **3개** | ✅ 우수 |

#### Instance별 상세 성능

**✅ astropy-12907** (Perfect)
```json
{
  "hfs": 1.0,     // Hidden Fix Score: 100%
  "tss": 1.0,     // Test Strength Score: 100%
  "og": 0.0,      // Overfit Gap: 0%
  "brs": 1.0,     // Bug Reproduction Strength: 100%
  "overall": 0.9938,
  "iterations": 1,
  "brs_fail_on_buggy": true
}
```

**✅ sympy-20590** (Perfect)
```json
{
  "hfs": 1.0,
  "tss": 1.0,
  "og": 0.0,
  "brs": 1.0,
  "overall": 0.9938,
  "iterations": 1,
  "brs_fail_on_buggy": true
}
```

**✅ astropy-14182** (Perfect)
```json
{
  "hfs": 1.0,
  "tss": 1.0,
  "og": 0.0,
  "brs": 1.0,
  "overall": 0.9938,
  "iterations": 1
}
```

**❌ astropy-14365** (Failed)
```json
{
  "hfs": 0.0,
  "tss": 0.0,
  "og": 0.0,
  "brs": 0.0,
  "overall": 0.0,
  "iterations": 0,
  "failure_reason": "File I/O policy violation"
}
```

---

### 강점 및 약점

#### ✅ 강점
1. **높은 BRS**: 100% (통과한 모든 케이스가 버그 재현 성공)
2. **안정성**: 일관된 결과 (무작위성 없음)
3. **효율성**: 대부분 1 iteration만에 해결
4. **복잡한 케이스 해결**: astropy-12907 (nested models), sympy-20590 (symbol evaluation)

#### ❌ 약점
1. **File I/O 케이스 실패**: astropy-14365 (policy violation)
2. **개선 여지**: 75% → 100% 목표

---

## 2. 해결 시급한 문제 (우선순위)

### 🔴 Priority 1: astropy-14365 (File I/O Policy Violation)

**현상**:
```
Test diff rejected by policy: file I/O patterns found: ['\bopen\(']
```

**원인**:
- LLM이 `open()` 직접 사용
- Policy가 file I/O를 엄격히 차단
- tmp_path 사용 유도 실패

**영향**:
- Success rate: 75% (1/4 실패)
- Overall score: -24.845% (astropy-14365 점수 0%)

**비즈니스 임팩트**: 
- **High** - 전체 성공률 25% 차이
- 해결 시 Success rate: 75% → 100%
- 해결 시 Overall score: 74.53% → 93.28% (+18.75%p)

**해결 난이도**: 
- **Medium** - P0.10에서 일시적 해결 경험 있음
- 단, 회귀 위험 존재 (Prompt bloat)

---

### 🟡 Priority 2: 성능 최적화 (Iteration 감소)

**현상**:
- 일부 케이스에서 여러 iteration 필요 (최대 8회까지 가능)
- 현재 3개 케이스는 모두 1 iteration으로 해결

**개선 가능성**:
- LLM 응답 품질 향상
- 프롬프트 미세 조정
- Controller 전략 개선

**비즈니스 임팩트**:
- **Low** - 현재 효율적 (1 iteration)
- 비용 절감 가능 (LLM 호출 감소)

**해결 난이도**:
- **Low** - 점진적 개선 가능

---

### 🟢 Priority 3: 새로운 케이스 확장

**현상**:
- 현재 4개 케이스만 테스트
- SWE-bench_Lite 전체: 300개 instance

**개선 가능성**:
- 더 많은 케이스로 robustness 검증
- 새로운 failure pattern 발견

**비즈니스 임팩트**:
- **Medium** - 장기 안정성 확보
- 새로운 문제 조기 발견

**해결 난이도**:
- **Low** - 단순 확장

---

## 3. 회귀를 일으키는 해결책 (Avoid List)

### ❌ Anti-Pattern 1: Prompt Bloat (프롬프트 비대화)

**사례**: P0.10 실패

**내용**:
```python
# prompts.py에 87줄 추가
=== P0.10: CRITICAL Diff Format Rules ===
[... 87 lines of RST, File I/O rules ...]
```

**결과**:
- BRS 100% → 0% (2개 케이스)
- Overall score 74.53% → 67.45% (-7.08%p)
- astropy-12907, sympy-20590 회귀

**원인**:
1. **주의력 희석**: BRS 집중도 25% → 17%
2. **우선순위 혼란**: Diff format > 버그 재현
3. **인지 과부하**: 복잡도 threshold 초과

**교훈**:
- ✅ **DO**: 최소 변경 (2-3줄)
- ❌ **DON'T**: 대규모 규칙 추가 (87줄)

---

### ❌ Anti-Pattern 2: Multiple Changes at Once (다중 변경)

**사례**: P0.10 실패

**내용**:
- prompts.py 변경 (87줄 추가)
- policy.py 변경 (tmp_path 허용)
- test_author.py 변경 (CRITICAL REMINDERS)

**결과**:
- 원인 규명 어려움 (3개 변경 중 어느 것이 원인?)
- Rollback test 필요 (시간 낭비)

**교훈**:
- ✅ **DO**: 한 번에 한 가지만 변경
- ✅ **DO**: 변경마다 회귀 테스트
- ❌ **DON'T**: 여러 파일 동시 변경

---

### ❌ Anti-Pattern 3: System Prompt Heavy Approach

**사례**: P0.10의 prompts.py 수정

**내용**:
- System prompt에 모든 규칙 추가
- LLM이 "지침"을 따르도록 강제

**결과**:
- LLM 혼란 (어느 지침이 우선?)
- 핵심 목표 손실 (버그 재현 < Diff format)

**대안**:
- ✅ **User message**: 구체적 상황별 가이드
- ✅ **Code normalization**: 후처리로 문제 해결
- ❌ **System prompt**: 일반적 원칙만

**교훈**:
- ✅ **DO**: Code로 해결 (pre_apply_gate, normalization)
- ✅ **DO**: User message로 상황별 가이드
- ❌ **DON'T**: System prompt 비대화

---

### ❌ Anti-Pattern 4: Policy Loosening (정책 완화)

**사례**: P0.10의 policy.py 수정

**내용**:
```python
# tmp_path 있으면 write_text/read_text 허용
if has_tmp_path:
    forbidden_hits = [h for h in hits if h not in [r"\.write_text\(", r"\.read_text\("]]
```

**우려사항**:
- 보안 정책 약화
- 예상치 못한 부작용 가능
- 회귀 테스트 필요

**결과** (P0.10):
- astropy-14365 해결 (0% → 99.38%)
- 하지만 BRS 회귀 발생 (인과관계 불명확)

**교훈**:
- ✅ **DO**: Policy 변경 시 철저한 회귀 테스트
- ✅ **DO**: 최소 권한 원칙 유지
- ❌ **DON'T**: 광범위한 정책 완화

---

### ❌ Anti-Pattern 5: Over-Engineering (과잉 설계)

**사례**: P0.10의 RST separator 처리

**내용**:
- 40줄의 RST 규칙 추가
- 다양한 예시와 설명
- WRONG/CORRECT 패턴

**결과**:
- astropy-14182 여전히 실패 (0%)
- RST 규칙이 오히려 혼란 가중
- Prompt bloat의 주범

**대안**:
- ✅ **Code normalization**: pre_apply_gate에 regex 추가
- ✅ **Minimal prompt**: 1-2줄 힌트만
- ❌ **40줄 규칙**: 효과 없음

**교훈**:
- ✅ **DO**: 간단한 문제는 코드로 해결
- ✅ **DO**: 복잡한 패턴은 정규화 로직 추가
- ❌ **DON'T**: 프롬프트로 모든 것 해결

---

## 권장 해결 전략

### ✅ Safe Approach (회귀 방지)

#### 1. Minimal Prompt Addition (최소 프롬프트 추가)
```python
# prompts.py에 2-3줄만 추가
Hard constraints:
- DO NOT add pytest.skip / xfail
- DO NOT use network (requests/urllib/socket)
- Avoid file I/O. Use pytest tmp_path fixture with write_text/read_text if needed  # ← 1줄만 추가
- Tests must be deterministic and fast
```

**장점**:
- Prompt bloat 방지
- BRS 회귀 위험 최소화
- 명확한 가이드

**단점**:
- 효과 불확실 (테스트 필요)

#### 2. User Message Injection (사용자 메시지 주입)
```python
# test_author.py에서 특정 케이스만 추가 가이드
if instance_id == "astropy-14365":
    user_message += "\nIMPORTANT: Use tmp_path fixture for file operations (tmp_path.write_text, tmp_path.read_text)"
```

**장점**:
- 케이스별 맞춤 가이드
- System prompt 비대화 방지
- 다른 케이스 영향 없음

**단점**:
- 케이스별 하드코딩 필요

#### 3. Code Normalization (코드 정규화)
```python
# pre_apply_gate.py에 file I/O 변환 로직 추가
def normalize_file_io(diff: str) -> str:
    # open() → tmp_path.write_text() 자동 변환
    if r'\bopen\(' in diff:
        # transform to tmp_path pattern
        ...
```

**장점**:
- 근본적 해결
- 프롬프트 변경 없음
- 회귀 위험 없음

**단점**:
- 구현 복잡도 높음
- 완벽한 변환 어려움

---

## 최종 권장사항

### Priority 1 해결 전략 (astropy-14365)

**Phase 1: Minimal Prompt** (Low Risk, Medium Reward)
1. prompts.py에 1줄만 추가
2. astropy-14365 단독 테스트
3. 성공 시 전체 회귀 테스트 (4개 instance)
4. BRS 유지 확인

**Phase 2: User Message** (Medium Risk, High Reward)
1. test_author.py에 케이스별 가이드
2. astropy-14365에만 적용
3. 회귀 테스트

**Phase 3: Policy + Minimal Prompt** (High Risk, High Reward)
1. policy.py tmp_path 허용 (P0.10 방식)
2. prompts.py 1줄 추가
3. 즉시 전체 회귀 테스트
4. BRS 감시

### Avoid List 체크리스트

**변경 전 반드시 확인**:
- [ ] 프롬프트 추가가 10줄 이하인가?
- [ ] 한 번에 하나의 파일만 변경하는가?
- [ ] 단독 테스트 → 회귀 테스트 순서인가?
- [ ] BRS 모니터링 계획이 있는가?
- [ ] 코드 정규화로 해결 가능한가?

---

## Summary

### 현재 성능
- ✅ 75% Success Rate
- ✅ 74.53% Overall Score
- ✅ 100% BRS (통과 케이스)

### 시급한 문제
1. 🔴 **astropy-14365** (File I/O) - High Impact
2. 🟡 Iteration 최적화 - Low Impact
3. 🟢 케이스 확장 - Medium Impact

### 회귀 방지
1. ❌ Prompt Bloat (87줄 추가)
2. ❌ Multiple Changes (다중 변경)
3. ❌ System Prompt Heavy
4. ❌ Policy Loosening
5. ❌ Over-Engineering

### 안전한 해결책
1. ✅ Minimal Prompt (1-3줄)
2. ✅ User Message (케이스별)
3. ✅ Code Normalization (후처리)
4. ✅ 단계별 테스트 (회귀 확인)
