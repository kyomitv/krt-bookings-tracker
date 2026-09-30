"""
Confirmation modal before ending work day and quitting agent.
Aesthetic inspired by krtstudios.tv.
"""
import tkinter as tk
from typing import Optional, Callable
from agent.ui.theme import (
    BG_MAIN, BG_CARD, BG_CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_MUTED, ACCENT_RED, ACCENT_RED_HOVER, ACCENT_BLUE,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    FONT_EYEBROW, apply_window_theme, center_window, get_krt_logo_tk
)
from agent.logger import logger

class ConfirmEndWorkModal:
    """Modal asking confirmation before ending work day and closing agent."""

    def __init__(
        self,
        parent: tk.Tk,
        formatted_duration: str = "00:00:00",
    ):
        self.parent = parent
        self.formatted_duration = formatted_duration
        self.confirmed = False

        self.top = tk.Toplevel(self.parent)
        apply_window_theme(self.top, title="Fin de journée — KRT Tracker")
        self.top.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build_ui()
        center_window(self.top, width=490, height=370)

    def _build_ui(self):
        container = tk.Frame(self.top, bg=BG_MAIN, padx=26, pady=24)
        container.pack(fill=tk.BOTH, expand=True)

        # Header Eyebrow
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
            text="CLÔTURE DE JOURNÉE",
            font=FONT_EYEBROW,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        ).pack(side=tk.RIGHT)

        # Title
        tk.Label(
            container,
            text="Fin de journée de travail",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            container,
            text="Voulez-vous enregistrer la fin de votre session et fermer l'agent ?",
            font=FONT_BODY,
            fg=TEXT_SECONDARY,
            bg=BG_MAIN,
            wraplength=390,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 14))

        # Summary Card
        card = tk.Frame(container, bg=BG_CARD, padx=16, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 18))

        tk.Label(
            card,
            text="TEMPS CUMULÉ AUJOURD'HUI",
            font=FONT_EYEBROW,
            fg=TEXT_MUTED,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            card,
            text=self.formatted_duration,
            font=FONT_SUBTITLE,
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(3, 0))

        # Buttons frame
        btn_frame = tk.Frame(container, bg=BG_MAIN)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        cancel_btn = tk.Button(
            btn_frame,
            text="Annuler / Continuer",
            font=FONT_BODY,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_CARD_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            cursor="hand2",
            padx=14,
            pady=8,
            command=self._cancel,
        )
        cancel_btn.pack(side=tk.LEFT)

        confirm_btn = tk.Button(
            btn_frame,
            text="Enregistrer & Quitter",
            font=FONT_BODY_BOLD,
            bg=ACCENT_RED,
            fg="#FFFFFF",
            activebackground=ACCENT_RED_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self._confirm,
        )
        confirm_btn.pack(side=tk.RIGHT)

    def _confirm(self):
        logger.info("User confirmed END_WORK & Quit.")
        self.confirmed = True
        self.top.destroy()

    def _cancel(self):
        logger.info("User cancelled END_WORK dialog.")
        self.confirmed = False
        self.top.destroy()

    def show_modal(self) -> bool:
        self.top.deiconify()
        self.top.lift()
        self.top.attributes("-topmost", True)
        self.top.focus_force()
        self.parent.wait_window(self.top)
        return self.confirmed

