"""
Startup Session Qualification Modal for KRT Bookings Tracker.
Asks the technician whether to start a Pro Work Session, Resume an existing session, or Personal/Leisure Mode.
Aesthetic inspired by krtstudios.tv.
"""
import datetime
import tkinter as tk
from typing import Optional, Callable, Dict, Any
from agent.ui.theme import (
    BG_MAIN, BG_CARD, BG_CARD_HOVER, BORDER_COLOR, BORDER_FOCUS, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_MUTED, ACCENT_BLUE, ACCENT_GREEN, ACCENT_GREEN_HOVER,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    FONT_EYEBROW, apply_window_theme, center_window, get_krt_logo_tk
)
from agent.logger import logger

class StartupModal:
    """Startup dialog asking technician to qualify the session."""

    def __init__(
        self,
        parent: tk.Tk,
        user_name: str = "Technicien",
        resumable_session: Optional[Dict[str, Any]] = None,
    ):
        self.parent = parent
        self.user_name = user_name
        self.resumable_session = resumable_session
        self.choice: str = "resume" if resumable_session else "work"

        self.top = tk.Toplevel(self.parent)
        apply_window_theme(self.top, title="Qualification de session — KRT Tracker")
        self.top.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        height = 540 if self.resumable_session else 460
        center_window(self.top, width=560, height=height)

    def _build_ui(self):
        container = tk.Frame(self.top, bg=BG_MAIN, padx=28, pady=22)
        container.pack(fill=tk.BOTH, expand=True)

        # Header Badge / Eyebrow
        top_bar = tk.Frame(container, bg=BG_MAIN)
        top_bar.pack(fill=tk.X, pady=(0, 10))

        self.logo_img = get_krt_logo_tk(target_height=20)
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
            text="ACCUEIL TECHNICIEN",
            font=FONT_EYEBROW,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        ).pack(side=tk.RIGHT)

        tk.Label(
            container,
            text=f"👋 Bonjour {self.user_name}",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
        ).pack(anchor="w", pady=(2, 0))

        subtitle_text = "Une session de travail était déjà en cours aujourd'hui :" if self.resumable_session else "Comment souhaitez-vous qualifier cette session d'ordinateur ?"
        tk.Label(
            container,
            text=subtitle_text,
            font=FONT_BODY,
            fg=TEXT_SECONDARY,
            bg=BG_MAIN,
        ).pack(anchor="w", pady=(4, 0))

        # Action Cards Frame
        actions_frame = tk.Frame(container, bg=BG_MAIN)
        actions_frame.pack(fill=tk.BOTH, expand=True, pady=(14, 8))

        if self.resumable_session:
            # Extract start time and duration
            start_str = "--:--"
            duration_str = ""
            started_at = self.resumable_session.get("started_at")
            if started_at:
                try:
                    clean_str = started_at.replace("Z", "+00:00")
                    dt = datetime.datetime.fromisoformat(clean_str).astimezone()
                    start_str = dt.strftime("%H:%M")
                except Exception:
                    pass
            sec = self.resumable_session.get("duration_seconds", 0)
            if sec:
                h, m = divmod(sec // 60, 60)
                duration_str = f" (~{h}h{m:02d} enregistrées)" if h > 0 else f" (~{m} min enregistrées)"

            # Option 1: Resume Active Session (Primary Emerald)
            resume_btn = tk.Button(
                actions_frame,
                text=f"🔄  Reprendre la session de travail en cours\n     Démarrée à {start_str}{duration_str}",
                font=FONT_BODY_BOLD,
                bg=ACCENT_GREEN,
                fg="#FFFFFF",
                activebackground=ACCENT_GREEN_HOVER,
                activeforeground="#FFFFFF",
                relief=tk.FLAT,
                cursor="hand2",
                justify=tk.LEFT,
                padx=16,
                pady=10,
                command=self._select_resume,
            )
            resume_btn.pack(fill=tk.X, pady=(0, 8))

            # Option 2: Start NEW work session (Discards/closes prior session)
            new_work_btn = tk.Button(
                actions_frame,
                text="🆕  Démarrer une NOUVELLE session de travail\n     Clôturer la session précédente et repartir à zéro",
                font=FONT_BODY,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                activebackground=BG_CARD_HOVER,
                activeforeground=TEXT_PRIMARY,
                relief=tk.FLAT,
                highlightbackground=BORDER_COLOR,
                highlightthickness=1,
                cursor="hand2",
                justify=tk.LEFT,
                padx=16,
                pady=10,
                command=self._select_new_work,
            )
            new_work_btn.pack(fill=tk.X, pady=(0, 8))

        else:
            # Option 1: Standard Work Mode (Pro)
            work_btn = tk.Button(
                actions_frame,
                text="💼  Démarrer ma session de travail\n     Enclencher le compteur d'heures RH & la synchronisation",
                font=FONT_BODY_BOLD,
                bg=ACCENT_GREEN,
                fg="#FFFFFF",
                activebackground=ACCENT_GREEN_HOVER,
                activeforeground="#FFFFFF",
                relief=tk.FLAT,
                cursor="hand2",
                justify=tk.LEFT,
                padx=16,
                pady=12,
                command=self._select_work,
            )
            work_btn.pack(fill=tk.X, pady=(0, 10))

        # Personal / Leisure Mode
        personal_btn = tk.Button(
            actions_frame,
            text="☕  Mode Loisir / Perso\n     Utilisation personnelle du PC (compteurs RH en veille)",
            font=FONT_BODY,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_CARD_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            cursor="hand2",
            justify=tk.LEFT,
            padx=16,
            pady=10 if self.resumable_session else 12,
            command=self._select_personal,
        )
        personal_btn.pack(fill=tk.X)

        # Bottom Notice
        footer_label = tk.Label(
            container,
            text="🔒 Vous pouvez changer de mode ou mettre en pause à tout moment via la barre des tâches.",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
            wraplength=450,
            justify=tk.CENTER,
        )
        footer_label.pack(side=tk.BOTTOM, pady=(6, 0))

    def _select_resume(self):
        logger.info("User selected RESUME existing work session.")
        self.choice = "resume"
        self.top.destroy()

    def _select_new_work(self):
        logger.info("User selected NEW work session (closing existing).")
        self.choice = "new_work"
        self.top.destroy()

    def _select_work(self):
        logger.info("User selected WORK session.")
        self.choice = "work"
        self.top.destroy()

    def _select_personal(self):
        logger.info("User selected PERSONAL / LEISURE session.")
        self.choice = "personal"
        self.top.destroy()

    def _on_close(self):
        fallback = "resume" if self.resumable_session else "work"
        logger.info(f"Startup modal closed via X (defaulting to {fallback}).")
        self.choice = fallback
        self.top.destroy()

    def show_modal(self) -> str:
        self.top.deiconify()
        self.top.lift()
        self.top.attributes("-topmost", True)
        self.top.focus_force()
        self.parent.wait_window(self.top)
        return self.choice

