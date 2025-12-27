# Deployment Notes

## 2025-01-27: Fix email-validator dependency

**Issue:** Fly.io backend crash on startup with `ImportError: email-validator is not installed, run 'pip install pydantic[email]'`

**Root Cause:** Backend uses `EmailStr` from Pydantic in `app/schemas/auth.py`, but `email-validator` package was not included in `requirements.txt`.

**Fix:** Added `email-validator>=2.0.0` to `backend/requirements.txt`. The Dockerfile installs dependencies via `pip install -r requirements.txt`, so this fix is automatically included in the container build.

**Files Changed:**
- `backend/requirements.txt` - Added `email-validator>=2.0.0`

**Verification:**
- Dependency is installed during Docker build (line 67: `RUN pip install --no-cache-dir -r requirements.txt`)
- EmailStr import works: `from pydantic import EmailStr`

**Deployment:**
- Merge `fix/fly-email-validator` branch
- Run `fly deploy` - container will rebuild with new dependency
- Check logs: `fly logs -a thandev-backend` to confirm successful boot

