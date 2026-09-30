"""
Script to generate application icons (PNG and ICO) for KRT Bookings Tracker Agent.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_icons():
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []

    for w, h in sizes:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Rounded dark background
        radius = int(w * 0.2)
        draw.rounded_rectangle(
            [(0, 0), (w - 1, h - 1)],
            radius=radius,
            fill="#0F172A",
            outline="#3B82F6",
            width=max(1, int(w * 0.04)),
        )

        # Inner vibrant circle
        padding = int(w * 0.22)
        draw.ellipse(
            [(padding, padding), (w - padding, h - padding)],
            fill="#3B82F6",
        )

        # Inner dot (Emerald Green #10B981)
        dot_pad = int(w * 0.38)
        draw.ellipse(
            [(dot_pad, dot_pad), (w - dot_pad, h - dot_pad)],
            fill="#10B981",
        )

        images.append(img)

    # Save highest resolution PNG
    png_path = assets_dir / "app_icon.png"
    images[0].save(png_path, format="PNG")
    print(f"Generated PNG icon: {png_path}")

    # Save multi-size ICO
    ico_path = assets_dir / "app_icon.ico"
    images[0].save(ico_path, format="ICO", sizes=[(s[0], s[1]) for s in sizes])
    print(f"Generated ICO icon: {ico_path}")

if __name__ == "__main__":
    generate_icons()
