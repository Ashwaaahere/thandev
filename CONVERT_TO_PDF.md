# Converting Documentation to PDF

The comprehensive documentation is available in `COMPLETE_REPOSITORY_DOCUMENTATION.md`.

## Option 1: Using Pandoc (Recommended)

If you have pandoc installed:

```bash
pandoc COMPLETE_REPOSITORY_DOCUMENTATION.md -o THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  --toc \
  --toc-depth=3
```

## Option 2: Using Markdown-PDF (Node.js)

```bash
npm install -g markdown-pdf
markdown-pdf COMPLETE_REPOSITORY_DOCUMENTATION.md -o THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.pdf
```

## Option 3: Using Online Tools

1. Copy the markdown content
2. Use online converters like:
   - https://www.markdowntopdf.com/
   - https://dillinger.io/ (export as PDF)
   - https://stackedit.io/ (export as PDF)

## Option 4: Using Python (if reportlab is installed)

```bash
pip install reportlab
python3 generate_complete_pdf.py
```

## Option 5: Using VS Code

1. Install "Markdown PDF" extension in VS Code
2. Open `COMPLETE_REPOSITORY_DOCUMENTATION.md`
3. Right-click → "Markdown PDF: Export (pdf)"

## Option 6: Using Docker (if pandoc available)

```bash
docker run --rm -v "$PWD":/data pandoc/latex \
  COMPLETE_REPOSITORY_DOCUMENTATION.md \
  -o THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=1in \
  --toc
```

The markdown file is comprehensive and ready for conversion!



