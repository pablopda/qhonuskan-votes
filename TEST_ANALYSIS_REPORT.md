# Test Suite Analysis Report: /home/user/qhonuskan-votes/demo/app/tests/

## Executive Summary
- Total Test Files: 5 (6 if counting Playwright)
- Total Tests: 114 (without Playwright tests that require the module)
- Passing Tests: 111
- Failing Tests: 3
- Import Errors: 1 (Playwright module not installed)
- Tests with Missing Assertions: 1
- New Files Without Test Coverage: 5

---

## 1. BROKEN TESTS (3 FAILURES)

All three failures are related to the same root cause: **Vote deletion signal handling issue**.

### Issue: TypeError in Vote Deletion
**Problem**: When deleting a vote, `vote_changed.send(sender=self)` is called AFTER the vote has been deleted from the database. At this point, the model instance no longer has a primary key, causing Django's signal dispatcher to fail when trying to hash the instance.

#### Test #1: test_vote_deletion
- **File**: `/home/user/qhonuskan-votes/demo/app/tests/test_models.py`
- **Line**: 299-305
- **Class**: `TestThreadModelVote`
- **Error**: `TypeError: Model instances without primary key value are unhashable`
- **Traceback**:
  ```
  demo/app/tests/test_models.py:303: in test_vote_deletion
      vote.delete()
  demo/qhonuskan_votes/models.py:410: in delete
      vote_changed.send(sender=self)
  ```

#### Test #2: test_signal_fired_on_vote_delete
- **File**: `/home/user/qhonuskan-votes/demo/app/tests/test_models.py`
- **Line**: 318-326
- **Class**: `TestVoteSignals`
- **Error**: `TypeError: Model instances without primary key value are unhashable`
- **Traceback**: Same as above (line 410 in models.py)

#### Test #3: test_score_updates_after_vote_deletion
- **File**: `/home/user/qhonuskan-votes/demo/app/tests/test_models.py`
- **Line**: 469-479
- **Class**: `TestObjectsWithScoresManager`
- **Error**: `TypeError: Model instances without primary key value are unhashable`
- **Traceback**: Same as above (line 410 in models.py)

**Root Cause**: In `/home/user/qhonuskan-votes/demo/qhonuskan_votes/models.py`, line 407-410:
```python
super(Vote, self).delete(*args, **kwargs)  # Line 407: deletes the instance from DB

# Send signals after deletion
vote_changed.send(sender=self)  # Line 410: tries to use instance that no longer has pk
```

**Impact**: Any code that deletes votes will fail with TypeError.

**Recommendation**: Move the `vote_changed.send(sender=self)` call to BEFORE the `super().delete()` call, or save the pk/state before deletion and pass it to the signal differently.

---

## 2. IMPORT ERRORS (1 ERROR)

### Error: Missing Playwright Module
- **File**: `/home/user/qhonuskan-votes/demo/app/tests/test_voting.py`
- **Line**: 5
- **Error**: `ModuleNotFoundError: No module named 'playwright'`
- **Code**:
  ```python
  from playwright.sync_api import expect
  ```

**Impact**: All E2E tests in `test_voting.py` (4 tests) cannot be collected or run:
  - `test_upvote_and_cancel`
  - `test_upvote_then_downvote`
  - `test_multiple_users_voting_same_thread`
  - `test_single_user_voting_multiple_threads`

**Recommendation**: 
1. Install Playwright: `pip install playwright`
2. Install browser binaries: `playwright install`
3. Or mark these tests as conditional on Playwright being installed using pytest markers

---

## 3. TESTS WITH INCOMPLETE ASSERTIONS

### Test Missing Final Assertion
- **File**: `/home/user/qhonuskan-votes/demo/app/tests/test_models.py`
- **Line**: 349-360
- **Test**: `TestVoteSignals.test_signal_sender_is_vote_instance`
- **Issue**: Test extracts the sender but never asserts anything about it

**Current Code**:
```python
@pytest.mark.django_db
def test_signal_sender_is_vote_instance(self, thread, user, signal_receiver):
    """Test that signal sender is the vote instance."""
    vote = thread.votes.create(voter=user, value=1)
    
    # Check the sender passed to the signal
    call_args = signal_receiver.call_args
    assert call_args is not None
    # Signal sends 'sender' as the vote instance
    sender = call_args[1].get('sender') or call_args[0][0] if call_args[0] else None
    if sender is None and call_args[1]:
        sender = call_args[1].get('sender')
    # ^^^ TEST ENDS HERE - NO ASSERTION ABOUT sender!
```

**Impact**: The test doesn't actually verify that the sender is the vote instance. It extracts the value but doesn't validate it.

**Recommendation**: Add assertion at the end:
```python
assert isinstance(sender, type(vote)), f"Expected sender to be vote instance, got {type(sender)}"
assert sender == vote  # or whatever the intended check is
```

---

## 4. TESTS WITH KNOWN ISSUES / COMMENTS

### Known Bug: Score Recalculation on Toggle
- **File**: `/home/user/qhonuskan-votes/demo/app/tests/test_views.py`
- **Lines**: 124, 150, 641
- **Tests Affected**:
  - `TestVoteEndpointSuccess.test_toggle_upvote_removes_vote` (line 124)
  - `TestVoteEndpointSuccess.test_toggle_downvote_removes_vote` (line 150)
  - `TestVoteEndpointEdgeCases.test_full_vote_cycle` (line 641)

**Code Example** (line 120-127):
```python
# Second upvote should toggle off
response = authenticated_client.post(vote_url, {
    'vote_model': get_vote_model_name(),
    'object_id': thread.pk,
    'value': 1
})
assert response.status_code == 200
data = response.json()
assert data['voted_as'] == 0
# Note: Score should be 0 after toggle, but there's a known bug in score recalculation
# Verify the vote was actually deleted from database
vote_count = thread.votes.filter(voter__username='testuser').count()
assert vote_count == 0
```

**Issue**: The tests acknowledge that there's a bug where the score doesn't update correctly after toggling votes. The test works around this by only checking `voted_as` and vote count, not the score.

**Recommendation**: 
1. Create an issue to track this bug
2. Fix the score recalculation logic
3. Add proper score assertion once fixed

---

## 5. MISSING TEST COVERAGE FOR NEW FILES

The following files are mentioned as new but have no test coverage:

### 5.1 services.py
- **Status**: File does not exist
- **Expected Location**: `/home/user/qhonuskan-votes/demo/app/services.py`
- **Tests Needed**: Test service layer functionality (business logic)

### 5.2 forms.py
- **Status**: File does not exist
- **Expected Location**: `/home/user/qhonuskan-votes/demo/app/forms.py`
- **Tests Needed**: 
  - Form validation
  - Form rendering
  - Error handling

### 5.3 repositories.py
- **Status**: File does not exist
- **Expected Location**: `/home/user/qhonuskan-votes/demo/app/repositories.py`
- **Tests Needed**:
  - Database queries
  - Data retrieval logic
  - Caching (if applicable)

### 5.4 cache.py
- **Status**: File does not exist
- **Expected Location**: `/home/user/qhonuskan-votes/demo/app/cache.py`
- **Tests Needed**:
  - Cache hit/miss scenarios
  - Cache invalidation
  - TTL handling
  - Fallback behavior

### 5.5 signals.py
- **Status**: File does not exist
- **Expected Location**: `/home/user/qhonuskan-votes/demo/app/signals.py`
- **Tests Needed**:
  - Signal connection/disconnection
  - Signal dispatch on various actions
  - Signal handler execution
  - Error handling in signal handlers

---

## 6. FIXTURE ANALYSIS

All fixtures appear well-designed with proper `@pytest.fixture` decorators and `db` parameter usage. No issues found with fixture definitions.

### Fixtures Used:
- `user`, `user2`, `user3` - Create test users (proper)
- `thread`, `thread2`, `thread3` - Create test threads (proper)
- `client` - Django test client (proper)
- `authenticated_client` - Pre-authenticated client (proper)
- `vote_model` - Get the ThreadModelVote model (proper)
- `signal_receiver` - MagicMock for signal testing (proper, with cleanup)
- `disconnect_signal` - Auto-disconnect/reconnect signal (proper for isolation)

**No fixture issues identified.**

---

## 7. CIRCULAR DEPENDENCY CHECK

Tested imports with Django setup:
```
PYTHONPATH=/home/user/qhonuskan-votes/demo python -c \
  "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings'); \
   import django; django.setup(); \
   from app.models import ThreadModel; \
   from qhonuskan_votes.models import VotesField; \
   print('Imports successful')"
```

**Result**: No circular import dependencies detected. ✓

---

## 8. ASSERTION QUALITY ANALYSIS

Most assertions are well-structured. Notable patterns:

**Good assertions**:
- `assert response.status_code == 200`
- `assert vote.value == 1`
- `assert thread.votes.count() == 2`
- `assert thread_with_score.vote_score == 2`

**Weak assertions** (that should be improved):
- Line 357-359 in test_models.py: Extracts value but doesn't assert it

---

## 9. TEST ORGANIZATION

**Structure**: Well-organized into 5 test files by functionality:
- `test_models.py` - Model and manager tests (50 tests)
- `test_views.py` - View/endpoint tests (48 tests)
- `test_templatetags.py` - Template tag tests (16 tests)
- `test_utils.py` - Utility function tests (9 tests)
- `test_voting.py` - E2E/integration tests with Playwright (4 tests, not runnable)

**Classes**: Well-organized with test classes grouping related tests

**Documentation**: Good docstrings on all test methods

---

## SUMMARY TABLE

| Category | Count | Status |
|----------|-------|--------|
| Total Tests | 114 | - |
| Passing Tests | 111 | ✓ |
| Failing Tests | 3 | ✗ |
| Collection Errors | 1 | ⚠ |
| Tests w/ Incomplete Assertions | 1 | ⚠ |
| Missing File Coverage | 5 | ✗ |
| Circular Dependencies | 0 | ✓ |
| Fixture Issues | 0 | ✓ |

---

## RECOMMENDED ACTIONS (Priority Order)

### CRITICAL
1. **Fix vote deletion signal** - Affects 3 failing tests
   - Move `vote_changed.send(sender=self)` before `super().delete()`
   - Or refactor to capture state before deletion

### HIGH
2. **Install Playwright** - Enables E2E test execution
   - `pip install playwright && playwright install`
   - Or make Playwright tests conditional

3. **Complete test_signal_sender_is_vote_instance** - Add missing assertion
   - Verify sender is actually the vote instance

### MEDIUM
4. **Fix score recalculation bug** - Address known issue
   - Debug why score doesn't update on vote toggle
   - Uncomment score assertions once fixed

5. **Create test files for new modules** - Add coverage for:
   - services.py
   - forms.py
   - repositories.py
   - cache.py
   - signals.py

### LOW
6. **Documentation** - Document new files and modules as they're created

---

## DETAILED FAILURE LOGS

```
FAILED demo/app/tests/test_models.py::TestThreadModelVote::test_vote_deletion
TypeError: Model instances without primary key value are unhashable

FAILED demo/app/tests/test_models.py::TestVoteSignals::test_signal_fired_on_vote_delete
TypeError: Model instances without primary key value are unhashable

FAILED demo/app/tests/test_models.py::TestObjectsWithScoresManager::test_score_updates_after_vote_deletion
TypeError: Model instances without primary key value are unhashable
```

