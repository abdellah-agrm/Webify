"""
WebP Optima Pro - Main Desktop Application
Built with CustomTkinter & Pillow.

Features:
- Dark Theme native UI
- Aspect Ratio Locked Dimension Controls (px)
- Dynamic Quality Slider (1-100%)
- Unicode Slug Renaming Engine (e.g., 'CONSTRUCTION & GROS ŒUVRE' -> 'construction-and-gros-oeuvre.webp')
- Multi-Image Batch Conversion & Queue Management
- Default Export Directory: C:\\Users\\Administrateur.SHARED-PC-05\\Downloads
- Open Target Directory button
- Background Threaded Processing with Progress Tracker
"""

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import List, Dict, Any, Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from slugify import generate_slug
from optimizer import (
    optimize_to_webp,
    get_image_info,
    calculate_aspect_dimensions,
    format_bytes,
)

# Color Palette (Slate Dark Theme)
COLOR_BG_DARK = "#14161f"
COLOR_SIDEBAR_BG = "#1a1c2a"
COLOR_CARD_BG = "#222536"
COLOR_CARD_BORDER = "#33374c"
COLOR_CARD_HOVER = "#2a2e43"

COLOR_PRIMARY = "#7aa2f7"       # Vibrant Cyan Blue
COLOR_PRIMARY_HOVER = "#3d59a1"
COLOR_SUCCESS = "#73daca"       # Emerald Green
COLOR_SUCCESS_HOVER = "#41a6b5"
COLOR_WARNING = "#e0af68"       # Amber
COLOR_DANGER = "#f7768e"        # Rose Red

COLOR_TEXT_MAIN = "#c0caf5"
COLOR_TEXT_MUTED = "#9aa5ce"
COLOR_TEXT_DARK = "#565f89"


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller freeze"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path


if HAS_DND:
    class BaseApp(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception as e:
                print(f"TkinterDnD init note: {e}")
else:
    class BaseApp(ctk.CTk):
        pass


class WebPOptimaApp(BaseApp):
    def __init__(self):
        super().__init__()

        # Appearance setup
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Webify — Web Image Optimizer")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(fg_color=COLOR_BG_DARK)

        # Set App Window Icon (.ico)
        icon_ico = get_resource_path("app_icon.ico")
        if icon_ico.exists():
            try:
                self.iconbitmap(str(icon_ico))
            except Exception:
                pass

        # State Variables
        self.default_downloads = r"C:\Users\Administrateur.SHARED-PC-05\Downloads"
        if not os.path.exists(self.default_downloads):
            self.default_downloads = str(Path.home() / "Downloads")

        self.output_dir = ctk.StringVar(value=self.default_downloads)
        self.quality_val = ctk.IntVar(value=82)
        self.lossless_val = ctk.BooleanVar(value=False)
        self.strip_exif_val = ctk.BooleanVar(value=True)
        self.keep_aspect_val = ctk.BooleanVar(value=True)

        self.custom_slug_input = ctk.StringVar(value="")
        self.slug_preview_var = ctk.StringVar(value="output-name.webp")

        self.width_var = ctk.StringVar(value="")
        self.height_var = ctk.StringVar(value="")

        # Internal state
        self.file_queue: List[Dict[str, Any]] = []
        self.is_processing = False
        self.lock_aspect_updating = False  # Prevents infinite loop during aspect calculation
        self.current_aspect_ratio = 16.0 / 9.0  # Fallback aspect ratio

        # Setup UI
        self._build_ui()

        # Enable Drag and Drop if available
        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drag_drop)
            except Exception as e:
                print(f"DnD initialization note: {e}")

    def _build_ui(self):
        # Main Layout: Left Sidebar (Controls) | Right Main (Queue & Stats)
        self.grid_columnconfigure(0, weight=0)  # Sidebar fixed
        self.grid_columnconfigure(1, weight=1)  # Queue panel flexible
        self.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------
        # LEFT SIDEBAR - CONTROLS & SETTINGS
        # ----------------------------------------------------
        sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR_BG, corner_radius=0, width=380)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar.grid_rowconfigure(8, weight=1)  # Spacer push bottom

        # App Brand Header
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(20, 10))

        # Brand Icon & Title Container
        title_box = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_box.pack(anchor="w")

        icon_png = get_resource_path("generative-image.png")
        if icon_png.exists():
            try:
                pil_img = Image.open(str(icon_png))
                ctk_icon = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(32, 32))
                lbl_icon = ctk.CTkLabel(title_box, image=ctk_icon, text="")
                lbl_icon.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        brand_title = ctk.CTkLabel(
            title_box,
            text="Webify",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_PRIMARY,
        )
        brand_title.pack(side="left")

        brand_sub = ctk.CTkLabel(
            brand_frame,
            text="Ultra-fast web image compression & slug generator",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
        )
        brand_sub.pack(anchor="w", pady=(4, 0))

        # Scrollable Settings Container
        settings_scroll = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent", label_text=""
        )
        settings_scroll.pack(fill="both", expand=True, padx=15, pady=10)

        # SECTION 1: Export Directory Choice
        self._create_section_label(settings_scroll, "1. EXPORT DESTINATION")

        dest_card = ctk.CTkFrame(
            settings_scroll, fg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER, border_width=1
        )
        dest_card.pack(fill="x", pady=(5, 15), ipady=8, ipadx=8)

        dest_entry = ctk.CTkEntry(
            dest_card,
            textvariable=self.output_dir,
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_CARD_BORDER,
            text_color=COLOR_TEXT_MAIN,
        )
        dest_entry.pack(fill="x", padx=10, pady=(8, 6))

        dest_btn_frame = ctk.CTkFrame(dest_card, fg_color="transparent")
        dest_btn_frame.pack(fill="x", padx=10)

        btn_browse = ctk.CTkButton(
            dest_btn_frame,
            text="📁 Browse Folder",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_CARD_HOVER,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
            height=30,
            command=self._browse_output_dir,
        )
        btn_browse.pack(side="left", expand=True, fill="x", padx=(0, 4))

        btn_open_folder = ctk.CTkButton(
            dest_btn_frame,
            text="↗ Open Folder",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_CARD_HOVER,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_MUTED,
            height=30,
            command=self._open_output_dir,
        )
        btn_open_folder.pack(side="right", expand=True, fill="x", padx=(4, 0))

        # SECTION 2: Image Quality Slider
        self._create_section_label(settings_scroll, "2. COMPRESSION & QUALITY")

        quality_card = ctk.CTkFrame(
            settings_scroll, fg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER, border_width=1
        )
        quality_card.pack(fill="x", pady=(5, 15), ipadx=8, ipady=8)

        qual_header = ctk.CTkFrame(quality_card, fg_color="transparent")
        qual_header.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            qual_header, text="Quality:", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_MAIN
        ).pack(side="left")

        self.lbl_quality_val = ctk.CTkLabel(
            qual_header,
            text="82% (Balanced Web)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_PRIMARY,
        )
        self.lbl_quality_val.pack(side="right")

        self.slider_quality = ctk.CTkSlider(
            quality_card,
            from_=1,
            to=100,
            number_of_steps=99,
            variable=self.quality_val,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            progress_color=COLOR_PRIMARY,
            command=self._on_quality_change,
        )
        self.slider_quality.pack(fill="x", padx=10, pady=8)

        chk_lossless = ctk.CTkCheckBox(
            quality_card,
            text="Lossless Mode (100% Perfect Quality)",
            variable=self.lossless_val,
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._on_lossless_toggle,
        )
        chk_lossless.pack(anchor="w", padx=10, pady=(2, 6))

        # SECTION 3: Dimension & Aspect Ratio Controls (px)
        self._create_section_label(settings_scroll, "3. DIMENSIONS & ASPECT RATIO (PX)")

        dim_card = ctk.CTkFrame(
            settings_scroll, fg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER, border_width=1
        )
        dim_card.pack(fill="x", pady=(5, 15), ipadx=8, ipady=8)

        # Aspect Ratio Lock Switch
        chk_aspect = ctk.CTkSwitch(
            dim_card,
            text="🔒 Lock Aspect Ratio (Auto-calculate)",
            variable=self.keep_aspect_val,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            progress_color=COLOR_PRIMARY,
        )
        chk_aspect.pack(anchor="w", padx=10, pady=(8, 8))

        # Width and Height Inputs
        inputs_frame = ctk.CTkFrame(dim_card, fg_color="transparent")
        inputs_frame.pack(fill="x", padx=10, pady=4)
        inputs_frame.columnconfigure(0, weight=1)
        inputs_frame.columnconfigure(1, weight=1)

        # Width Entry
        w_box = ctk.CTkFrame(inputs_frame, fg_color="transparent")
        w_box.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(w_box, text="Width (px)", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        self.entry_width = ctk.CTkEntry(
            w_box,
            textvariable=self.width_var,
            placeholder_text="Original",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_CARD_BORDER,
        )
        self.entry_width.pack(fill="x", pady=(2, 0))
        self.width_var.trace_add("write", self._on_width_edited)

        # Height Entry
        h_box = ctk.CTkFrame(inputs_frame, fg_color="transparent")
        h_box.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ctk.CTkLabel(h_box, text="Height (px)", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        self.entry_height = ctk.CTkEntry(
            h_box,
            textvariable=self.height_var,
            placeholder_text="Original",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_CARD_BORDER,
        )
        self.entry_height.pack(fill="x", pady=(2, 0))
        self.height_var.trace_add("write", self._on_height_edited)

        # Quick Preset Buttons
        ctk.CTkLabel(dim_card, text="Quick Resizing Presets:", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(
            anchor="w", padx=10, pady=(10, 4)
        )

        presets_frame = ctk.CTkFrame(dim_card, fg_color="transparent")
        presets_frame.pack(fill="x", padx=10, pady=(0, 6))

        presets = [
            ("Original", lambda: self._apply_preset_width(None)),
            ("1920px (FHD)", lambda: self._apply_preset_width(1920)),
            ("1280px (HD)", lambda: self._apply_preset_width(1280)),
            ("800px (Web)", lambda: self._apply_preset_width(800)),
        ]
        for idx, (p_text, p_cmd) in enumerate(presets):
            btn = ctk.CTkButton(
                presets_frame,
                text=p_text,
                font=ctk.CTkFont(size=10),
                fg_color=COLOR_CARD_HOVER,
                hover_color=COLOR_PRIMARY_HOVER,
                text_color=COLOR_TEXT_MAIN,
                height=26,
                command=p_cmd,
            )
            r = idx // 2
            c = idx % 2
            btn.grid(row=r, column=c, sticky="ew", padx=2, pady=2)
            presets_frame.columnconfigure(c, weight=1)

        # SECTION 4: Name & Unicode Slug Generator
        self._create_section_label(settings_scroll, "4. IMAGE SLUG RENAMING")

        slug_card = ctk.CTkFrame(
            settings_scroll, fg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER, border_width=1
        )
        slug_card.pack(fill="x", pady=(5, 15), ipadx=8, ipady=8)

        ctk.CTkLabel(
            slug_card,
            text="Custom Title / Slug Base:",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MAIN,
        ).pack(anchor="w", padx=10, pady=(8, 2))

        entry_slug = ctk.CTkEntry(
            slug_card,
            textvariable=self.custom_slug_input,
            placeholder_text="e.g. CONSTRUCTION & GROS ŒUVRE",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_CARD_BORDER,
        )
        entry_slug.pack(fill="x", padx=10, pady=4)
        self.custom_slug_input.trace_add("write", self._update_slug_preview)

        # Live Slug Preview Box
        preview_box = ctk.CTkFrame(slug_card, fg_color=COLOR_BG_DARK, corner_radius=6)
        preview_box.pack(fill="x", padx=10, pady=(6, 8))

        ctk.CTkLabel(
            preview_box,
            text="Generated WebP Slug:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=8, pady=(4, 0))

        lbl_slug_result = ctk.CTkLabel(
            preview_box,
            textvariable=self.slug_preview_var,
            font=ctk.CTkFont(size=12, weight="bold", family="Consolas"),
            text_color=COLOR_SUCCESS,
        )
        lbl_slug_result.pack(anchor="w", padx=8, pady=(0, 4))

        # SECTION 5: Extras & Options
        chk_strip = ctk.CTkCheckBox(
            settings_scroll,
            text="Strip EXIF / Camera Metadata (Smaller Size)",
            variable=self.strip_exif_val,
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
        )
        chk_strip.pack(anchor="w", padx=5, pady=(5, 10))

        # ----------------------------------------------------
        # RIGHT MAIN PANEL - DROP ZONE, QUEUE & PROGRESS
        # ----------------------------------------------------
        main_panel = ctk.CTkFrame(self, fg_color=COLOR_BG_DARK, corner_radius=0)
        main_panel.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        main_panel.grid_rowconfigure(2, weight=1)
        main_panel.grid_columnconfigure(0, weight=1)

        # Top Action Bar: Upload Buttons & Clear
        top_bar = ctk.CTkFrame(main_panel, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        btn_add_files = ctk.CTkButton(
            top_bar,
            text="➕ Select Images",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#ffffff",
            height=38,
            command=self._select_files,
        )
        btn_add_files.pack(side="left", padx=(0, 10))

        btn_add_dir = ctk.CTkButton(
            top_bar,
            text="📁 Select Folder",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_CARD_BG,
            hover_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT_MAIN,
            height=38,
            command=self._select_folder,
        )
        btn_add_dir.pack(side="left", padx=(0, 10))

        btn_clear = ctk.CTkButton(
            top_bar,
            text="🗑 Clear Queue",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_MUTED,
            height=38,
            command=self._clear_queue,
        )
        btn_clear.pack(side="right")

        # Stats Summary Banner
        self.stats_frame = ctk.CTkFrame(
            main_panel, fg_color=COLOR_SIDEBAR_BG, border_color=COLOR_CARD_BORDER, border_width=1
        )
        self.stats_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        self.lbl_stats_summary = ctk.CTkLabel(
            self.stats_frame,
            text="Queue: 0 files loaded | Target: C:\\Users\\Administrateur.SHARED-PC-05\\Downloads",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
        )
        self.lbl_stats_summary.pack(side="left", padx=15, pady=10)

        # Queue Scrollable Container
        self.queue_scroll = ctk.CTkScrollableFrame(
            main_panel,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            label_text="IMAGE CONVERSION QUEUE",
            label_font=ctk.CTkFont(size=12, weight="bold"),
            label_text_color=COLOR_TEXT_MUTED,
        )
        self.queue_scroll.grid(row=2, column=0, sticky="nsew", pady=(0, 15))

        # Initial Empty Queue Banner
        self.empty_label = ctk.CTkLabel(
            self.queue_scroll,
            text="✨ Drag & Drop Images / Folders Here\nor click 'Select Images' above to get started",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.empty_label.pack(expand=True, pady=120)

        # Bottom Processing Action Bar
        bottom_bar = ctk.CTkFrame(main_panel, fg_color=COLOR_SIDEBAR_BG, corner_radius=10)
        bottom_bar.grid(row=3, column=0, sticky="ew")

        bottom_content = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        bottom_content.pack(fill="x", padx=15, pady=15)

        self.btn_optimize_all = ctk.CTkButton(
            bottom_content,
            text="🚀 OPTIMIZE ALL IMAGES (WEBP)",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            text_color="#102a24",
            height=46,
            command=self._start_optimization_thread,
        )
        self.btn_optimize_all.pack(fill="x", pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(
            bottom_content,
            fg_color=COLOR_BG_DARK,
            progress_color=COLOR_SUCCESS,
            height=8,
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

    # ----------------------------------------------------
    # HELPER UI BUILDERS & EVENT HANDLERS
    # ----------------------------------------------------
    def _create_section_label(self, parent, text: str):
        lbl = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_PRIMARY,
        )
        lbl.pack(anchor="w", pady=(10, 2))

    def _browse_output_dir(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir.get())
        if folder:
            self.output_dir.set(folder)
            self._update_stats_banner()

    def _open_output_dir(self):
        target = self.output_dir.get()
        if os.path.exists(target):
            try:
                os.startfile(target)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open directory: {e}")
        else:
            messagebox.showwarning("Warning", "Output directory does not exist yet!")

    def _on_quality_change(self, val):
        q = int(val)
        if self.lossless_val.get():
            self.lbl_quality_val.configure(text="Lossless Mode (100%)", text_color=COLOR_SUCCESS)
        else:
            tag = "Low Size" if q < 60 else ("Balanced Web" if q <= 85 else "High Quality")
            self.lbl_quality_val.configure(text=f"{q}% ({tag})", text_color=COLOR_PRIMARY)

    def _on_lossless_toggle(self):
        if self.lossless_val.get():
            self.slider_quality.configure(state="disabled")
            self.lbl_quality_val.configure(text="Lossless Mode (100%)", text_color=COLOR_SUCCESS)
        else:
            self.slider_quality.configure(state="normal")
            self._on_quality_change(self.quality_val.get())

    def _update_slug_preview(self, *args):
        raw = self.custom_slug_input.get()
        if raw.strip():
            slug = generate_slug(raw)
        else:
            slug = "image-title"
        self.slug_preview_var.set(f"{slug}.webp")
        self._refresh_queue_slug_display()

    # ----------------------------------------------------
    # DYNAMIC ASPECT RATIO RESIZING LOGIC
    # ----------------------------------------------------
    def _on_width_edited(self, *args):
        if self.lock_aspect_updating or not self.keep_aspect_val.get():
            return
        w_str = self.width_var.get().strip()
        if not w_str.isdigit():
            return
        w = int(w_str)
        if w > 0 and self.current_aspect_ratio > 0:
            self.lock_aspect_updating = True
            h = max(1, int(round(w / self.current_aspect_ratio)))
            self.height_var.set(str(h))
            self.lock_aspect_updating = False

    def _on_height_edited(self, *args):
        if self.lock_aspect_updating or not self.keep_aspect_val.get():
            return
        h_str = self.height_var.get().strip()
        if not h_str.isdigit():
            return
        h = int(h_str)
        if h > 0 and self.current_aspect_ratio > 0:
            self.lock_aspect_updating = True
            w = max(1, int(round(h * self.current_aspect_ratio)))
            self.width_var.set(str(w))
            self.lock_aspect_updating = False

    def _apply_preset_width(self, width: Optional[int]):
        if width is None:
            self.width_var.set("")
            self.height_var.set("")
        else:
            self.width_var.set(str(width))

    # ----------------------------------------------------
    # FILE QUEUE MANAGEMENT & DRAG AND DROP
    # ----------------------------------------------------
    def _on_drag_drop(self, event):
        files_raw = event.data
        # Parse dropped file list from TkinterDnD string
        paths = self.splitlist(files_raw) if hasattr(self, "splitlist") else [files_raw]
        valid_paths = []
        for p in paths:
            clean_p = p.strip("{}")
            if os.path.isdir(clean_p):
                for root, _, files in os.walk(clean_p):
                    for f in files:
                        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif")):
                            valid_paths.append(os.path.join(root, f))
            elif os.path.isfile(clean_p):
                valid_paths.append(clean_p)
        self._add_files_to_queue(valid_paths)

    def _select_files(self):
        files = filedialog.askopenfilenames(
            title="Select Images to Optimize",
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tiff;*.gif"),
                ("All Files", "*.*"),
            ],
        )
        if files:
            self._add_files_to_queue(list(files))

    def _select_folder(self):
        folder = filedialog.askdirectory(title="Select Folder containing Images")
        if folder:
            valid_paths = []
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif")):
                        valid_paths.append(os.path.join(root, f))
            self._add_files_to_queue(valid_paths)

    def _add_files_to_queue(self, paths: List[str]):
        new_items = 0
        for p in paths:
            if any(item["path"] == p for item in self.file_queue):
                continue

            info = get_image_info(p)
            if not info:
                continue

            item = {
                "path": p,
                "orig_w": info["width"],
                "orig_h": info["height"],
                "orig_size": info["file_size"],
                "format": info["format"],
                "status": "Pending",
                "result": None,
                "widget_frame": None,
            }
            self.file_queue.append(item)
            new_items += 1

        if new_items > 0 and self.file_queue:
            # Update aspect ratio reference from first image
            first = self.file_queue[0]
            if first["orig_w"] > 0 and first["orig_h"] > 0:
                self.current_aspect_ratio = first["orig_w"] / first["orig_h"]

        self._render_queue()
        self._update_stats_banner()

    def _clear_queue(self):
        self.file_queue.clear()
        self._render_queue()
        self._update_stats_banner()
        self.progress_bar.set(0)

    def _remove_queue_item(self, idx: int):
        if 0 <= idx < len(self.file_queue):
            del self.file_queue[idx]
            self._render_queue()
            self._update_stats_banner()

    def _render_queue(self):
        # Clear existing widgets in scroll frame
        for child in self.queue_scroll.winfo_children():
            child.destroy()

        if not self.file_queue:
            self.empty_label = ctk.CTkLabel(
                self.queue_scroll,
                text="✨ Drag & Drop Images / Folders Here\nor click 'Select Images' above to get started",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=COLOR_TEXT_MUTED,
            )
            self.empty_label.pack(expand=True, pady=120)
            return

        is_multi = len(self.file_queue) > 1
        custom_base = self.custom_slug_input.get().strip()

        for idx, item in enumerate(self.file_queue):
            row_frame = ctk.CTkFrame(
                self.queue_scroll,
                fg_color=COLOR_CARD_BG,
                border_color=COLOR_CARD_BORDER,
                border_width=1,
            )
            row_frame.pack(fill="x", pady=4, padx=5)
            item["widget_frame"] = row_frame

            row_content = ctk.CTkFrame(row_frame, fg_color="transparent")
            row_content.pack(fill="x", padx=10, pady=8)

            # Left File Details
            file_name = Path(item["path"]).name
            info_str = f"{file_name} [{item['format'].upper()} • {item['orig_w']}x{item['orig_h']} • {format_bytes(item['orig_size'])}]"

            lbl_info = ctk.CTkLabel(
                row_content,
                text=info_str,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT_MAIN,
                anchor="w",
            )
            lbl_info.pack(side="left", fill="x", expand=True)

            # Slug Target Name
            if custom_base:
                if is_multi:
                    target_slug = f"{generate_slug(custom_base)}-{idx + 1}.webp"
                else:
                    target_slug = f"{generate_slug(custom_base)}.webp"
            else:
                target_slug = f"{generate_slug(Path(item['path']).stem)}.webp"

            lbl_slug = ctk.CTkLabel(
                row_content,
                text=f"➔ {target_slug}",
                font=ctk.CTkFont(size=11, family="Consolas"),
                text_color=COLOR_PRIMARY,
            )
            lbl_slug.pack(side="left", padx=15)

            # Status / Result Badge
            status = item["status"]
            if status == "Pending":
                badge_bg = COLOR_CARD_HOVER
                badge_fg = COLOR_TEXT_MUTED
                badge_text = "Pending"
            elif status == "Processing":
                badge_bg = COLOR_PRIMARY_HOVER
                badge_fg = "#ffffff"
                badge_text = "Processing..."
            elif status == "Done" and item["result"]:
                res = item["result"]
                badge_bg = COLOR_SUCCESS_HOVER
                badge_fg = "#ffffff"
                badge_text = f"{format_bytes(res['opt_size'])} (-{res['savings_pct']:.1f}%)"
            else:
                badge_bg = COLOR_DANGER
                badge_fg = "#ffffff"
                badge_text = "Error"

            lbl_badge = ctk.CTkLabel(
                row_content,
                text=badge_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=badge_bg,
                text_color=badge_fg,
                corner_radius=4,
                width=110,
                height=24,
            )
            lbl_badge.pack(side="left", padx=10)

            # Remove Item Button
            btn_del = ctk.CTkButton(
                row_content,
                text="✕",
                width=26,
                height=24,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                hover_color=COLOR_DANGER,
                text_color=COLOR_TEXT_MUTED,
                command=lambda i=idx: self._remove_queue_item(i),
            )
            btn_del.pack(side="right")

    def _refresh_queue_slug_display(self):
        if self.file_queue:
            self._render_queue()

    def _update_stats_banner(self):
        total_count = len(self.file_queue)
        target_path = self.output_dir.get()

        if total_count == 0:
            self.lbl_stats_summary.configure(
                text=f"Queue: 0 files | Export Folder: {target_path}",
                text_color=COLOR_TEXT_MUTED,
            )
            return

        done_items = [i for i in self.file_queue if i["status"] == "Done" and i["result"]]
        if done_items:
            orig_total = sum(i["result"]["orig_size"] for i in done_items)
            opt_total = sum(i["result"]["opt_size"] for i in done_items)
            saved_bytes = max(0, orig_total - opt_total)
            pct = (saved_bytes / orig_total * 100.0) if orig_total > 0 else 0.0

            text = (
                f"Queue: {len(done_items)}/{total_count} Done | "
                f"Original: {format_bytes(orig_total)} ➔ Optimized: {format_bytes(opt_total)} | "
                f"Saved: {format_bytes(saved_bytes)} ({pct:.1f}%)"
            )
            self.lbl_stats_summary.configure(text=text, text_color=COLOR_SUCCESS)
        else:
            total_bytes = sum(i["orig_size"] for i in self.file_queue)
            text = f"Queue: {total_count} files ({format_bytes(total_bytes)}) ready | Export Folder: {target_path}"
            self.lbl_stats_summary.configure(text=text, text_color=COLOR_TEXT_MAIN)

    # ----------------------------------------------------
    # BATCH OPTIMIZATION BACKGROUND THREAD
    # ----------------------------------------------------
    def _start_optimization_thread(self):
        if not self.file_queue:
            messagebox.showinfo("Information", "Please add at least one image to optimize!")
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.btn_optimize_all.configure(state="disabled", text="⏳ OPTIMIZING IMAGES...")
        self.progress_bar.set(0)

        # Spawn background processing thread
        thread = threading.Thread(target=self._run_optimization, daemon=True)
        thread.start()

    def _run_optimization(self):
        out_dir = self.output_dir.get()
        quality = self.quality_val.get()
        lossless = self.lossless_val.get()
        strip_exif = self.strip_exif_val.get()
        keep_aspect = self.keep_aspect_val.get()

        # Parse width/height inputs
        w_val = int(self.width_var.get().strip()) if self.width_var.get().strip().isdigit() else None
        h_val = int(self.height_var.get().strip()) if self.height_var.get().strip().isdigit() else None

        custom_base = self.custom_slug_input.get().strip()
        is_multi = len(self.file_queue) > 1

        total = len(self.file_queue)

        for idx, item in enumerate(self.file_queue):
            item["status"] = "Processing"
            self.after(0, self._render_queue)

            # Determine slug name
            if custom_base:
                if is_multi:
                    custom_name = f"{custom_base}-{idx + 1}"
                else:
                    custom_name = custom_base
            else:
                custom_name = Path(item["path"]).stem

            res = optimize_to_webp(
                input_path=item["path"],
                output_dir=out_dir,
                custom_name=custom_name,
                target_w=w_val,
                target_h=h_val,
                keep_aspect=keep_aspect,
                quality=quality,
                lossless=lossless,
                strip_exif=strip_exif,
                compression_method=6,
            )

            if res.get("success"):
                item["status"] = "Done"
                item["result"] = res
            else:
                item["status"] = "Error"
                item["result"] = res

            progress = (idx + 1) / total
            self.after(0, self.progress_bar.set, progress)
            self.after(0, self._render_queue)
            self.after(0, self._update_stats_banner)

        self.is_processing = False
        self.after(
            0,
            lambda: self.btn_optimize_all.configure(
                state="normal", text="🚀 OPTIMIZE ALL IMAGES (WEBP)"
            ),
        )
        self.after(0, self._on_batch_complete)

    def _on_batch_complete(self):
        messagebox.showinfo(
            "Optimization Complete!",
            f"Successfully processed images!\nSaved to: {self.output_dir.get()}",
        )


def main():
    app = WebPOptimaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
