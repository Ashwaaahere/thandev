# Thandev — Security Intelligence & Scanning (Hybrid SiteZapper)

**Thandev** is a developer-first security platform that combines **real-time threat intelligence** (CVE/KEV/PoCs/news) with **automated vulnerability scanning** (SiteZapper).

> MVP: ingest & display real-time security items, store in DB, cross-link with your scan findings. LLM/RAG comes next.

---

## ✨ Modules
- **backend/** — FastAPI + Celery/Redis + Postgres (APIs, ingestion, enrichment).
- **frontend/** — Next.js + Tailwind (UI: live feed, filters, detail pages).
- **.github/** — CI, CodeQL, issue/PR templates, Dependabot.
- **docker-compose.yml** — local dev stack (web API + UI + db + redis + worker).

## 🧱 Architecture
Ingest (NVD, CISA KEV, Exploit-DB, vendor advisories) → Normalize → Enrich (EPSS, KEV, PoCs) → Store (Postgres) → API (FastAPI) → UI (Next.js).

## 🚀 Quickstart
```bash
# 1) Start all services (first run builds the images)
docker compose up --build

# 2) API (FastAPI): http://localhost:8000/docs
# 3) Frontend (Next.js): http://localhost:3000
# 4) Postgres: localhost:5432 (user: thandev, pass: thandev, db: thandev)
# 5) Redis: localhost:6379
```

## 🧪 Health checks
- API: `GET /health` → `{"status":"ok"}`
- Frontend: Home page renders “Thandev Feed”

## 🗂 Project layout
```
thandev/
  backend/               # FastAPI app + Celery worker
  frontend/              # Next.js app
  .github/workflows/     # CI and security scans
  .github/ISSUE_TEMPLATE # Issue templates
  docker-compose.yml
  SECURITY.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  LICENSE
```

## 🧰 Dev scripts
```bash
# format/lint (backend)
docker compose exec api bash -lc "ruff check . && black --check ."

# run unit tests (backend - placeholder)
docker compose exec api pytest -q
```

## 🔒 Security policy
See **SECURITY.md** for how to report vulnerabilities. We run **CodeQL** on PRs.

## 🤝 Contributing
Read **CONTRIBUTING.md**. Use our issue templates and PR template for smooth reviews.

## 📜 License
MIT — see **LICENSE**.
