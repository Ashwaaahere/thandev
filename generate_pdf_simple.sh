#!/bin/bash
# Simple PDF generation script using HTML intermediate format

echo "Converting markdown to HTML..."
pandoc COMPLETE_REPOSITORY_DOCUMENTATION.md \
  -o THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.html \
  --standalone \
  --toc \
  --toc-depth=3 \
  --css=https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css \
  --metadata title="Thandev Platform - Complete Repository Documentation"

if [ $? -eq 0 ]; then
    echo "✅ HTML file created: THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.html"
    echo ""
    echo "To convert HTML to PDF, you can:"
    echo ""
    echo "Option 1: Use Chrome/Chromium (recommended)"
    echo "  chromium-browser --headless --disable-gpu --print-to-pdf=THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.pdf THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.html"
    echo ""
    echo "Option 2: Use Firefox"
    echo "  firefox --headless --print-to-pdf=THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.pdf THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.html"
    echo ""
    echo "Option 3: Open HTML in browser and print to PDF"
    echo "  Open THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.html in your browser"
    echo "  Press Ctrl+P and select 'Save as PDF'"
    echo ""
    echo "Option 4: Install LaTeX and use pandoc directly"
    echo "  sudo apt-get install texlive-xetex"
    echo "  pandoc COMPLETE_REPOSITORY_DOCUMENTATION.md -o THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.pdf --pdf-engine=xelatex --toc"
else
    echo "❌ Failed to create HTML file"
    exit 1
fi



