# Favicon Information

## 📍 **Favicon Location**

Your favicon is located at:
- **SVG File:** `frontend/public/favicon.svg`
- **App Icon:** `frontend/app/icon.svg` (Next.js App Router icon)

Both files are identical SVG images.

---

## 🎨 **Favicon Design**

The favicon is a **32x32 pixel** SVG with:
- **Gradient:** Blue (#60A5FA) to Purple (#8B5CF6)
- **Shape:** Rounded rectangle (8px border radius)
- **Format:** SVG (scalable vector graphics)

---

## 🖼️ **Convert to PNG**

### **Option 1: Use the HTML Converter (Easiest)**

1. Open `favicon_converter.html` in your browser
2. Click the "Download as PNG" button
3. The PNG file will be downloaded

### **Option 2: Online Converter**

1. Go to: https://cloudconvert.com/svg-to-png
2. Upload `frontend/public/favicon.svg`
3. Set size to 512x512 (or desired size)
4. Download the PNG

### **Option 3: Command Line (if tools installed)**

```bash
# Using ImageMagick
convert -background none -resize 512x512 frontend/public/favicon.svg favicon.png

# Using Inkscape
inkscape frontend/public/favicon.svg --export-filename=favicon.png --export-width=512 --export-height=512

# Using rsvg-convert (librsvg)
rsvg-convert -w 512 -h 512 -o favicon.png frontend/public/favicon.svg
```

---

## 📁 **File Locations**

```
frontend/
├── public/
│   └── favicon.svg          ← Main favicon (used in browser)
└── app/
    └── icon.svg            ← Next.js App Router icon
```

---

## 💡 **Note**

SVG is already an image format and can be used directly in:
- HTML: `<img src="/favicon.svg">`
- CSS: `background-image: url('/favicon.svg')`
- Most modern applications

If you need PNG specifically (for older browsers or specific use cases), use one of the conversion methods above.

---

## 🎯 **Quick Access**

- **View SVG:** Open `frontend/public/favicon.svg` in any browser or image viewer
- **Convert to PNG:** Open `favicon_converter.html` in browser and download
