"""
Confirmation modal before ending work day and quitting agent.
"""
import tkinter as tk
from typing import Optional, Callable
from agent.ui.theme import (
    BG_MAIN, BG_CARD, BG_CARD_HOVER, BORDER_COLOR, TEXT_PRIMARY,
    TEXT_SECONDARY, ACCENT_RED, ACCENT_RED_HOVER, FONT_TITLE,
    FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, center_window
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
        self.top.title("Fin de journée - KRT Tracker")
        self.top.configure(bg=BG_MAIN)
        self.top.resizable(False, False)
        self.top.protocol("WM_DELETE_WINDOW", self._cancel)
        center_window(self.top, 440, 320)

        self._build_ui()

    def _build_ui(self):
        container = tk.Frame(self.top, bg=BG_MAIN, padx=24, pady=24)
        container.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(
            container,
            text="Fin de journée de travail",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
        ).pack(anchor="w")

        tk.Label(
            container,
            text="Voulez-vous enregistrer la fin de votre journée de travail ?",
            font=FONT_BODY,
            fg=TEXT_SECONDARY,
            bg=BG_MAIN,
            wraplength=380,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(6, 16))

        # Summary Card
        card = tk.Frame(container, bg=BG_CARD, padx=16, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 20))

        tk.Label(
            card,
            text="Temps de travail enregistré aujourd'hui :",
            font=FONT_SMALL,
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            card,
            text=self.formatted_duration,
            font=FONT_SUBTITLE,
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(2, 0))

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
            padx=14,
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
