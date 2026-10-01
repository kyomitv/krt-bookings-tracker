"""
System Tray (Systray) Manager for KRT Bookings Tracker Agent.
Uses pystray + Pillow for cross-platform taskbar icon and context menu.
"""
import threading
import webbrowser
from typing import Optional
import pystray
from PIL import Image, ImageDraw
from agent.config import WEB_SCHEDULES_URL
from agent.logger import logger

class SystrayManager:
    """Manages the background system tray icon, tooltips, and context menu."""

    def __init__(self, agent):
        self.agent = agent
        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    def _create_icon_image(self, color_hex: str = "#10B981") -> Image.Image:
        """Generates a dynamic high-res rounded icon image with KRT branding and state indicator."""
        width = 64
        height = 64
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Background rounded box (Dark Obsidian #08070A)
        draw.rounded_rectangle(
            [(2, 2), (width - 3, height - 3)],
            radius=14,
            fill="#08070A",
            outline="#26242C",
            width=2,
        )

        # Load KRT logo if available
        from agent.ui.theme import get_asset_path
        logo_path = get_asset_path("krt_logo_site.png")
        if not logo_path.exists():
            logo_path = get_asset_path("app_icon.png")

        if logo_path.exists():
            try:
                logo_img = Image.open(logo_path).convert("RGBA")
                target_w = 42
                target_h = 42
                orig_w, orig_h = logo_img.size
                ratio = min(target_w / orig_w, target_h / orig_h)
                new_w = max(1, int(orig_w * ratio))
                new_h = max(1, int(orig_h * ratio))
                resized = logo_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                pos_x = (width - new_w) // 2
                pos_y = (height - new_h) // 2 - 2
                image.paste(resized, (pos_x, pos_y), resized)
            except Exception:
                pass
        else:
            # Fallback text
            draw.text((width // 2, height // 2 - 2), "KRT", fill="#F4F2ED", anchor="mm")

        # Status badge indicator (bottom right circle with dark outline)
        dot_r = 8
        dot_cx = width - 12
        dot_cy = height - 12
        draw.ellipse(
            [(dot_cx - dot_r - 2, dot_cy - dot_r - 2), (dot_cx + dot_r + 2, dot_cy + dot_r + 2)],
            fill="#08070A"
        )
        draw.ellipse(
            [(dot_cx - dot_r, dot_cy - dot_r), (dot_cx + dot_r, dot_cy + dot_r)],
            fill=color_hex
        )

        return image

    def _get_status_color(self) -> str:
        status = getattr(self.agent, "status", "idle")
        if status == "active":
            return "#10B981"  # Emerald Green
        elif status == "paused":
            return "#F59E0B"  # Amber
        elif status == "personal":
            return "#345CFF"  # Cobalt Blue
        return "#706E76"      # Muted Gray

    def update_icon(self):
        """Refreshes the tray icon appearance based on current agent state."""
        if self.icon and self._is_running:
            try:
                color = self._get_status_color()
                self.icon.icon = self._create_icon_image(color)
                user_name = self.agent.get_user_display_name()
                status_text = self.agent.get_status_display_text()
                self.icon.title = f"KRT Tracker ({user_name}) - {status_text}"
            except Exception as e:
                logger.warning(f"Error updating tray icon: {e}")

    def _build_menu(self) -> pystray.Menu:
        user_name = self.agent.get_user_display_name()

        def on_open_dashboard(icon, item):
            logger.info("Tray clicked: Open Dashboard")
            self.agent.root.after(0, self.agent.show_dashboard)

        def on_open_web_schedule(icon, item):
            logger.info(f"Tray clicked: Open Web Schedule ({WEB_SCHEDULES_URL})")
            try:
                webbrowser.open(WEB_SCHEDULES_URL)
            except Exception as e:
                logger.error(f"Error opening web schedule URL: {e}")

        def on_toggle_pause(icon, item):
            logger.info("Tray clicked: Toggle Pause")
            if self.agent.status == "active":
                self.agent.root.after(0, self.agent.pause_work)
            elif self.agent.status == "paused":
                self.agent.root.after(0, self.agent.resume_work)
            elif self.agent.status == "personal":
                self.agent.root.after(0, self.agent.start_work)

        def on_toggle_mode(icon, item):
            logger.info("Tray clicked: Toggle Mode")
            if self.agent.status == "personal":
                self.agent.root.after(0, self.agent.start_work)
            else:
                self.agent.root.after(0, self.agent.start_personal_mode)

        def on_check_update(icon, item):
            logger.info("Tray clicked: Check for updates")
            self.agent.root.after(0, lambda: self.agent.check_updates(manual=True))

        def on_quit(icon, item):
            logger.info("Tray clicked: Quit")
            self.agent.root.after(0, self.agent.prompt_end_work)

        def get_pause_label(item):
            if self.agent.status == "paused":
                return "▶️  Reprendre le travail"
            return "⏸️  Mettre en pause"

        def get_mode_label(item):
            if self.agent.status == "personal":
                return "💼  Passer en mode pro (Travail)"
            return "☕  Passer en mode loisir / perso"

        menu_items = [
            pystray.MenuItem(f"👤 KRT Tracker : {user_name}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⏱️  Suivi de la journée (Dashboard)", on_open_dashboard, default=True),
            pystray.MenuItem("📅  Gérer mes horaires (Web)", on_open_web_schedule),
            pystray.MenuItem(get_pause_label, on_toggle_pause),
            pystray.MenuItem(get_mode_label, on_toggle_mode),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🔄  Vérifier les mises à jour...", on_check_update),
            pystray.MenuItem("⏹️  Terminer la journée & Quitter", on_quit),
        ]

        return pystray.Menu(*menu_items)

    def start(self):
        """Starts the system tray icon in a dedicated background thread."""
        logger.info("Starting systray icon thread...")
        image = self._create_icon_image(self._get_status_color())
        menu = self._build_menu()
        self.icon = pystray.Icon(
            "krt_bookings_tracker",
            image,
            "KRT Bookings Tracker",
            menu,
        )

        def run_tray():
            try:
                self._is_running = True
                logger.info("Systray event loop running.")
                self.icon.run()
            except Exception as e:
                logger.error(f"Systray icon crashed: {e}")
            finally:
                self._is_running = False

        self._thread = threading.Thread(target=run_tray, daemon=True, name="SystrayThread")
        self._thread.start()

    def stop(self):
        """Stops and removes the system tray icon."""
        logger.info("Stopping systray icon...")
        self._is_running = False
        if self.icon:
            try:
                self.icon.stop()
            except Exception as e:
                logger.warning(f"Error stopping systray icon: {e}")
