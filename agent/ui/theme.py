"""
Theme and UI constants for KRT Bookings Tracker Tkinter Interface.
"""

# Color Palette
BG_MAIN = "#0F172A"       # Deep Slate 900
BG_CARD = "#1E293B"       # Slate 800
BG_CARD_HOVER = "#273549" # Slate 750
BG_INPUT = "#0F172A"      # Slate 900
BORDER_COLOR = "#334155"  # Slate 700
BORDER_FOCUS = "#3B82F6"  # Blue 500

TEXT_PRIMARY = "#F8FAFC"   # Slate 50
TEXT_SECONDARY = "#94A3B8" # Slate 400
TEXT_MUTED = "#64748B"     # Slate 500

ACCENT_BLUE = "#3B82F6"
ACCENT_BLUE_HOVER = "#2563EB"
ACCENT_GREEN = "#10B981"
ACCENT_GREEN_HOVER = "#059669"
ACCENT_AMBER = "#F59E0B"
ACCENT_AMBER_HOVER = "#D97706"
ACCENT_RED = "#EF4444"
ACCENT_RED_HOVER = "#DC2626"
ACCENT_PURPLE = "#8B5CF6"

# Fonts
FONT_FAMILY = "Segoe UI" if "Segoe UI" else "Helvetica"
FONT_TITLE = (FONT_FAMILY, 18, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 12, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_BODY_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_TIMER = (FONT_FAMILY, 32, "bold")
FONT_BADGE = (FONT_FAMILY, 9, "bold")

def center_window(window, width: int, height: int):
    """Centers a tkinter window on screen."""
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
