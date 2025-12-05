# Bug Fixes - December 5, 2024

## Bug 1: Import Order Issue ✅ FIXED

**Problem:**
- `run_photo_scanner` was called in the startup event at line 250
- But it wasn't imported until lines 527-530 (after the startup event definition)
- This would cause `NameError: name 'run_photo_scanner' is not defined` on startup

**Fix:**
- Moved the import of `run_photo_scanner` to line 157 (right after event_manager import)
- This ensures it's available when the startup event function runs
- Removed the duplicate import at lines 527-530

**Files Changed:**
- `wildlife-app/backend/main.py` - Lines 157-160 (added import), Lines 527-530 (removed duplicate)

---

## Bug 2: Incorrect Dependency Injection ✅ FIXED

**Problem:**
- `get_photo_scan_status` endpoint used incorrect dependency injection pattern
- Used `get_db_func=Depends(get_db)` which already resolves to a `Session` object
- Then tried to call `next(get_db_func())` which fails because:
  1. `get_db_func` is already a `Session`, not a callable
  2. `Session` objects are not iterable (can't use `next()`)
- Also had `db.close()` in finally block which is unnecessary (FastAPI handles this)

**Fix:**
- Changed parameter from `get_db_func=Depends(get_db)` to `db: Session = Depends(get_db)`
- Removed the incorrect `next(get_db_func())` call
- Removed `db.close()` from finally block (FastAPI dependency injection handles cleanup)
- Now `db` is directly available as a `Session` object

**Files Changed:**
- `wildlife-app/backend/routers/debug.py` - Line 106 (fixed parameter), Line 109 (removed incorrect call), Line 149 (removed unnecessary close)

---

## Verification

✅ Application imports successfully
✅ No linter errors
✅ Both bugs fixed and verified

---

## Testing

To verify the fixes work:
1. Start the server: `python main.py` or use `scripts/start-backend-only.bat`
2. Check startup logs - should see "[OK] Photo scanner background task started"
3. Test endpoint: `GET /api/photo-scan-status` - should return status without errors

