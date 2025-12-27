# Rollback Instructions for P0.9.1 Phase 1

## Safe Rollback Point: v0.9.1-phase1-verified

**Git Tag**: `v0.9.1-phase1-verified`
**Commit**: `ba7fcb3`
**Date**: 2025-12-27 18:00 KST
**Status**: ✅ Production Ready - Performance Independently Verified

---

## When to Rollback

Rollback to this verified version if:

1. **Future development causes regressions**
   - P0.9.2 or later versions show performance degradation
   - BRS drops below 100%
   - Average Overall drops below 0.90
   - Any instance shows significant regression

2. **Experimental features fail**
   - Plan-then-Diff 2-stage implementation causes issues
   - New features introduce instability
   - Breaking changes need to be reverted

3. **Production deployment issues**
   - Need to quickly restore stable version
   - Critical bugs discovered in newer versions

---

## Verified Performance at This Point

### Overall Metrics
- **BRS**: 100% (4/4 instances)
- **Average Overall**: 0.950
- **Perfect Scores**: 3/4 instances (≥0.987)

### Instance-Level Results
| Instance | BRS | HFS | TSS | Overall | Status |
|----------|-----|-----|-----|---------|--------|
| astropy-12907 | 1.0 | 1.0 | 1.0 | 0.987 | ✅ Perfect |
| sympy-20590 | 1.0 | 1.0 | 1.0 | 0.994 | ✅ Perfect |
| astropy-14182 | 1.0 | 1.0 | 0.5 | 0.825 | ✅ Good |
| astropy-14365 | 1.0 | 1.0 | 1.0 | 0.994 | ✅ Perfect |

---

## Rollback Methods

### Method 1: Temporary Checkout (Testing Only)

Use this to temporarily test the verified version without changing your current branch:

```bash
# Checkout the verified tag
git checkout v0.9.1-phase1-verified

# Test the verified version
PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
  ~/anaconda3/envs/testing/bin/python scripts/run_mvp.py \
  --config configs/p091_regression_test.yaml \
  --run-id rollback-test-$(date +%Y%m%d-%H%M%S)

# Return to your previous branch
git checkout main
```

### Method 2: Create New Branch from Verified Tag (Recommended)

Use this to create a new branch based on the verified version for continued development:

```bash
# Create and checkout new branch from verified tag
git checkout -b rollback-to-verified v0.9.1-phase1-verified

# Verify you're on the correct version
git log --oneline -3

# Expected output:
# ba7fcb3 MAJOR UPDATE: P0.9.1 Phase 1 Performance Verification Complete
# 32eb433 docs: Comprehensive project status and performance report
# 482d73f docs: P0.9.1 Phase 1 final report

# Continue development from this stable point
# When ready, merge or push this branch
```

### Method 3: Hard Reset main to Verified Tag (CAUTION)

⚠️ **WARNING**: This will discard all commits after the verified tag. Only use if you're certain you want to permanently discard newer changes.

```bash
# BACKUP FIRST - Create a backup branch
git branch backup-before-rollback

# Hard reset main to verified tag
git checkout main
git reset --hard v0.9.1-phase1-verified

# Force push to remote (if needed)
# WARNING: This rewrites history on remote
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_jh" git push origin main --force

# If you made a mistake, recover from backup:
# git reset --hard backup-before-rollback
```

### Method 4: Revert Specific Commits

If only specific commits need to be undone:

```bash
# List commits after verified tag
git log v0.9.1-phase1-verified..HEAD --oneline

# Revert specific commits (creates new commits)
git revert <commit-hash>

# Push to remote
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_jh" git push origin main
```

---

## Verification After Rollback

After rolling back, verify the system works correctly:

### 1. Check Code Version
```bash
# Verify you're at the correct commit
git log --oneline -1
# Expected: ba7fcb3 MAJOR UPDATE: P0.9.1 Phase 1 Performance Verification Complete

# Check for the verification report
ls -la P091_PHASE1_VERIFICATION_REPORT.md
```

### 2. Run Quick Test
```bash
# Test single instance (fast verification)
PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
  ~/anaconda3/envs/testing/bin/python scripts/run_mvp.py \
  --config configs/test_gpt4o_14365.yaml \
  --run-id rollback-verify-$(date +%Y%m%d-%H%M%S)

# Check result
cat outputs/rollback-verify-*/astropy__astropy-14365/metrics.json
# Expected Overall: ~0.994
```

### 3. Run Full Regression Test (Optional)
```bash
# Full test on all 4 instances
PYTHONPATH=/home/jin/prj_ws/agenticAI/Test-Aware_Debugging_Loop:$PYTHONPATH \
  ~/anaconda3/envs/testing/bin/python scripts/run_mvp.py \
  --config configs/p091_regression_test.yaml \
  --run-id rollback-full-verify-$(date +%Y%m%d-%H%M%S)

# Check results
find outputs/rollback-full-verify-* -name "metrics.json" -exec cat {} \;
```

---

## What's Included at This Tag

### Core Implementation
- **P0.9.1 Phase 1**: Policy violation auto-retry mechanism
  - Location: `scripts/run_mvp.py` lines 317-395
  - MAX_POLICY_RETRIES = 2
  - Auto-generates corrective feedback for policy violations

### Documentation
- `PROJECT_STATUS_REPORT.md`: Comprehensive performance report (VERIFIED)
- `P091_PHASE1_VERIFICATION_REPORT.md`: Independent verification results
- `P091_PHASE1_FINAL_REPORT.md`: Phase 1 implementation details

### Configuration
- `configs/p091_regression_test.yaml`: Full regression test config
- `configs/test_gpt4o_14365.yaml`: Single instance test config

### Known Limitations at This Point
- **astropy-14182**: TSS = 0.5 (LLM patch quality variability)
  - BRS and HFS both 1.0 (bug reproduction and fix work correctly)
  - Overall: 0.825 (still good performance)
  - Root cause: LLM generates patches with minor quality issues
  - Not a framework bug - would require different approach

---

## Comparison with Other Versions

### P0.9 (Baseline)
- BRS: 75% (3/4)
- Average Overall: 0.713
- astropy-14365: 0.0 (FAILED)

### P0.9.1 Phase 1 (This Tag) ✅
- BRS: 100% (4/4)
- Average Overall: 0.950
- astropy-14365: 0.994 (FIXED)

### P0.9.1 Phase 2 (FAILED - Rolled Back)
- BRS: 100% (4/4)
- Average Overall: 0.800 (regression from 0.950)
- astropy-14182: 0.225 (severe regression from 0.825)
- Reason: Malformed patch cleaning too aggressive

---

## Support and Contact

If you need help with rollback:

1. **Check commit history**:
   ```bash
   git log --graph --oneline --all | head -20
   ```

2. **View tag details**:
   ```bash
   git show v0.9.1-phase1-verified
   ```

3. **List all tags**:
   ```bash
   git tag -l "v0.9*"
   ```

---

## Safety Checklist Before Rollback

- [ ] Understand why you're rolling back
- [ ] Create backup branch (if using hard reset)
- [ ] Verify you have the correct tag: `v0.9.1-phase1-verified`
- [ ] Check current branch: `git branch`
- [ ] Review commits you'll lose: `git log v0.9.1-phase1-verified..HEAD`
- [ ] Choose appropriate rollback method (1-4 above)
- [ ] Plan verification after rollback

---

**Last Updated**: 2025-12-27 18:15 KST
**Verified Commit**: ba7fcb3
**Git Tag**: v0.9.1-phase1-verified
