"""
Login View for KRT Bookings Tracker.
Modal for first launch authentication and pairing.
Aesthetic inspired by krtstudios.tv.
"""
import tkinter as tk
from typing import Callable, Optional, Dict, Any
from agent.ui.theme import (
    BG_MAIN, BG_CARD, BG_INPUT, BORDER_COLOR, BORDER_FOCUS, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_MUTED, ACCENT_BLUE, ACCENT_BLUE_HOVER,
    ACCENT_RED, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_EYEBROW, apply_window_theme, center_window, get_krt_logo_tk
)
from agent.autostart import AutostartManager
from agent.logger import logger

class LoginWindow:
    """Authentication window displayed when credentials are not found."""

    def __init__(self, parent: tk.Tk, client=None, on_success: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.parent = parent
        self.client = client
        self.on_success = on_success
        self.auth_data: Optional[Dict[str, Any]] = None

        self.top = tk.Toplevel(self.parent)
        apply_window_theme(self.top, title="Connexion — KRT Bookings Tracker")
        self.top.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        center_window(self.top, width=500, height=580)

    def set_client(self, client):
        self.client = client

    def _build_ui(self):
        container = tk.Frame(self.top, bg=BG_MAIN, padx=32, pady=28)
        container.pack(fill=tk.BOTH, expand=True)

        # Header Logo / Eyebrow
        self.logo_img = get_krt_logo_tk(target_height=26)
        if self.logo_img:
            logo_label = tk.Label(container, image=self.logo_img, bg=BG_MAIN)
            logo_label.pack(anchor="center", pady=(0, 6))
        else:
            badge_frame = tk.Frame(container, bg=BG_CARD, padx=12, pady=4, highlightbackground=BORDER_COLOR, highlightthickness=1)
            badge_frame.pack(anchor="center", pady=(0, 8))
            tk.Label(
                badge_frame,
                text="KRT STUDIOS",
                font=FONT_EYEBROW,
                fg=ACCENT_BLUE,
                bg=BG_CARD,
            ).pack()

        # Title
        tk.Label(
            container,
            text="Espace Technicien",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
        ).pack(anchor="center", pady=(4, 0))

        tk.Label(
            container,
            text="Connectez votre agent de suivi du temps de travail",
            font=FONT_SMALL,
            fg=TEXT_SECONDARY,
            bg=BG_MAIN,
        ).pack(anchor="center", pady=(4, 18))

        # Form Card
        card = tk.Frame(container, bg=BG_CARD, padx=22, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        # Email Field
        tk.Label(card, text="Email Professionnel", font=FONT_BODY_BOLD, fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w")
        self.email_entry = tk.Entry(
            card,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightcolor=BORDER_FOCUS,
            highlightthickness=1,
        )
        self.email_entry.pack(fill=tk.X, pady=(6, 14), ipady=6)
        self.email_entry.focus_set()

        # Password Field
        tk.Label(card, text="Mot de passe", font=FONT_BODY_BOLD, fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w")
        self.password_entry = tk.Entry(
            card,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            show="•",
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightcolor=BORDER_FOCUS,
            highlightthickness=1,
        )
        self.password_entry.pack(fill=tk.X, pady=(6, 14), ipady=6)

        # Autostart checkbox
        self.autostart_var = tk.BooleanVar(value=True)
        autostart_cb = tk.Checkbutton(
            card,
            text="Lancer automatiquement au démarrage du PC",
            variable=self.autostart_var,
            font=FONT_SMALL,
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_INPUT,
            relief=tk.FLAT,
        )
        autostart_cb.pack(anchor="w", pady=(0, 10))

        # Error Label
        self.error_label = tk.Label(card, text="", font=FONT_SMALL, fg=ACCENT_RED, bg=BG_CARD, wraplength=340)
        self.error_label.pack(fill=tk.X, pady=(0, 6))

        # Submit Button
        self.submit_btn = tk.Button(
            card,
            text="Se connecter",
            font=FONT_BODY_BOLD,
            bg=ACCENT_BLUE,
            fg="#FFFFFF",
            activebackground=ACCENT_BLUE_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._handle_login,
        )
        self.submit_btn.pack(fill=tk.X, ipady=8, pady=(4, 0))

        # Enter key binding
        self.top.bind("<Return>", lambda e: self._handle_login())

    def _handle_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()

        if not email or not password:
            self.error_label.config(text="Veuillez renseigner votre email et mot de passe.")
            return

        self.submit_btn.config(state=tk.DISABLED, text="Connexion en cours...")
        self.error_label.config(text="")
        self.top.update()

        if not self.client:
            from agent.supabase_client import SupabaseClient
            self.client = SupabaseClient()

        success, error_msg, session_data = self.client.sign_in_with_password(email, password)

        if success and session_data:
            logger.info("Login succeeded in UI, saving credentials and closing login modal.")
            if self.autostart_var.get():
                AutostartManager.enable()

            self.auth_data = session_data
            if self.on_success:
                self.on_success(session_data)
            self.top.destroy()
        else:
            self.submit_btn.config(state=tk.NORMAL, text="Se connecter")
            self.error_label.config(text=error_msg or "Échec de connexion.")

    def _on_close(self):
        logger.info("Login window closed by user.")
        self.auth_data = None
        self.top.destroy()

    def show_modal(self) -> Optional[Dict[str, Any]]:
        self.top.deiconify()
        self.top.lift()
        self.top.focus_force()
        self.parent.wait_window(self.top)
        return self.auth_data

