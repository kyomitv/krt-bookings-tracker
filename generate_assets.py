"""
Script to generate application icons (PNG and ICO) for KRT Bookings Tracker Agent
using the authentic KRT Studios brand identity.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

def generate_icons():
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    logo_src_path = assets_dir / "krt_logo_site.png"
    if not logo_src_path.exists():
        # Fallback if download hasn't happened yet
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://krtstudios.tv/podcast/assets/krt-logo.png",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            data = urllib.request.urlopen(req, timeout=10).read()
            logo_src_path.write_bytes(data)
        except Exception as e:
            print(f"[Assets] Warning: Could not download remote logo: {e}")

    # Load logo if available
    logo_img = None
    if logo_src_path.exists():
        try:
            logo_img = Image.open(logo_src_path).convert("RGBA")
        except Exception as e:
            print(f"[Assets] Error opening logo source: {e}")

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    images = []

    for w, h in sizes:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 1. Background squircle: Dark obsidian (#08070A) with subtle border (#26242B)
        radius = max(2, int(w * 0.22))
        draw.rounded_rectangle(
            [(0, 0), (w - 1, h - 1)],
            radius=radius,
            fill="#08070A",
            outline="#26242B",
            width=max(1, int(w * 0.035)),
        )

        # 2. Electric Blue accent pill / dot indicator in top-right or center
        if logo_img:
            # Fit logo nicely within inner bounding box
            pad = int(w * 0.18)
            target_w = w - (pad * 2)
            target_h = h - (pad * 2)
            
            # Preserve aspect ratio
            logo_w, logo_h = logo_img.size
            ratio = min(target_w / logo_w, target_h / logo_h)
            new_w = max(1, int(logo_w * ratio))
            new_h = max(1, int(logo_h * ratio))
            
            resized_logo = logo_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            pos_x = (w - new_w) // 2
            pos_y = (h - new_h) // 2
            img.paste(resized_logo, (pos_x, pos_y), resized_logo)
        else:
            # High-end typographic fallback if logo is missing
            draw.text((w // 2, h // 2), "KRT", fill="#F4F2ED", anchor="mm")

        # 3. Subtle bottom accent line in electric blue (#345CFF)
        if w >= 32:
            accent_margin = int(w * 0.28)
            accent_y = h - max(3, int(h * 0.09))
            accent_h = max(2, int(h * 0.04))
            draw.rounded_rectangle(
                [(accent_margin, accent_y), (w - accent_margin, accent_y + accent_h)],
                radius=max(1, accent_h // 2),
                fill="#345CFF",
            )

        images.append(img)

    # Save highest resolution PNG
    png_path = assets_dir / "app_icon.png"
    images[0].save(png_path, format="PNG")
    print(f"Generated PNG icon: {png_path}")

    # Save multi-size ICO for Windows
    ico_path = assets_dir / "app_icon.ico"
    images[0].save(ico_path, format="ICO", sizes=[(s[0], s[1]) for s in sizes])
    print(f"Generated ICO icon: {ico_path}")

if __name__ == "__main__":
    generate_icons()
