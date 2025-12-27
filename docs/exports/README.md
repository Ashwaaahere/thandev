# Thandev Documentation Exports

This directory contains the generated documentation for Thandev in both Markdown and PDF formats.

## Directory Structure

```
docs/exports/
├── markdown/          # Source Markdown files
├── pdfs/              # Generated PDF files
├── assets/            # Images/diagrams (if needed)
└── README.md          # This file
```

## Generated Documentation

### Individual Documentation Files

1. **THANDEV_OVERVIEW.md** / **THANDEV_OVERVIEW.pdf**
   - Product purpose, user journey, feature list
   - What works today vs coming soon
   - The "happy path" (login → create project → run scan → view findings → download report)

2. **THANDEV_ARCHITECTURE.md** / **THANDEV_ARCHITECTURE.pdf**
   - System components: frontend, backend, brain, runner, redis/postgres
   - Dataflow diagrams (Mermaid)
   - Sequence diagrams for scan execution

3. **THANDEV_BACKEND.md** / **THANDEV_BACKEND.pdf**
   - Folder map (backend/app/*)
   - Core modules: api routes, services, models, schemas, core config
   - Scan orchestration
   - Findings pipeline
   - Reporting (PDF generation)

4. **THANDEV_BRAIN.md** / **THANDEV_BRAIN.pdf**
   - services/thandev-brain overview
   - Planner inputs/outputs
   - RAG storage + embedding provider setup
   - Report prompt building
   - Finding enrichment endpoints

5. **THANDEV_RUNNER.md** / **THANDEV_RUNNER.pdf**
   - services/thandev-runner overview
   - Redis streams contract
   - Tool execution backends
   - Concurrency limits and idempotency

6. **THANDEV_FRONTEND.md** / **THANDEV_FRONTEND.pdf**
   - frontend/app routes
   - Dashboard components
   - Scan progress UX
   - Findings UI data contract
   - Auth/session behavior

7. **THANDEV_INFRA_AND_DEVOPS.md** / **THANDEV_INFRA_AND_DEVOPS.pdf**
   - Local dev setup
   - Deployment targets (fly/vercel/cloud-run)
   - Required services
   - Operational notes

8. **THANDEV_SECURITY_MODEL.md** / **THANDEV_SECURITY_MODEL.pdf**
   - Tenancy model, isolation strategy
   - Auth flow + headers
   - Rate limiting / CORS / security headers

### Complete Documentation

9. **THANDEV_FULL_REPO.md** / **THANDEV_FULL_REPO.pdf**
   - Master document containing all sections in order
   - Complete A-to-Z documentation

## Regenerating Documentation

### Prerequisites

1. **Python 3.11+** with standard library (no external dependencies required for generation)
2. **Node.js 18+** with npm (for PDF export)
3. **System libraries** (for PDF generation on Linux):
   ```bash
   # Ubuntu 24.04+
   sudo apt-get install -y libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2t64
   
   # Older Ubuntu/Debian
   sudo apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
   ```

### Step 1: Generate Markdown Files

Run the documentation generator script:

```bash
cd /home/ashwath/thandev
python3 scripts/generate_thandev_docs.py
```

This script:
- Scans the repository structure
- Extracts API routes, models, tools, configs
- Generates markdown files in `docs/exports/markdown/`
- Includes source references (file paths, line ranges)

**Output**: 9 Markdown files in `docs/exports/markdown/`

### Step 2: Generate PDF Files

Run the PDF export script:

```bash
cd /home/ashwath/thandev
./scripts/export_docs_to_pdf.sh
```

This script:
- Converts each markdown file to PDF using `npx md-to-pdf`
- Outputs PDFs to `docs/exports/pdfs/`
- Handles errors gracefully with troubleshooting tips

**Output**: 9 PDF files in `docs/exports/pdfs/`

### One-Command Regeneration

To regenerate everything:

```bash
cd /home/ashwath/thandev
python3 scripts/generate_thandev_docs.py && ./scripts/export_docs_to_pdf.sh
```

## Documentation Quality

### Source References

All documentation includes source references:
- File paths (e.g., `backend/app/api/scans.py`)
- Line numbers where applicable
- Code snippets with context

### No Hallucinations

The generator script:
- Only documents what exists in the codebase
- Extracts information from actual files
- Labels assumptions explicitly
- Points to missing sources when information is incomplete

### Verification

Before committing documentation:
- ✅ Verify all PDFs are generated successfully
- ✅ Verify the docs do not claim features that are not in code
- ✅ Ensure "what works vs planned" is explicit
- ✅ Ensure diagrams render (Mermaid blocks compatible with md-to-pdf)

## File Locations

**Markdown Source**: `docs/exports/markdown/`
**PDF Output**: `docs/exports/pdfs/`
**Generator Script**: `scripts/generate_thandev_docs.py`
**PDF Export Script**: `scripts/export_docs_to_pdf.sh`

## Troubleshooting

### PDF Generation Fails

If PDF generation fails with "Failed to launch the browser process":

1. **Install system libraries** (see Prerequisites above)
2. **Alternative**: Use an online Markdown to PDF converter
3. **Alternative**: Use pandoc if installed:
   ```bash
   for md in docs/exports/markdown/*.md; do
     pandoc "$md" -o "${md%.md}.pdf"
   done
   ```

### Markdown Generation Fails

If the generator script fails:

1. **Check Python version**: Requires Python 3.11+
2. **Check file permissions**: Ensure script is executable (`chmod +x scripts/generate_thandev_docs.py`)
3. **Check repository structure**: Ensure you're running from repo root

## Maintenance

### When to Regenerate

Regenerate documentation when:
- New API endpoints are added
- Database models change
- New services are added
- Tool matrix changes
- Configuration options change

### Keeping Docs Current

The generator script scans the actual codebase, so documentation stays current as long as:
- Code structure follows conventions
- API routes use FastAPI decorators
- Models inherit from SQLAlchemy Base
- Config uses Pydantic Settings

## Notes

- Documentation is **read-only** - do not manually edit generated markdown files
- All changes should be made to the generator script or source code
- PDFs are generated from markdown, so regenerate both when updating

