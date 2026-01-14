#!/usr/bin/env node
/**
 * Convert favicon.svg to PNG using Node.js
 * This script creates a PNG version of the favicon
 */

const fs = require('fs');
const path = require('path');

const svgPath = path.join(__dirname, 'frontend', 'public', 'favicon.svg');
const outputPath = path.join(__dirname, 'favicon.png');

// Read the SVG file
const svgContent = fs.readFileSync(svgPath, 'utf8');

// Create an HTML file that will render the SVG and allow saving as PNG
const htmlContent = `<!DOCTYPE html>
<html>
<head>
    <title>Favicon Converter</title>
    <style>
        body {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            font-family: Arial, sans-serif;
        }
        .container {
            text-align: center;
        }
        canvas {
            border: 1px solid #ccc;
            margin: 20px;
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
            cursor: pointer;
            background: #60A5FA;
            color: white;
            border: none;
            border-radius: 5px;
        }
        button:hover {
            background: #8B5CF6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Favicon Image</h1>
        <canvas id="canvas" width="512" height="512"></canvas>
        <br>
        <button onclick="downloadPNG()">Download as PNG</button>
    </div>
    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        
        img.onload = function() {
            ctx.drawImage(img, 0, 0, 512, 512);
        };
        
        img.src = 'data:image/svg+xml;base64,' + btoa(\`${svgContent.replace(/`/g, '\\`')}\`);
        
        function downloadPNG() {
            const link = document.createElement('a');
            link.download = 'favicon.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        }
    </script>
</body>
</html>`;

// Write the HTML file
const htmlPath = path.join(__dirname, 'favicon_converter.html');
fs.writeFileSync(htmlPath, htmlContent);

console.log('✅ Created favicon_converter.html');
console.log('');
console.log('To get the PNG image:');
console.log('1. Open favicon_converter.html in your browser');
console.log('2. Click "Download as PNG" button');
console.log('3. The favicon.png file will be downloaded');
console.log('');
console.log('Or you can view the SVG directly at:');
console.log(`   ${svgPath}`);
