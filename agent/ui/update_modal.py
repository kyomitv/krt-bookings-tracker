"""
Modern Tkinter Update Modal for KRT Bookings Tracker.
Presents available GitHub Releases, changelog, live download progress, and auto-restart trigger.
Aesthetic inspired by krtstudios.tv.
"""
import sys
import threading
import tkinter as tk
from typing import Optional, Callable

from agent.config import APP_VERSION, APP_VERSION_DISPLAY
from agent.updater import ReleaseInfo, AutoUpdater
from agent.ui.theme import (
    BG_MAIN, BG_CARD, BG_CARD_HOVER, BG_INPUT, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT_BLUE,
    ACCENT_BLUE_HOVER, ACCENT_GREEN, ACCENT_RED, FONT_TITLE,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_BADGE,
    apply_window_theme, center_window
)
from agent.logger import logger


class UpdateModal:
    """Dialog displaying new release information, changelog, and one-click update installation."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, release_info: ReleaseInfo, updater: AutoUpdater, on_before_restart: Optional[Callable[[], None]] = None):
        self.parent = parent
        self.release_info = release_info
        self.updater = updater
        self.on_before_restart = on_before_restart
        self.is_downloading = False

        self.top = tk.Toplevel(self.parent)
        apply_window_theme(self.top, title=f"Mise à jour disponible — {self.release_info.tag_name}")
        self.top.attributes("-topmost", True)

        # Only make transient if parent is a visible toplevel window (not hidden root)
        try:
            if hasattr(self.parent, "winfo_viewable") and self.parent.winfo_viewable():
                self.top.transient(self.parent)
        except Exception:
            pass

        self._build_ui()
        center_window(self.top, width=580, height=560)
        self.show()

    def _build_ui(self):
        container = tk.Frame(self.top, bg=BG_MAIN, padx=24, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        # --- Header Section ---
        header_frame = tk.Frame(container, bg=BG_MAIN)
        header_frame.pack(fill=tk.X, pady=(0, 14))

        title_label = tk.Label(
            header_frame,
            text="✨ Nouvelle version disponible !",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
        )
        title_label.pack(anchor="w")

        # Version tags comparison (Current -> New)
        tags_frame = tk.Frame(header_frame, bg=BG_MAIN)
        tags_frame.pack(fill=tk.X, pady=(6, 0))

        curr_badge = tk.Label(
            tags_frame,
            text=f"{APP_VERSION_DISPLAY}",
            font=FONT_BADGE,
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            padx=8,
            pady=3,
        )
        curr_badge.pack(side=tk.LEFT)

        arrow_label = tk.Label(
            tags_frame,
            text=" ➜ ",
            font=FONT_BODY_BOLD,
            bg=BG_MAIN,
            fg=ACCENT_BLUE,
        )
        arrow_label.pack(side=tk.LEFT)

        new_badge = tk.Label(
            tags_frame,
            text=f"{self.release_info.tag_name}",
            font=FONT_BADGE,
            bg=ACCENT_BLUE,
            fg="#FFFFFF",
            padx=8,
            pady=3,
        )
        new_badge.pack(side=tk.LEFT)

        # File size info
        size_mb = self.release_info.asset_size / (1024 * 1024) if self.release_info.asset_size else 0
        size_text = f"• Taille : {size_mb:.1f} Mo" if size_mb > 0 else ""
        info_label = tk.Label(
            tags_frame,
            text=f"{size_text}",
            font=FONT_SMALL,
            bg=BG_MAIN,
            fg=TEXT_MUTED,
            padx=8,
        )
        info_label.pack(side=tk.LEFT)

        # --- Changelog / Release Notes Box ---
        notes_label = tk.Label(
            container,
            text="Notes de version & Nouveautés :",
            font=FONT_BODY_BOLD,
            fg=TEXT_PRIMARY,
            bg=BG_MAIN,
        )
        notes_label.pack(anchor="w", pady=(0, 6))

        notes_frame = tk.Frame(container, bg=BG_INPUT, highlightbackground=BORDER_COLOR, highlightthickness=1)
        notes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 14))

        scrollbar = tk.Scrollbar(notes_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.notes_text = tk.Text(
            notes_frame,
            bg=BG_INPUT,
            fg=TEXT_SECONDARY,
            font=FONT_BODY,
            wrap=tk.WORD,
            padx=10,
            pady=10,
            relief=tk.FLAT,
            yscrollcommand=scrollbar.set,
            height=8,
        )
        self.notes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.notes_text.yview)

        # Populate changelog
        self.notes_text.insert(tk.END, self.release_info.body)
        self.notes_text.config(state=tk.DISABLED)

        # --- Progress Bar & Status (Initially hidden / idle) ---
        self.progress_frame = tk.Frame(container, bg=BG_MAIN)
        self.progress_frame.pack(fill=tk.X, pady=(0, 12))

        self.status_label = tk.Label(
            self.progress_frame,
            text="Prêt pour l'installation",
            font=FONT_SMALL,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        )
        self.status_label.pack(anchor="w", pady=(0, 4))

        # Modern styled Canvas progress bar
        self.progress_canvas = tk.Canvas(
            self.progress_frame,
            height=8,
            bg=BG_CARD,
            highlightthickness=0,
        )
        self.progress_canvas.pack(fill=tk.X)
        self.progress_bar_rect = self.progress_canvas.create_rectangle(0, 0, 0, 8, fill=ACCENT_BLUE, width=0)

        # --- Action Buttons ---
        self.btn_frame = tk.Frame(container, bg=BG_MAIN)
        self.btn_frame.pack(fill=tk.X)

        self.later_btn = tk.Button(
            self.btn_frame,
            text="Plus tard",
            font=FONT_BODY,
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            activebackground=BG_CARD_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self._on_close,
        )
        self.later_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.update_btn = tk.Button(
            self.btn_frame,
            text="📥 Mettre à jour & Redémarrer",
            font=FONT_BODY_BOLD,
            bg=ACCENT_BLUE,
            fg="#FFFFFF",
            activebackground=ACCENT_BLUE_HOVER,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self._start_update_download,
        )
        self.update_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0))

    def _update_progress(self, downloaded: int, total: int, percent: float):
        """Thread-safe UI callback to update download progress bar."""
        def apply():
            if not self.top.winfo_exists():
                return
            width = self.progress_canvas.winfo_width()
            fill_width = (percent / 100.0) * width
            self.progress_canvas.coords(self.progress_bar_rect, 0, 0, fill_width, 8)

            d_mb = downloaded / (1024 * 1024)
            t_mb = total / (1024 * 1024)
            self.status_label.config(
                text=f"Téléchargement : {percent:.1f}% ({d_mb:.1f} / {t_mb:.1f} Mo)",
                fg=TEXT_PRIMARY,
            )
        self.top.after(0, apply)

    def _start_update_download(self):
        """Initiates the download and installation in a background thread."""
        if self.is_downloading:
            return

        self.is_downloading = True
        self.update_btn.config(state=tk.DISABLED, text="Téléchargement...")
        self.later_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Connexion à GitHub...", fg=ACCENT_BLUE)

        def worker():
            downloaded_file = self.updater.download_update(
                self.release_info,
                progress_callback=self._update_progress
            )

            if not downloaded_file:
                def on_error():
                    self.is_downloading = False
                    self.status_label.config(text="❌ Échec du téléchargement. Veuillez réessayer.", fg=ACCENT_RED)
                    self.update_btn.config(state=tk.NORMAL, text="Réessayer")
                    self.later_btn.config(state=tk.NORMAL)
                self.top.after(0, on_error)
                return

            def on_install():
                self.status_label.config(text="⚡ Application de la mise à jour et redémarrage...", fg=ACCENT_GREEN)
                # Give UI 500ms to refresh
                self.top.after(500, lambda: self._execute_restart(downloaded_file))

            self.top.after(0, on_install)

        thread = threading.Thread(target=worker, daemon=True, name="UpdateDownloadThread")
        thread.start()

    def _execute_restart(self, new_binary):
        """Calls on_before_restart if provided, then replaces binary and exits cleanly."""
        if self.on_before_restart:
            try:
                self.on_before_restart()
            except Exception as e:
                logger.warning(f"Error during on_before_restart: {e}")

        success = self.updater.apply_update_and_restart(new_binary)
        if success:
            logger.info("Restart initiated. Terminating application for updater script.")
            import os
            try:
                self.top.destroy()
            except Exception:
                pass
            os._exit(0)
        else:
            self.status_label.config(text="❌ Erreur lors de l'application de la mise à jour.", fg=ACCENT_RED)
            self.later_btn.config(state=tk.NORMAL)

    def _on_close(self):
        if not self.is_downloading:
            try:
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
