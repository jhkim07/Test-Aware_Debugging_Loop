# 해결 방안 분류 및 우선순위 로드맵

**작성일**: 2024-12-24  
**목적**: astropy-14182 & astropy-14365 실패 케이스 해결을 위한 체계적 접근

---

## 📊 해결 방안 분류 체계

### 분류 기준
1. **해결 대상**: astropy-14182 (RST malformed) vs astropy-14365 (Policy rejection)
2. **구현 난이도**: 쉬움 🟢 / 중간 🟡 / 어려움 🔴
3. **예상 효과**: 낮음 / 중간 / 높음
4. **구현 시간**: 즉시 / 단기 (1주) / 중기 (1개월) / 장기 (2개월+)

---

## 🎯 해결 방안 전체 목록

### Category A: LLM 프롬프트 강화 (사전 예방)

| ID | 방안 | 대상 | 난이도 | 효과 | 시간 |
|----|------|------|--------|------|------|
| **A1** | RST File Diff Rules 추가 | astropy-14182 | 🟢 쉬움 | 높음 | 즉시 |
| **A2** | File I/O 가이드 추가 | astropy-14365 | 🟢 쉬움 | 높음 | 즉시 |
| **A3** | Unified Diff 포맷 강화 | 둘 다 | 🟢 쉬움 | 중간 | 즉시 |

### Category B: Normalization 개선 (사후 치료)

| ID | 방안 | 대상 | 난이도 | 효과 | 시간 |
|----|------|------|--------|------|------|
| **B1** | Prefix 있는 라인 검증 | astropy-14182 | 🟡 중간 | 높음 | 1주 |
| **B2** | RST-Specific Handler | astropy-14182 | 🟡 중간 | 중간 | 2주 |
| **B3** | 패턴 학습 시스템 | 둘 다 | 🔴 어려움 | 높음 | 1개월 |

### Category C: Policy 개선

| ID | 방안 | 대상 | 난이도 | 효과 | 시간 |
|----|------|------|--------|------|------|
| **C1** | Policy 조건부 완화 | astropy-14365 | 🟡 중간 | 중간 | 1주 |
| **C2** | Smart Detection | astropy-14365 | 🟡 중간 | 높음 | 2주 |

---

## 🚀 우선순위 매트릭스

### 우선순위 평가 기준

**점수 계산**:
- 효과 (높음=3, 중간=2, 낮음=1)
- 구현 용이성 (쉬움=3, 중간=2, 어려움=1)
- ROI = 효과 × 구현 용이성 / 시간(주)

### 우선순위 순위

| 순위 | ID | 방안 | ROI | 우선순위 | 이유 |
|------|----|------|-----|----------|------|
| **1** | **A1** | RST File Diff Rules | **9.0** | 🔴 **CRITICAL** | 즉시 효과, 높은 ROI |
| **2** | **A2** | File I/O 가이드 | **9.0** | 🔴 **CRITICAL** | 즉시 효과, 높은 ROI |
| **3** | **A3** | Unified Diff 포맷 강화 | **6.0** | 🟠 **HIGH** | 즉시 효과, 중간 ROI |
| **4** | **B1** | Prefix 있는 라인 검증 | **4.5** | 🟠 **HIGH** | 높은 효과, 1주 소요 |
| **5** | **C2** | Smart Detection | **3.0** | 🟡 **MEDIUM** | 높은 효과, 2주 소요 |
| **6** | **B2** | RST-Specific Handler | **3.0** | 🟡 **MEDIUM** | 중간 효과, 2주 소요 |
| **7** | **C1** | Policy 조건부 완화 | **2.0** | 🟢 **LOW** | 중간 효과, 보안 고려 |
| **8** | **B3** | 패턴 학습 시스템 | **1.0** | 🟢 **LOW** | 장기 투자, 1개월+ |

---

## 📅 Phase별 구현 계획

### Phase 1: Quick Wins (즉시 ~ 1주)

**목표**: 즉시 적용 가능한 프롬프트 강화로 50% → 75% 성공률 달성

#### Week 1: 프롬프트 강화

**Day 1-2: A1 - RST File Diff Rules**
- [ ] `bench_agent/agent/prompts.py`의 `SYSTEM_TEST_AUTHOR`에 RST 가이드 추가
- [ ] 예제 코드 작성 (올바른 형태 vs 잘못된 형태)
- [ ] 테스트: astropy-14182 재실행

**Day 3-4: A2 - File I/O 가이드**
- [ ] `SYSTEM_TEST_AUTHOR`에 File I/O 가이드 추가
- [ ] tmp_path, StringIO 사용 예제 추가
- [ ] 테스트: astropy-14365 재실행

**Day 5: A3 - Unified Diff 포맷 강화**
- [ ] 기존 프롬프트에 diff 포맷 규칙 강화
- [ ] 모든 라인은 +, -, space로 시작해야 함 강조
- [ ] 통합 테스트

**예상 결과**:
- astropy-14365: 80-90% 성공률 (프롬프트 개선)
- astropy-14182: 60-70% 성공률 (프롬프트 개선)
- **전체 Success Rate: 50% → 75%**

---

### Phase 2: Normalization 개선 (2-3주)

**목표**: Enhanced normalization으로 75% → 85-90% 성공률 달성

#### Week 2: B1 - Prefix 있는 라인 검증

**구현 내용**:
```python
# bench_agent/protocol/pre_apply_normalization.py
def _sanitize_malformed_patterns_general(self, diff: str):
    # ... 기존 코드 ...
    
    if in_hunk:
        # 기존: prefix 없는 라인만 처리
        if not line.startswith(('+', '-', ' ', '\\')):
            # sanitize
        
        # NEW: prefix 있는 라인도 검증
        if line.startswith('+'):
            content = line[1:].lstrip()  # Remove + and leading spaces
            
            # RST separator 패턴 감지 (따옴표 없이)
            if re.match(r'^\s*[=\-+*#|]{3,}(\s+[=\-+*#|]{3,})*\s*$', content):
                if not (content.strip().startswith('"') or content.strip().startswith("'")):
                    # 따옴표 추가 필요
                    fixed_content = '        "' + content.strip() + '",'
                    fixed_line = '+' + fixed_content
                    sanitized.append(fixed_line)
                    fixes.append(f"Line {i+1}: Unquoted separator → quoted")
                    continue
```

**테스트**:
- [ ] astropy-14182 재실행 (여러 iteration)
- [ ] 성공률 측정

#### Week 3: B2 - RST-Specific Handler

**구현 내용**:
```python
def normalize_rst_diff(diff: str, file_path: str) -> str:
    """RST 파일 전용 정규화"""
    if not (file_path.endswith('.rst') or 'rst' in file_path.lower()):
        return diff
    
    # RST-specific patterns
    # 1. 테이블 구분선 자동 따옴표 처리
    # 2. 들여쓰기 검증
    # 3. prefix 검증
    return normalized_diff
```

**예상 결과**:
- astropy-14182: 85-90% 성공률
- **전체 Success Rate: 75% → 87.5%**

---

### Phase 3: Policy & Learning (1-2개월)

**목표**: 장기적 안정성 및 90%+ 성공률 달성

#### Week 4-5: C2 - Smart Detection

**구현 내용**:
```python
def validate_test_diff_smart(test_diff: str, policy: dict):
    """안전한 file I/O 구분"""
    if 'open(' in test_diff:
        # tmp_path와 함께 사용?
        if 'tmp_path' in test_diff:
            return True, []  # ✅ 허용
        
        # StringIO?
        if 'StringIO' in test_diff:
            return True, []  # ✅ 허용
        
        # 그 외는 거부
        return False, ["Direct file I/O not allowed"]
```

#### Week 6-8: B3 - 패턴 학습 시스템

**구현 내용**:
- 실패 패턴 데이터베이스 구축
- 자동 프롬프트 업데이트
- 실패 빈도 기반 우선순위 조정

**예상 결과**:
- **전체 Success Rate: 87.5% → 90%+**

---

## 📈 예상 개선 효과

### 현재 상태 (P0.9)
```
Success Rate: 50% (2/4)
- ✅ astropy-12907: 성공
- ✅ sympy-20590: 성공
- ❌ astropy-14182: 실패 (malformed)
- ❌ astropy-14365: 실패 (policy)
```

### Phase 1 완료 후 (1주)
```
Success Rate: 75% (3/4)
- ✅ astropy-12907: 성공
- ✅ sympy-20590: 성공
- ✅ astropy-14365: 성공 (프롬프트 개선)
- ❌ astropy-14182: 실패 (일부 개선)
```

### Phase 2 완료 후 (1개월)
```
Success Rate: 87.5% (3.5/4)
- ✅ astropy-12907: 성공
- ✅ sympy-20590: 성공
- ✅ astropy-14365: 성공
- 🟡 astropy-14182: 50-70% 성공률 (normalization 개선)
```

### Phase 3 완료 후 (2개월)
```
Success Rate: 90%+ (3.6+/4)
- ✅ astropy-12907: 성공
- ✅ sympy-20590: 성공
- ✅ astropy-14365: 성공
- ✅ astropy-14182: 80-90% 성공률
```

---

## 🎯 즉시 실행 가능한 항목 (이번 주)

### 우선순위 1: A1 - RST File Diff Rules

**구현 위치**: `bench_agent/agent/prompts.py`의 `SYSTEM_TEST_AUTHOR`

**추가할 내용**:
```python
"""
=== CRITICAL: RST File Diff Rules ===

When modifying .rst files or creating tests with RST table data:

1. RST Table Separators are STRINGS, not diff format:
   ❌ WRONG:
   +    expected = [
   +        "wave response ints",
   ==== ========= ====              ← NO PREFIX! Will fail!
   +    ]
   
   ✅ CORRECT:
   +    expected = [
   +        "wave response ints",
   +        "==== ========= ====",   ← Quoted string with + prefix
   +    ]

2. Test node IDs must have prefix:
   ❌ WRONG:
   "astropy/io/ascii/tests/test_rst.py::test_name",
   
   ✅ CORRECT:
   +        "astropy/io/ascii/tests/test_rst.py::test_name",

3. ALL content lines MUST start with +, -, or space
   - No exceptions
   - Even if it looks like a table separator
   - Even if it's inside a string array

4. When in doubt, quote it and prefix it:
   - Wrap in quotes: "===="
   - Add + prefix: +        "===="
"""
```

### 우선순위 2: A2 - File I/O 가이드

**구현 위치**: `bench_agent/agent/prompts.py`의 `SYSTEM_TEST_AUTHOR`

**추가할 내용**:
```python
"""
=== File I/O in Tests ===

PROHIBITED:
❌ Direct file operations:
   with open('file.txt') as f:
   f = open('data.csv')

ALLOWED:
✅ pytest tmp_path fixture:
   def test_example(tmp_path):
       test_file = tmp_path / "test.txt"
       test_file.write_text("content")
       # test using test_file

✅ StringIO for text data:
   from io import StringIO
   mock_file = StringIO("test content")

✅ Mock objects:
   from unittest.mock import mock_open
   with mock_open(read_data="content") as m:
       # test code

REASON: Direct file I/O violates test isolation and security policies
"""
```

---

## 📊 리스크 평가

### 낮은 리스크 ✅
- **A1, A2, A3**: 프롬프트 추가만으로 기존 기능에 영향 없음
- **B1**: 기존 normalization 로직 확장, 기존 동작 유지

### 중간 리스크 ⚠️
- **B2**: RST-specific handler가 다른 파일 타입에 영향 줄 수 있음
- **C1**: Policy 완화는 보안 리스크 증가 가능

### 높은 리스크 🔴
- **B3**: 패턴 학습 시스템은 복잡도 증가, 버그 가능성

---

## ✅ 체크리스트

### Phase 1 (즉시)
- [x] A1: RST File Diff Rules 프롬프트 추가 ✅ (2024-12-24 완료)
- [x] A2: File I/O 가이드 프롬프트 추가 ✅ (2024-12-24 완료)
- [x] A3: Unified Diff 포맷 강화 ✅ (2024-12-24 완료)
- [ ] astropy-14182 재테스트 (진행 중)
- [ ] astropy-14365 재테스트
- [ ] 성공률 측정 및 문서화

### Phase 2 (1개월)
- [ ] B1: Prefix 있는 라인 검증 구현
- [ ] B2: RST-Specific Handler 구현
- [ ] 통합 테스트
- [ ] 성공률 측정

### Phase 3 (2개월)
- [ ] C2: Smart Detection 구현
- [ ] B3: 패턴 학습 시스템 설계 및 구현
- [ ] Full regression test (300 instances)
- [ ] 모니터링 및 지속적 개선

---

## 📝 참고사항

1. **프롬프트 강화가 가장 효과적**: ROI 9.0으로 최고
2. **사전 예방 > 사후 치료**: 프롬프트 개선이 normalization보다 효과적
3. **단계적 접근**: Phase별로 성공률 측정하며 진행
4. **리스크 관리**: Policy 완화는 신중하게 접근

---

**작성자**: AI Code Assistant  
**최종 업데이트**: 2024-12-24  
**상태**: ✅ Ready for Implementation

