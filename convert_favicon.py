#!/usr/bin/env python3
"""
Convert favicon.svg to PNG image
"""
import subprocess
import sys
import os

def convert_svg_to_png_simple():
    """Create a simple PNG from the SVG using available tools"""
    svg_path = "frontend/public/favicon.svg"
    output_path = "favicon.png"
    
    if not os.path.exists(svg_path):
        print(f"Error: {svg_path} not found")
        return False
    
    # Try using rsvg-convert (librsvg)
    try:
        result = subprocess.run(
            ["rsvg-convert", "-w", "512", "-h", "512", "-o", output_path, svg_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"✅ Created {output_path} using rsvg-convert")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Try using inkscape
    try:
        result = subprocess.run(
            ["inkscape", svg_path, "--export-filename", output_path, "--export-width", "512", "--export-height", "512"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"✅ Created {output_path} using inkscape")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Try using ImageMagick
    try:
        result = subprocess.run(
            ["convert", "-background", "none", "-resize", "512x512", svg_path, output_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"✅ Created {output_path} using ImageMagick")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print("❌ No SVG to PNG converter found. Please install one of:")
    print("   - librsvg (rsvg-convert)")
    print("   - inkscape")
    print("   - ImageMagick (convert)")
    print("\nOr use an online converter: https://cloudconvert.com/svg-to-png")
    return False

if __name__ == "__main__":
    convert_svg_to_png_simple()
