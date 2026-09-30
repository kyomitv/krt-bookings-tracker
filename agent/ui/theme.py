"""
Theme and UI constants for KRT Bookings Tracker Tkinter Interface.
Inspired by the modern, premium aesthetic of krtstudios.tv.
"""
import sys
import tkinter as tk
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageTk

# ==================== ART DIRECTION / PALETTE (krtstudios.tv) ====================
# Deep obsidian background and graphite surfaces
BG_MAIN = "#08070A"         # Ultra-deep obsidian matte black
BG_CARD = "#121115"         # Surface graphite card
BG_CARD_HOVER = "#1A1920"   # Card hover highlight
BG_CARD_ACTIVE = "#22202A"  # Card active/pressed
BG_INPUT = "#16151B"        # Sleek dark form input background

# Subtle borders and dividers
BORDER_COLOR = "#26242C"    # Crisp subtle card & divider border
BORDER_SUBTLE = "#1C1A22"   # Fainter separator
BORDER_HOVER = "#3D3A46"    # Border hover
BORDER_FOCUS = "#345CFF"    # Focus electric blue ring

# Refined typography colors
TEXT_PRIMARY = "#F4F2ED"     # Warm chalk / paper white
TEXT_SECONDARY = "#B1AFB5"   # Muted silver gray
TEXT_MUTED = "#706E76"       # Dark muted gray for metadata / hints
TEXT_INVERTED = "#08070A"    # High contrast text on white/light elements
PAPER = "#F1F0E9"            # High-contrast light paper badge

# Accent colors
ACCENT_BLUE = "#345CFF"        # Signature KRT Electric Cobalt Blue
ACCENT_BLUE_HOVER = "#2347DF"  # Cobalt hover
ACCENT_BLUE_LIGHT = "#9BADFF"  # Soft blue focus accent
ACCENT_GREEN = "#10B981"       # Vibrant Emerald for Active session
ACCENT_GREEN_HOVER = "#059669"
ACCENT_AMBER = "#F59E0B"       # Warm Amber for Paused state
ACCENT_AMBER_HOVER = "#D97706"
ACCENT_RED = "#E11D48"         # Crimson / Rose Red for Stop & Quit
ACCENT_RED_HOVER = "#BE123C"
ACCENT_PURPLE = "#8B5CF6"

# Fonts
FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"
FONT_TITLE = (FONT_FAMILY, 20, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 15, "bold")
FONT_BODY = (FONT_FAMILY, 13)
FONT_BODY_BOLD = (FONT_FAMILY, 13, "bold")
FONT_SMALL = (FONT_FAMILY, 12)
FONT_EYEBROW = (FONT_FAMILY, 11, "bold")
FONT_TIMER = (FONT_FAMILY, 46, "bold")
FONT_BADGE = (FONT_FAMILY, 12, "bold")

# Global icon cache to prevent garbage collection in Tkinter
_ICON_PHOTO_CACHE = {}
_LOGO_PHOTO_CACHE = {}


def get_asset_path(filename: str) -> Path:
    """Returns absolute path to an asset, handling both dev and PyInstaller frozen runtime."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS) / "assets"
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent / "assets"
    return base_dir / filename


def apply_windows_app_id():
    """Sets explicit AppUserModelID and DPI awareness on Windows to ensure crisp rendering and taskbar grouping."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("krt.studios.bookings.tracker")
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def get_app_icon_photo() -> Optional[ImageTk.PhotoImage]:
    """Returns the Tkinter-compatible PhotoImage of the application icon."""
    global _ICON_PHOTO_CACHE
    if "app_icon" in _ICON_PHOTO_CACHE:
        return _ICON_PHOTO_CACHE["app_icon"]

    icon_png = get_asset_path("app_icon.png")
    if icon_png.exists():
        try:
            pil_img = Image.open(icon_png).convert("RGBA")
            tk_img = ImageTk.PhotoImage(pil_img)
            _ICON_PHOTO_CACHE["app_icon"] = tk_img
            return tk_img
        except Exception:
            pass
    return None


def get_krt_logo_tk(target_height: int = 24) -> Optional[ImageTk.PhotoImage]:
    """Returns the authentic KRT Studios logo resized to given height with preserved aspect ratio."""
    global _LOGO_PHOTO_CACHE
    key = f"logo_{target_height}"
    if key in _LOGO_PHOTO_CACHE:
        return _LOGO_PHOTO_CACHE[key]

    # Try official logo site asset first, then app icon
    logo_path = get_asset_path("krt_logo_site.png")
    if not logo_path.exists():
        logo_path = get_asset_path("app_icon.png")

    if logo_path.exists():
        try:
            pil_img = Image.open(logo_path).convert("RGBA")
            orig_w, orig_h = pil_img.size
            ratio = target_height / orig_h
            target_width = max(1, int(orig_w * ratio))
            resized = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(resized)
            _LOGO_PHOTO_CACHE[key] = tk_img
            return tk_img
        except Exception:
            pass
    return None


def center_window(window: tk.Toplevel | tk.Tk, width: Optional[int] = None, height: Optional[int] = None):
    """Centers a tkinter window on screen, ensuring it fits its content without cropping."""
    window.update_idletasks()
    req_w = window.winfo_reqwidth()
    req_h = window.winfo_reqheight()

    final_w = max(width or 0, req_w)
    final_h = max(height or 0, req_h)

    # Extra margin if calculated from widgets
    if height is None or final_h > height:
        final_h += 10
    if width is None or final_w > width:
        final_w += 10

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width // 2) - (final_w // 2))
    y = max(0, (screen_height // 2) - (final_h // 2))
    window.geometry(f"{final_w}x{final_h}+{x}+{y}")


def apply_window_theme(
    window: tk.Toplevel | tk.Tk,
    title: str = "KRT Bookings Tracker",
    width: Optional[int] = None,
    height: Optional[int] = None,
    resizable: bool = False,
):
    """
    Applies consistent KRT Studios theme, custom app icon, background color,
    and centered geometry to any Tk or Toplevel window.
    """
    apply_windows_app_id()

    window.title(title)
    window.configure(bg=BG_MAIN)
    window.resizable(resizable, resizable)

    # Apply application icon (both iconphoto and iconbitmap for maximum Windows/Tkinter compatibility)
    try:
        ico_path = get_asset_path("app_icon.ico")
        if ico_path.exists() and sys.platform == "win32":
            window.iconbitmap(str(ico_path))
    except Exception:
        pass

    try:
        photo = get_app_icon_photo()
        if photo:
            window.iconphoto(True, photo)
    except Exception:
        pass

    if width and height:
        center_window(window, width, height)


