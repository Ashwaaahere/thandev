# PDF Generation Instructions

The PDF export script (`export_docs_to_pdf.sh`) requires Chrome/Chromium and system libraries to work.

## Quick Fix

Run this command to install required dependencies, then run the export script:

```bash
sudo apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2

cd /home/ashwath/thandev/docs
./export_docs_to_pdf.sh
```

## Generated PDFs Location

After running the script successfully, all PDFs will be in:

```
/home/ashwath/thandev/docs/
```

Files generated:
- `THANDEV_ARCHITECTURE.pdf`
- `THANDEV_BACKEND.pdf`
- `THANDEV_BRAIN.pdf`
- `THANDEV_FRONTEND.pdf`
- `THANDEV_INFRA_AND_DEVOPS.pdf`
- `THANDEV_OVERVIEW.pdf`
- `THANDEV_RUNNER.pdf`
- `THANDEV_SECURITY_MODEL.pdf`

## Alternative Methods

If you can't install the system libraries, you can:

1. **Use an online converter**: Upload the Markdown files to a service like [Markdown to PDF](https://www.markdowntopdf.com/)

2. **Use pandoc** (if installed):
   ```bash
   for md in THANDEV_*.md; do
     pandoc "$md" -o "${md%.md}.pdf"
   done
   ```

3. **Use VS Code**: Install the "Markdown PDF" extension and export from the editor

