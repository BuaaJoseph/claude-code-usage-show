"""Generate a macOS .icns icon for Claude Code Usage app.

Run on macOS: python3 scripts/create_icon.py
Requires: Pillow (pip install Pillow)
"""

import subprocess
import tempfile
from pathlib import Path

def create_icon():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow not installed. Install with: pip install Pillow")
        print("Generating placeholder icon instead...")
        create_placeholder_iconset()
        return

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    assets_dir = Path(__file__).parent.parent / "assets"
    iconset_dir = assets_dir / "AppIcon.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Rounded rect background
        margin = max(1, size // 16)
        radius = max(2, size // 5)
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=radius,
            fill=(74, 158, 255),
        )

        # Draw "CC" text
        font_size = max(8, size // 3)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        text = "CC"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (size - tw) // 2
        y = (size - th) // 2 - bbox[1]
        draw.text((x, y), text, fill=(255, 255, 255), font=font)

        # Save at 1x
        if size <= 512:
            img.save(iconset_dir / f"icon_{size}x{size}.png")
        # Save as 2x of the half-size
        half = size // 2
        if half in sizes and size >= 32:
            img.save(iconset_dir / f"icon_{half}x{half}@2x.png")

    # Convert iconset to icns using iconutil (macOS only)
    icns_path = assets_dir / "AppIcon.icns"
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            check=True,
        )
        print(f"Icon created: {icns_path}")
    except FileNotFoundError:
        print("iconutil not found (not on macOS). Iconset created at:", iconset_dir)
        print("Run on macOS to convert: iconutil -c icns assets/AppIcon.iconset -o assets/AppIcon.icns")


def create_placeholder_iconset():
    """Create minimal PNG icons without Pillow."""
    assets_dir = Path(__file__).parent.parent / "assets"
    iconset_dir = assets_dir / "AppIcon.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)
    print(f"Iconset directory created: {iconset_dir}")
    print("Add icon PNGs manually or install Pillow and re-run.")


if __name__ == "__main__":
    create_icon()
