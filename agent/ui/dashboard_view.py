"""
Live Tracking Dashboard Window for KRT Bookings Tracker.
Displays real-time work session timer, status badge, heartbeats, and control actions.
Aesthetic inspired by krtstudios.tv.
"""
import tkinter as tk
from typing import Optional
from agent.ui.theme import (
    BG_MAIN, BG_CARD, BG_CARD_HOVER, BG_INPUT, BORDER_COLOR, BORDER_FOCUS,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT_BLUE, ACCENT_BLUE_HOVER,
    ACCENT_GREEN, ACCENT_GREEN_HOVER, ACCENT_AMBER, ACCENT_AMBER_HOVER,
    ACCENT_RED, ACCENT_RED_HOVER, FONT_TITLE, FONT_SUBTITLE, FONT_BODY,
    FONT_BODY_BOLD, FONT_SMALL, FONT_EYEBROW, FONT_TIMER, FONT_BADGE,
    FONT_FAMILY, apply_window_theme, center_window, get_krt_logo_tk
)
from agent.logger import logger

class DashboardWindow:
    """Live dashboard window for technician time tracking."""

    def __init__(self, agent, parent: tk.Tk):
        self.agent = agent
        self.parent = parent

        self.top = tk.Toplevel(self.parent)
        apply_window_theme(self.top, title="KRT Tracker — Suivi de la journée", resizable=True)

        # Handle close button: minimize to systray
        self.top.protocol("WM_DELETE_WINDOW", self.hide)

        self._build_ui()
        center_window(self.top, width=540, height=720)
        self.top.minsize(500, max(660, self.top.winfo_reqheight()))
        self.top.bind("<Configure>", self._on_window_resize)
        self._is_visible = True
        self._update_loop()

    def _build_ui(self):
        self.container = tk.Frame(self.top, bg=BG_MAIN, padx=22, pady=16)
        self.container.pack(fill=tk.BOTH, expand=True)

        # --- 1. Footer Frame (Docked at bottom) ---
        footer_frame = tk.Frame(self.container, bg=BG_MAIN)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 4))

        from agent.config import APP_VERSION_DISPLAY
        version_label = tk.Label(
            footer_frame,
            text=f"{APP_VERSION_DISPLAY} • krtstudios.tv",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        )
        version_label.pack(side=tk.LEFT)

        check_update_btn = tk.Button(
            footer_frame,
            text="🔄 Vérifier MàJ",
            font=FONT_SMALL,
            bg=BG_MAIN,
            fg=ACCENT_BLUE,
            activebackground=BG_MAIN,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=lambda: self.agent.check_updates(manual=True),
        )
        check_update_btn.pack(side=tk.RIGHT)

        # --- 2. Action Buttons Frame (Docked above footer) ---
        actions_frame = tk.Frame(self.container, bg=BG_MAIN)
        actions_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 8))

        self.pause_resume_btn = tk.Button(
            actions_frame,
            text="⏸️  Mettre en pause",
            font=FONT_BODY_BOLD,
            bg=ACCENT_AMBER,
            fg="#FFFFFF",
            activebackground=ACCENT_AMBER_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._toggle_pause,
        )
        self.pause_resume_btn.pack(fill=tk.X, ipady=5, pady=(0, 6))

        self.end_day_btn = tk.Button(
            actions_frame,
            text="⏹️  Terminer la journée de travail",
            font=FONT_BODY_BOLD,
            bg=ACCENT_RED,
            fg="#FFFFFF",
            activebackground=ACCENT_RED_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._confirm_end_day,
        )
        self.end_day_btn.pack(fill=tk.X, ipady=5, pady=(0, 6))

        # Minimize to Tray button
        minimize_btn = tk.Button(
            actions_frame,
            text="Réduire dans la barre des tâches",
            font=FONT_SMALL,
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            activebackground=BG_CARD_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            cursor="hand2",
            command=self.hide,
        )
        minimize_btn.pack(fill=tk.X, ipady=4)

        # --- 3. Live Metrics Grid (Docked above actions) ---
        metrics_frame = tk.Frame(self.container, bg=BG_MAIN)
        metrics_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))

        # Metric 1: Total Today
        m1 = tk.Frame(metrics_frame, bg=BG_CARD, padx=12, pady=8, highlightbackground=BORDER_COLOR, highlightthickness=1)
        m1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        tk.Label(m1, text="TOTAL AUJOURD'HUI", font=FONT_EYEBROW, fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
        self.today_total_label = tk.Label(m1, text="00h 00m", font=FONT_BODY_BOLD, fg=TEXT_PRIMARY, bg=BG_CARD)
        self.today_total_label.pack(anchor="w", pady=(2, 0))

        # Metric 2: Heartbeat status
        m2 = tk.Frame(metrics_frame, bg=BG_CARD, padx=12, pady=8, highlightbackground=BORDER_COLOR, highlightthickness=1)
        m2.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        tk.Label(m2, text="SYNCHRONISATION", font=FONT_EYEBROW, fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
        self.heartbeat_label = tk.Label(m2, text="Connecté (1m)", font=FONT_BODY_BOLD, fg=ACCENT_GREEN, bg=BG_CARD)
        self.heartbeat_label.pack(anchor="w", pady=(2, 0))

        # --- 4. Top Brand Bar (Docked at top) ---
        top_bar = tk.Frame(self.container, bg=BG_MAIN)
        top_bar.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        self.logo_img = get_krt_logo_tk(target_height=20)
        if self.logo_img:
            logo_label = tk.Label(top_bar, image=self.logo_img, bg=BG_MAIN)
            logo_label.pack(side=tk.LEFT)
        else:
            tk.Label(
                top_bar,
                text="KRT STUDIOS",
                font=FONT_EYEBROW,
                fg=TEXT_PRIMARY,
                bg=BG_MAIN,
            ).pack(side=tk.LEFT)

        location_badge = tk.Label(
            top_bar,
            text="ORSAY PARIS • TRACKER AGENT",
            font=FONT_EYEBROW,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        )
        location_badge.pack(side=tk.RIGHT)

        # --- 5. User Profile Card (Docked below top bar) ---
        user_profile = self.agent.get_profile_info()
        full_name = f"{user_profile.get('first_name', '')} {user_profile.get('last_name', '')}".strip() or user_profile.get("email", "Technicien")
        role = user_profile.get("role", "Technicien").capitalize()

        header_frame = tk.Frame(self.container, bg=BG_CARD, padx=12, pady=8, highlightbackground=BORDER_COLOR, highlightthickness=1)
        header_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        # Avatar initial circle
        initials = (full_name[0] if full_name else "T").upper()
        avatar_frame = tk.Frame(header_frame, bg=ACCENT_BLUE, width=32, height=32)
        avatar_frame.pack(side=tk.LEFT, padx=(0, 10))
        avatar_frame.pack_propagate(False)
        tk.Label(avatar_frame, text=initials, font=FONT_BODY_BOLD, fg="#FFFFFF", bg=ACCENT_BLUE).place(relx=0.5, rely=0.5, anchor="center")

        user_info_frame = tk.Frame(header_frame, bg=BG_CARD)
        user_info_frame.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(user_info_frame, text=full_name, font=FONT_BODY_BOLD, fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor="w")
        tk.Label(user_info_frame, text=f"{role} • Équipe Technique KRT", font=FONT_SMALL, fg=TEXT_SECONDARY, bg=BG_CARD).pack(anchor="w")

        # --- 6. Main Live Timer Card (Expands dynamically to fill central space) ---
        timer_card = tk.Frame(self.container, bg=BG_CARD, padx=18, pady=14, highlightbackground=BORDER_COLOR, highlightthickness=1)
        timer_card.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 10))

        # Eyebrow tag + Status Pill Badge row
        timer_top = tk.Frame(timer_card, bg=BG_CARD)
        timer_top.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        tk.Label(
            timer_top,
            text="SESSION ACTUELLE",
            font=FONT_EYEBROW,
            fg=TEXT_MUTED,
            bg=BG_CARD
        ).pack(side=tk.LEFT)

        self.status_badge = tk.Label(
            timer_top,
            text="🟢 EN COURS",
            font=FONT_BADGE,
            fg=ACCENT_GREEN,
            bg=BG_CARD,
        )
        self.status_badge.pack(side=tk.RIGHT)

        # Centered Timer container within expanding card
        timer_center = tk.Frame(timer_card, bg=BG_CARD)
        timer_center.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        timer_inner = tk.Frame(timer_center, bg=BG_CARD)
        timer_inner.place(relx=0.5, rely=0.5, anchor="center")

        # Big Digital Timer
        self.timer_label = tk.Label(
            timer_inner,
            text="00:00:00",
            font=FONT_TIMER,
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        )
        self.timer_label.pack(anchor="center", pady=(0, 4))

        self.session_started_label = tk.Label(
            timer_inner,
            text="Session démarrée à --:--",
            font=FONT_SMALL,
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
        )
        self.session_started_label.pack(anchor="center", pady=(2, 0))

        self.session_estimated_end_label = tk.Label(
            timer_inner,
            text="Fin estimée à --:-- (7h + 1h30 pause)",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        self.session_estimated_end_label.pack(anchor="center", pady=(2, 0))

    def _toggle_pause(self):
        if self.agent.status == "active":
            self.agent.pause_work()
        elif self.agent.status == "paused":
            self.agent.resume_work()
        elif self.agent.status == "personal":
            self.agent.start_work()
        self._refresh_state()

    def _confirm_end_day(self):
        self.agent.prompt_end_work()

    def _refresh_state(self):
        status = self.agent.status
        if status == "active":
            self.status_badge.config(text="🟢 EN COURS", fg=ACCENT_GREEN)
            self.pause_resume_btn.config(text="⏸️  Mettre en pause", bg=ACCENT_AMBER, activebackground=ACCENT_AMBER_HOVER, state=tk.NORMAL)
        elif status == "paused":
            self.status_badge.config(text="🟡 EN PAUSE", fg=ACCENT_AMBER)
            self.pause_resume_btn.config(text="▶️  Reprendre le travail", bg=ACCENT_GREEN, activebackground=ACCENT_GREEN_HOVER, state=tk.NORMAL)
        elif status == "personal":
            self.status_badge.config(text="☕ MODE LOISIR / PERSO", fg=ACCENT_BLUE)
            self.pause_resume_btn.config(text="💼 Basculer en mode travail", bg=ACCENT_GREEN, activebackground=ACCENT_GREEN_HOVER, state=tk.NORMAL)
        else:
            self.status_badge.config(text="⚪ SESSION TERMINÉE", fg=TEXT_MUTED)
            self.pause_resume_btn.config(state=tk.DISABLED)

        # Update formatted timer
        elapsed_sec = self.agent.get_current_session_seconds()
        hours, remainder = divmod(elapsed_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.timer_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # Update start and estimated end time
        if self.agent.start_time_str:
            self.session_started_label.config(text=f"Session démarrée à {self.agent.start_time_str}")
        if self.agent.estimated_end_time_str:
            self.session_estimated_end_label.config(text=f"Fin estimée à {self.agent.estimated_end_time_str} (7h + 1h30 pause)")

        # Update today summary
        today_sec = self.agent.get_today_total_seconds()
        th, tm = divmod(today_sec // 60, 60)
        self.today_total_label.config(text=f"{th:02d}h {tm:02d}m")

        # Update Heartbeat
        last_hb = self.agent.get_last_heartbeat_ago()
        if self.agent.is_connected:
            self.heartbeat_label.config(text=f"Connecté ({last_hb})", fg=ACCENT_GREEN)
        else:
            self.heartbeat_label.config(text="Hors-ligne / Retry", fg=ACCENT_AMBER)

    def _update_loop(self):
        if self.top.winfo_exists():
            if self._is_visible:
                self._refresh_state()
            self.top.after(1000, self._update_loop)

    def show(self):
        logger.info("Showing Dashboard Window.")
        self._is_visible = True
        self.top.deiconify()
        self.top.lift()
        self.top.focus_force()
        self._refresh_state()

    def hide(self):
        logger.info("Hiding Dashboard Window to systray.")
        self._is_visible = False
        self.top.withdraw()

    def _on_window_resize(self, event):
        """Dynamically scales chronometer and text fonts when window is enlarged."""
        if event.widget == self.top:
            w = event.width
            h = event.height
            # Calculate dynamic font scaling (baseline: 540x720)
            scale = max(1.0, min(2.2, min(w / 540.0, h / 720.0)))
            timer_pt = int(46 * scale)
            sub_pt = int(12 * (1.0 + (scale - 1.0) * 0.4))
            try:
                self.timer_label.config(font=(FONT_FAMILY, timer_pt, "bold"))
                self.session_started_label.config(font=(FONT_FAMILY, sub_pt))
                self.session_estimated_end_label.config(font=(FONT_FAMILY, sub_pt))
            except Exception:
                pass


