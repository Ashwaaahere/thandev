# Hotfix: UI Stuck "Running" - Root Cause Analysis

## Issue Summary

The UI gets stuck showing "Running" status for scan sessions, preventing proper completion. The root cause is a Pydantic validation error when loading session state from Redis.

## Error Message

```
pydantic ValidationError: total_runtime_sec Input should be a valid integer, got fractional part
```

## Root Cause Analysis

### Write Path (Where fractional values are created)

1. **Step Execution** (`services/thandev-runner/app/tasks.py:83`):
   - Uses `time.time()` which returns a float (e.g., `123.456`)
   - Calculates: `execution_time = time.time() - start_time` → **float value**

2. **StepResult Creation** (`services/thandev-runner/app/tasks.py:156`):
   - Creates `StepResult` with `execution_time_sec=execution_time` (float)
   - Published to Redis stream as string: `"execution_time_sec": "123.456"`

3. **Session State Update** (`services/thandev-brain/app/controller/session_controller.py:358`):
   - Sums execution times: `total_runtime = sum(r.execution_time_sec for r in results.values())`
   - This sum is a **float** (e.g., `45.67`)
   - Written to Redis via `update_session()`: `updates["total_runtime_sec"] = total_runtime`

### Read Path (Where validation fails)

1. **Session State Model** (`services/thandev-brain/app/models.py:191`):
   ```python
   total_runtime_sec: int = Field(default=0, ge=0, description="Total runtime in seconds")
   ```
   - **Type mismatch**: Model expects `int`, but Redis contains `float` (e.g., `45.67`)

2. **Session Load** (`services/thandev-brain/app/session/state.py:158`):
   - Reads JSON from Redis: `state_dict = json.loads(data)`
   - Attempts to create `SessionState(**state_dict)`
   - **Pydantic validation fails** because `total_runtime_sec` is `45.67` (float) but model expects `int`

3. **Brain Loop Crash** (`services/thandev-brain/app/controller/session_controller.py:127`):
   - `get_session()` returns `None` due to validation error
   - Loop logs error but doesn't handle gracefully
   - Session remains in "RUNNING" status forever

## Exact Write/Read Mismatch

| Location | Type Written | Type Expected | Result |
|----------|-------------|----------------|--------|
| `tasks.py:83` | `float` (from `time.time()`) | - | ✅ Correct |
| `session_controller.py:358` | `float` (sum of floats) | - | ✅ Correct |
| `state.py:196` | `float` (written to Redis JSON) | - | ✅ Correct |
| `models.py:191` | - | `int` | ❌ **Mismatch** |
| `state.py:158` | `float` (from JSON) | `int` (Pydantic) | ❌ **Validation Error** |

## Impact

- **UI**: Sessions stuck in "Running" status
- **Brain Loop**: Crashes silently, session never transitions to COMPLETED
- **User Experience**: Cannot see scan results, must manually check logs

## Solution

Change `total_runtime_sec` type from `int` to `float` in the `SessionState` model to match the actual data being written.

## Files Affected

1. `services/thandev-brain/app/models.py` - Change field type
2. `services/thandev-brain/app/session/state.py` - Ensure serialization handles float
3. `services/thandev-brain/app/controller/session_controller.py` - Add error handling guard

## Additional Safeguards

1. Add error handling in brain loop to mark session as ERROR if state read fails
2. Add regression test to ensure fractional values load successfully
3. Ensure all runtime calculations use consistent float types

