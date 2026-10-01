"""
Connection Alert Modal for KRT Bookings Tracker.
Displays an alert when connection to Supabase / Database is lost and offers retry or restart options.
Aesthetic inspired by krtstudios.tv.
"""
import tkinter as tk
from typing import Optional, Callable
from agent.ui.theme import (
    BG_MAIN, BG_CARD, BG_CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_MUTED, ACCENT_AMBER, ACCENT_AMBER_HOVER, ACCENT_BLUE,
    ACCENT_BLUE_HOVER, ACCENT_GREEN, FONT_TITLE, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_EYEBROW, apply_window_theme, center_window, get_krt_logo_tk
)
from agent.logger import logger


class ConnectionAlertModal:
    """Modal alerting user of database connection loss with options to retry or restart."""

    def __init__(
        self,
        parent: tk.Tk,
        on_restart: Optional[Callable[[], None]] = None,
        on_retry: Optional[Callable[[], None]] = None,
        on_dismiss: Optional[Callable[[], None]] = None,
    ):
        self.parent = parent
        self.on_restart = on_restart
        self.on_retry = on_retry
        self.on_dismiss = on_dismiss

        self.top = tk.Toplevel(self.parent)
        apply_window_theme(self.top, title="Alerte Connexion — KRT Tracker")
        self.top.protocol("WM_DELETE_WINDOW", self._dismiss)

        self._status_label: Optional[tk.Label] = None
        self._build_ui()
        center_window(self.top, width=540, height=410)

    def _build_ui(self):
        container = tk.Frame(self.top, bg=BG_MAIN, padx=26, pady=24)
        container.pack(fill=tk.BOTH, expand=True)

        # Header Top Bar
        top_bar = tk.Frame(container, bg=BG_MAIN)
        top_bar.pack(fill=tk.X, pady=(0, 10))

        self.logo_img = get_krt_logo_tk(target_height=18)
        if self.logo_img:
            logo_label = tk.Label(top_bar, image=self.logo_img, bg=BG_MAIN)
            logo_label.pack(side=tk.LEFT)
        else:
            tk.Label(
                top_bar,
                text="KRT STUDIOS",
                font=FONT_EYEBROW,
                fg=ACCENT_BLUE,
                bg=BG_MAIN,
            ).pack(side=tk.LEFT)

        tk.Label(
            top_bar,
            text="⚠️ ALERTE SYNCHRONISATION",
            font=FONT_EYEBROW,
            fg=ACCENT_AMBER,
            bg=BG_MAIN,
        ).pack(side=tk.RIGHT)

        # Title
        tk.Label(
            container,
            text="Connexion à la base de données perdue",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            container,
            text="L'application ne parvient plus à communiquer avec les serveurs Supabase. Une reconnexion automatique est tentée en continu en arrière-plan.",
            font=FONT_BODY,
            fg=TEXT_SECONDARY,
            bg=BG_MAIN,
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(6, 12))

        # Warning Card
        card = tk.Frame(container, bg=BG_CARD, padx=16, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            card,
            text="ÉTAT DU SUIVI",
            font=FONT_EYEBROW,
            fg=TEXT_MUTED,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            card,
            text="ℹ️ Vos heures restent enregistrées localement sur ce PC et seront synchronisées dès que la connexion sera rétablie.",
            font=FONT_SMALL,
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            wraplength=440,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 0))

        # Status feedback label
        self._status_label = tk.Label(
            container,
            text="",
            font=FONT_SMALL,
            fg=ACCENT_AMBER,
            bg=BG_MAIN,
            anchor="w"
        )
        self._status_label.pack(fill=tk.X, pady=(0, 10))

        # Buttons Frame
        btn_frame = tk.Frame(container, bg=BG_MAIN)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        dismiss_btn = tk.Button(
            btn_frame,
            text="Continuer hors-ligne",
            font=FONT_BODY,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_CARD_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            cursor="hand2",
            padx=12,
            pady=7,
            command=self._dismiss,
        )
        dismiss_btn.pack(side=tk.LEFT)

        restart_btn = tk.Button(
            btn_frame,
            text="⚡ Redémarrer",
            font=FONT_BODY,
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            activebackground=BG_CARD_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            cursor="hand2",
            padx=12,
            pady=7,
            command=self._restart,
        )
        restart_btn.pack(side=tk.RIGHT, padx=(8, 0))

        retry_btn = tk.Button(
            btn_frame,
            text="🔄  Réessayer",
            font=FONT_BODY_BOLD,
            bg=ACCENT_BLUE,
            fg="#FFFFFF",
            activebackground=ACCENT_BLUE_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=7,
            command=self._retry,
        )
        retry_btn.pack(side=tk.RIGHT)

    def set_status_message(self, text: str, color: str = ACCENT_AMBER):
        if self._status_label and self.top.winfo_exists():
            self._status_label.config(text=text, fg=color)

    def _retry(self):
        logger.info("User clicked retry from connection alert modal.")
        self.set_status_message("Tentative de reconnexion en cours...", ACCENT_AMBER)
        if self.on_retry:
            self.on_retry()

    def _restart(self):
        logger.info("User clicked restart from connection alert modal.")
        self.close()
        if self.on_restart:
            self.on_restart()

    def _dismiss(self):
        logger.info("User dismissed connection alert modal.")
        self.close()
        if self.on_dismiss:
            self.on_dismiss()

    def close(self):
        """Safely closes the modal window."""
        try:
            if self.top.winfo_exists():
                self.top.destroy()
        except Exception:
            pass

    def show(self):
        """Displays or brings the modal to front."""
        try:
            self.top.deiconify()
            self.top.lift()
            self.top.attributes("-topmost", True)
            self.top.focus_force()
        except Exception:
            pass
