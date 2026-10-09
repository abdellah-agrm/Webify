"""
Webify — Web Image Optimizer (Dark Dashboard Pro)
Built with CustomTkinter & Pillow.

Features:
- Professional "Dark Dashboard Pro" design system (Avast / Adobe style)
- 4-Card dynamic live metrics dashboard (Files, Saved MB, Efficiency %, Destination)
- Tab-based streamlined controls (Quality, Dimensions, Naming, Output)
- Visual drop zone empty state with click-to-browse
- Rich image queue rows with 42x42 thumbnails, format & dimension chips, and slug previews
- Aspect-locked dimension controls with standard web presets
- Dynamic unicode slug generator with live preview
- Multi-threaded batch processing with sleek edge progress bar
- Full TkinterDnD drag-and-drop support
"""

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import List, Dict, Any, Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

# Configure TkinterDnD library environment if bundled with PyInstaller
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _meipass = Path(sys._MEIPASS)
    for _cand in [_meipass / "tkinterdnd2" / "tkdnd", _meipass / "tkdnd", _meipass / "tkinterdnd2"]:
        if _cand.exists():
            os.environ["TKDND_LIBRARY"] = str(_cand)
            break

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

# -------------------------------------------------------------------------
# DESIGN SYSTEM: Dark Dashboard Pro Palette (Avast / Adobe / JetBrains)
# -------------------------------------------------------------------------
COLOR_BG_DARK = "#0D0F1A"          # Layer 1: App deep background
COLOR_SURFACE = "#161827"          # Layer 2: Surface cards and panels
COLOR_SURFACE_HOVER = "#1E2035"    # Layer 3: Elevated hover & pill buttons
COLOR_BORDER = "#252840"           # Subtle 1px structural border
COLOR_BORDER_FOCUS = "#3A3F66"     # Focused / active border

COLOR_ACCENT = "#4C8EFF"           # Electric Blue - Single primary brand accent
COLOR_ACCENT_HOVER = "#6BA3FF"     # Lighter blue on hover
COLOR_ACCENT_BG = "#152445"        # Low-opacity accent background for chips

COLOR_SUCCESS = "#27C99A"          # Mint emerald (done / savings)
COLOR_SUCCESS_HOVER = "#1FA37C"
COLOR_SUCCESS_BG = "#11382C"

COLOR_DANGER = "#FF5B6B"           # Coral red (errors / delete)
COLOR_DANGER_HOVER = "#E04857"
COLOR_DANGER_BG = "#3D171E"

COLOR_WARNING = "#F5A623"          # Amber notice
COLOR_WARNING_BG = "#382910"

COLOR_TEXT_PRIMARY = "#E8EAFF"     # High contrast primary text
COLOR_TEXT_SECONDARY = "#8890B5"   # Medium contrast labels / descriptions
COLOR_TEXT_MUTED = "#555A80"       # Dimmed hints, timestamps & icons


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

        # CustomTkinter Appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Webify — Web Image Optimizer")
        self.geometry("1180x760")
        self.minsize(1020, 660)
        self.configure(fg_color=COLOR_BG_DARK)

        # Set App Window Icon (.ico)
        icon_ico = get_resource_path("app_icon.ico")
        if icon_ico.exists():
            try:
                self.iconbitmap(str(icon_ico))
            except Exception:
                pass

        # State Variables
        downloads_path = Path.home() / "Downloads"
        self.default_downloads = str(downloads_path if downloads_path.exists() else Path.home())

        self.output_dir = ctk.StringVar(value=self.default_downloads)
        self.quality_val = ctk.IntVar(value=82)
        self.lossless_val = ctk.BooleanVar(value=False)
        self.strip_exif_val = ctk.BooleanVar(value=True)
        self.keep_aspect_val = ctk.BooleanVar(value=True)

        self.custom_slug_input = ctk.StringVar(value="")
        self.slug_preview_var = ctk.StringVar(value="image-title.webp")

        self.width_var = ctk.StringVar(value="")
        self.height_var = ctk.StringVar(value="")

        # Internal Queue & Engine State
        self.file_queue: List[Dict[str, Any]] = []
        self.is_processing = False
        self.lock_aspect_updating = False
        self.current_aspect_ratio = 16.0 / 9.0

        # UI References for Dynamic Updates
        self.stat_val_count = None
        self.stat_val_saved = None
        self.stat_val_pct = None
        self.stat_val_folder = None
        self.queue_container = None
        self.empty_zone = None

        # Build UI Architecture
        self._build_ui()

        # Enable Drag and Drop if available
        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drag_drop)
            except Exception as e:
                print(f"DnD initialization note: {e}")

    # =========================================================================
    # UI ARCHITECTURE
    # =========================================================================
    def _build_ui(self):
        # Master Root Grid: Header (row 0), Body (row 1), Progress Bar (row 2)
        self.grid_rowconfigure(0, weight=0)  # Top Header bar
        self.grid_rowconfigure(1, weight=1)  # Two-column dashboard body
        self.grid_rowconfigure(2, weight=0)  # Bottom edge progress bar
        self.grid_columnconfigure(0, weight=1)

        # 1. Header Bar
        self._build_header_bar()

        # 2. Main Dashboard Body (Left: Tabbed Settings, Right: Dashboard & Queue)
        body_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(12, 8))
        body_frame.grid_columnconfigure(0, weight=0)  # Settings column fixed width
        body_frame.grid_columnconfigure(1, weight=1)  # Queue & stats flexible
        body_frame.grid_rowconfigure(0, weight=1)

        # Left Column: Tabbed Settings (330px width)
        self._build_settings_panel(body_frame)

        # Right Column: Dashboard Stats, Queue, Bottom Action Bar
        self._build_main_dashboard(body_frame)

        # 3. Bottom Edge Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            self,
            fg_color=COLOR_SURFACE,
            progress_color=COLOR_ACCENT,
            height=4,
            corner_radius=0,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew")
        self.progress_bar.set(0)

    # -------------------------------------------------------------------------
    # 1. TOP HEADER BAR
    # -------------------------------------------------------------------------
    def _build_header_bar(self):
        header = ctk.CTkFrame(
            self,
            fg_color=COLOR_SURFACE,
            corner_radius=0,
            height=56,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=20)

        # Left: App Brand & Icon
        brand_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        brand_box.pack(side="left", fill="y")

        icon_png = get_resource_path("generative-image.png")
        if icon_png.exists():
            try:
                pil_icon = Image.open(str(icon_png))
                ctk_icon = ctk.CTkImage(light_image=pil_icon, dark_image=pil_icon, size=(28, 28))
                lbl_icon = ctk.CTkLabel(brand_box, image=ctk_icon, text="")
                lbl_icon.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        brand_text_box = ctk.CTkFrame(brand_box, fg_color="transparent")
        brand_text_box.pack(side="left")

        lbl_app_name = ctk.CTkLabel(
            brand_text_box,
            text="Webify",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        lbl_app_name.pack(side="left", padx=(0, 8))

        lbl_tagline = ctk.CTkLabel(
            brand_text_box,
            text="High-Performance WebP Optimizer",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        )
        lbl_tagline.pack(side="left")

        # Right: Version Pill & Engine Status
        right_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        right_box.pack(side="right", fill="y")

        pill_version = ctk.CTkFrame(
            right_box,
            fg_color=COLOR_SURFACE_HOVER,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        pill_version.pack(side="right", pady=12)

        lbl_ver = ctk.CTkLabel(
            pill_version,
            text="v1.0 Pro",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_ACCENT,
            padx=10,
            pady=3,
        )
        lbl_ver.pack()

    # -------------------------------------------------------------------------
    # 2. LEFT SETTINGS PANEL (Tabbed Architecture)
    # -------------------------------------------------------------------------
    def _build_settings_panel(self, parent):
        panel = ctk.CTkFrame(
            parent,
            fg_color=COLOR_SURFACE,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_BORDER,
            width=330,
        )
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        panel.grid_propagate(False)

        # Panel Header Title
        title_box = ctk.CTkFrame(panel, fg_color="transparent")
        title_box.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            title_box,
            text="SETTINGS & OUTPUT",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w")

        # Tabview for Clean Categorized Controls
        self.tabview = ctk.CTkTabview(
            panel,
            fg_color="transparent",
            segmented_button_fg_color=COLOR_SURFACE_HOVER,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_selected_hover_color=COLOR_ACCENT_HOVER,
            segmented_button_unselected_color=COLOR_SURFACE_HOVER,
            segmented_button_unselected_hover_color=COLOR_BORDER_FOCUS,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=8,
        )
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        tab_quality = self.tabview.add("Quality")
        tab_dimensions = self.tabview.add("Dimensions")
        tab_naming = self.tabview.add("Naming")
        tab_output = self.tabview.add("Output")

        self._populate_quality_tab(tab_quality)
        self._populate_dimensions_tab(tab_dimensions)
        self._populate_naming_tab(tab_naming)
        self._populate_output_tab(tab_output)

    def _populate_quality_tab(self, parent):
        # Quality Value & Slider
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(10, 4))

        ctk.CTkLabel(
            header,
            text="WebP Quality",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(side="left")

        self.lbl_quality_val = ctk.CTkLabel(
            header,
            text="82% (Balanced Web)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_ACCENT,
        )
        self.lbl_quality_val.pack(side="right")

        self.slider_quality = ctk.CTkSlider(
            parent,
            from_=1,
            to=100,
            number_of_steps=99,
            variable=self.quality_val,
            button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            progress_color=COLOR_ACCENT,
            command=self._on_quality_change,
        )
        self.slider_quality.pack(fill="x", pady=(4, 14))

        # Quality Preset Pills
        ctk.CTkLabel(
            parent,
            text="Quick Presets",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 6))

        presets_box = ctk.CTkFrame(parent, fg_color="transparent")
        presets_box.pack(fill="x", pady=(0, 16))
        presets_box.columnconfigure((0, 1, 2), weight=1)

        presets = [
            ("Minimal (60%)", 60),
            ("Web (82%)", 82),
            ("Print (95%)", 95),
        ]
        for idx, (label, val) in enumerate(presets):
            btn = ctk.CTkButton(
                presets_box,
                text=label,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=COLOR_SURFACE_HOVER,
                hover_color=COLOR_BORDER_FOCUS,
                text_color=COLOR_TEXT_PRIMARY,
                height=28,
                corner_radius=6,
                command=lambda v=val: self._apply_quality_preset(v),
            )
            btn.grid(row=0, column=idx, padx=2, sticky="ew")

        # Lossless Switch
        divider = ctk.CTkFrame(parent, fg_color=COLOR_BORDER, height=1)
        divider.pack(fill="x", pady=(4, 14))

        lossless_box = ctk.CTkFrame(
            parent,
            fg_color=COLOR_SURFACE_HOVER,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        lossless_box.pack(fill="x", ipady=8, ipadx=10)

        self.switch_lossless = ctk.CTkSwitch(
            lossless_box,
            text="Lossless Compression",
            variable=self.lossless_val,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            progress_color=COLOR_ACCENT,
            command=self._on_lossless_toggle,
        )
        self.switch_lossless.pack(anchor="w", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            lossless_box,
            text="Preserves 100% pixel fidelity with larger file size.",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
            wraplength=260,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))

    def _populate_dimensions_tab(self, parent):
        # Aspect Ratio Switch
        switch_frame = ctk.CTkFrame(
            parent,
            fg_color=COLOR_SURFACE_HOVER,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        switch_frame.pack(fill="x", pady=(10, 14), ipadx=10, ipady=8)

        chk_aspect = ctk.CTkSwitch(
            switch_frame,
            text="🔒 Lock Aspect Ratio",
            variable=self.keep_aspect_val,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            progress_color=COLOR_ACCENT,
        )
        chk_aspect.pack(anchor="w", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            switch_frame,
            text="Editing either dimension scales the other proportionally.",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
            wraplength=260,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Width & Height Inputs Side-by-Side
        inputs_box = ctk.CTkFrame(parent, fg_color="transparent")
        inputs_box.pack(fill="x", pady=(0, 12))
        inputs_box.columnconfigure((0, 1), weight=1)

        # Width Box
        w_box = ctk.CTkFrame(inputs_box, fg_color="transparent")
        w_box.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkLabel(w_box, text="Width (px)", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.entry_width = ctk.CTkEntry(
            w_box,
            textvariable=self.width_var,
            placeholder_text="Original",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=6,
            height=32,
        )
        self.entry_width.pack(fill="x", pady=(4, 0))
        self.width_var.trace_add("write", self._on_width_edited)

        # Height Box
        h_box = ctk.CTkFrame(inputs_box, fg_color="transparent")
        h_box.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ctk.CTkLabel(h_box, text="Height (px)", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.entry_height = ctk.CTkEntry(
            h_box,
            textvariable=self.height_var,
            placeholder_text="Original",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=6,
            height=32,
        )
        self.entry_height.pack(fill="x", pady=(4, 0))
        self.height_var.trace_add("write", self._on_height_edited)

        # Quick Preset Buttons
        ctk.CTkLabel(
            parent,
            text="Dimension Presets",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=(8, 6))

        presets_grid = ctk.CTkFrame(parent, fg_color="transparent")
        presets_grid.pack(fill="x")
        presets_grid.columnconfigure((0, 1), weight=1)

        dim_presets = [
            ("Original", None),
            ("1920 (FHD)", 1920),
            ("1280 (HD)", 1280),
            ("800 (Web)", 800),
        ]
        for idx, (label, val) in enumerate(dim_presets):
            btn = ctk.CTkButton(
                presets_grid,
                text=label,
                font=ctk.CTkFont(size=11),
                fg_color=COLOR_SURFACE_HOVER,
                hover_color=COLOR_BORDER_FOCUS,
                text_color=COLOR_TEXT_PRIMARY,
                height=28,
                corner_radius=6,
                command=lambda v=val: self._apply_preset_width(v),
            )
            r = idx // 2
            c = idx % 2
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")

    def _populate_naming_tab(self, parent):
        ctk.CTkLabel(
            parent,
            text="Custom Title / Slug Base",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w", pady=(10, 4))

        entry_slug = ctk.CTkEntry(
            parent,
            textvariable=self.custom_slug_input,
            placeholder_text="e.g. CONSTRUCTION & GROS ŒUVRE",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=6,
            height=34,
        )
        entry_slug.pack(fill="x", pady=(0, 12))
        self.custom_slug_input.trace_add("write", self._update_slug_preview)

        # Monospace Live Slug Preview Card
        ctk.CTkLabel(
            parent,
            text="Generated WebP Slug:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 4))

        preview_card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_BG_DARK,
            corner_radius=6,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        preview_card.pack(fill="x", pady=(0, 14), ipadx=8, ipady=6)

        lbl_slug_res = ctk.CTkLabel(
            preview_card,
            textvariable=self.slug_preview_var,
            font=ctk.CTkFont(size=12, weight="bold", family="Consolas"),
            text_color=COLOR_ACCENT,
            anchor="w",
        )
        lbl_slug_res.pack(fill="x", padx=10, pady=4)

        # Explanatory tip
        tip_box = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE_HOVER, corner_radius=6)
        tip_box.pack(fill="x", padx=2, pady=4, ipadx=8, ipady=6)

        ctk.CTkLabel(
            tip_box,
            text="💡 Tip: Non-ASCII characters (é, ü, œ, &) are automatically converted into search-engine-friendly clean slugs.",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=260,
            justify="left",
        ).pack(fill="x", padx=6, pady=4)

    def _populate_output_tab(self, parent):
        ctk.CTkLabel(
            parent,
            text="Export Destination",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w", pady=(10, 4))

        dest_entry = ctk.CTkEntry(
            parent,
            textvariable=self.output_dir,
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_SECONDARY,
            corner_radius=6,
            height=32,
            state="readonly",
        )
        dest_entry.pack(fill="x", pady=(0, 10))

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 14))
        btn_row.columnconfigure((0, 1), weight=1)

        btn_browse = ctk.CTkButton(
            btn_row,
            text="📁 Browse",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_SURFACE_HOVER,
            hover_color=COLOR_BORDER_FOCUS,
            text_color=COLOR_TEXT_PRIMARY,
            height=30,
            corner_radius=6,
            command=self._browse_output_dir,
        )
        btn_browse.grid(row=0, column=0, padx=(0, 3), sticky="ew")

        btn_open = ctk.CTkButton(
            btn_row,
            text="↗ Open Folder",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_SURFACE_HOVER,
            hover_color=COLOR_BORDER_FOCUS,
            text_color=COLOR_TEXT_SECONDARY,
            height=30,
            corner_radius=6,
            command=self._open_output_dir,
        )
        btn_open.grid(row=0, column=1, padx=(3, 0), sticky="ew")

        divider = ctk.CTkFrame(parent, fg_color=COLOR_BORDER, height=1)
        divider.pack(fill="x", pady=(6, 12))

        # Metadata switch
        exif_box = ctk.CTkFrame(
            parent,
            fg_color=COLOR_SURFACE_HOVER,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        exif_box.pack(fill="x", ipady=8, ipadx=10)

        chk_strip = ctk.CTkSwitch(
            exif_box,
            text="Strip Camera / EXIF Data",
            variable=self.strip_exif_val,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            progress_color=COLOR_ACCENT,
        )
        chk_strip.pack(anchor="w", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            exif_box,
            text="Removes camera GPS, timestamp & model info for privacy and reduced size.",
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_MUTED,
            wraplength=260,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))

    # -------------------------------------------------------------------------
    # 3. RIGHT MAIN DASHBOARD (Stats + Drop Zone / Queue + Action Bar)
    # -------------------------------------------------------------------------
    def _build_main_dashboard(self, parent):
        main_col = ctk.CTkFrame(parent, fg_color="transparent")
        main_col.grid(row=0, column=1, sticky="nsew")
        main_col.grid_rowconfigure(1, weight=1)  # Queue/Drop zone flexible
        main_col.grid_columnconfigure(0, weight=1)

        # 1. Top Stat Cards Row (4 horizontal cards)
        self._build_stat_cards(main_col)

        # 2. Central Content Area: Drop Zone (Empty) or Queue List (Populated)
        self.center_card = ctk.CTkFrame(
            main_col,
            fg_color=COLOR_SURFACE,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        self.center_card.grid(row=1, column=0, sticky="nsew", pady=(12, 12))
        self.center_card.grid_rowconfigure(0, weight=1)
        self.center_card.grid_columnconfigure(0, weight=1)

        # Render Drop Zone by default
        self._render_queue()

        # 3. Bottom Sticky Action Bar
        self._build_action_bar(main_col)

    def _build_stat_cards(self, parent):
        stats_grid = ctk.CTkFrame(parent, fg_color="transparent")
        stats_grid.grid(row=0, column=0, sticky="ew")
        stats_grid.columnconfigure((0, 1, 2, 3), weight=1)

        # Card 1: Files Queued
        card1, self.stat_val_count, self.stat_sub_count = self._create_stat_card(
            stats_grid, "QUEUED", "0", "Ready to optimize", "📁", col=0
        )
        # Card 2: Total Saved
        card2, self.stat_val_saved, self.stat_sub_saved = self._create_stat_card(
            stats_grid, "SPACE SAVED", "0 KB", "Total reduction", "💾", col=1
        )
        # Card 3: Avg. Reduction
        card3, self.stat_val_pct, self.stat_sub_pct = self._create_stat_card(
            stats_grid, "SAVINGS RATE", "—%", "Average ratio", "📉", col=2
        )
        # Card 4: Export Folder
        card4, self.stat_val_folder, self.stat_sub_folder = self._create_stat_card(
            stats_grid, "DESTINATION", "Downloads", "Click to open ↗", "📂", col=3
        )
        card4.bind("<Button-1>", lambda e: self._open_output_dir())
        card4.configure(cursor="hand2")

    def _create_stat_card(self, parent, category: str, initial_val: str, subtext: str, icon_symbol: str, col: int):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_SURFACE,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        card.grid(row=0, column=col, padx=(0 if col == 0 else 6, 0 if col == 3 else 6), sticky="nsew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=10)

        # Top row: Category tag + Icon
        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x")

        ctk.CTkLabel(
            top_row,
            text=category,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        ctk.CTkLabel(
            top_row,
            text=icon_symbol,
            font=ctk.CTkFont(size=12),
            text_color=COLOR_ACCENT,
        ).pack(side="right")

        # Big Number Value
        lbl_val = ctk.CTkLabel(
            inner,
            text=initial_val,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        lbl_val.pack(fill="x", pady=(2, 0))

        # Subtext
        lbl_sub = ctk.CTkLabel(
            inner,
            text=subtext,
            font=ctk.CTkFont(size=10),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        lbl_sub.pack(fill="x")

        return card, lbl_val, lbl_sub

    def _build_action_bar(self, parent):
        action_bar = ctk.CTkFrame(parent, fg_color="transparent", height=46)
        action_bar.grid(row=2, column=0, sticky="ew")

        # Left: Quick Queue Add/Clear Buttons
        btn_add_files = ctk.CTkButton(
            action_bar,
            text="+ Add Images",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            border_color=COLOR_BORDER,
            border_width=1,
            text_color=COLOR_TEXT_PRIMARY,
            height=38,
            corner_radius=8,
            command=self._select_files,
        )
        btn_add_files.pack(side="left", padx=(0, 8))

        btn_add_folder = ctk.CTkButton(
            action_bar,
            text="📁 Add Folder",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            border_color=COLOR_BORDER,
            border_width=1,
            text_color=COLOR_TEXT_PRIMARY,
            height=38,
            corner_radius=8,
            command=self._select_folder,
        )
        btn_add_folder.pack(side="left", padx=(0, 8))

        btn_clear = ctk.CTkButton(
            action_bar,
            text="🗑 Clear",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=COLOR_DANGER_BG,
            text_color=COLOR_TEXT_MUTED,
            height=38,
            corner_radius=8,
            command=self._clear_queue,
        )
        btn_clear.pack(side="left")

        # Right: Primary Action Button (Electric Blue Accent)
        self.btn_optimize_all = ctk.CTkButton(
            action_bar,
            text="⚡ OPTIMIZE ALL IMAGES",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            height=40,
            corner_radius=8,
            command=self._start_optimization_thread,
        )
        self.btn_optimize_all.pack(side="right")

    # =========================================================================
    # QUEUE & DROP ZONE RENDERING
    # =========================================================================
    def _render_queue(self):
        # Clear children inside center_card
        for child in self.center_card.winfo_children():
            child.destroy()

        if not self.file_queue:
            self._render_empty_drop_zone()
        else:
            self._render_queue_list()

    def _render_empty_drop_zone(self):
        # Large interactive drop zone card
        self.empty_zone = ctk.CTkFrame(
            self.center_card,
            fg_color="transparent",
            corner_radius=10,
        )
        self.empty_zone.pack(fill="both", expand=True, padx=20, pady=20)

        # Dashed Border Box simulation using CTkFrame container
        drop_inner = ctk.CTkFrame(
            self.empty_zone,
            fg_color=COLOR_SURFACE_HOVER,
            corner_radius=12,
            border_width=2,
            border_color=COLOR_BORDER_FOCUS,
            cursor="hand2",
        )
        drop_inner.pack(fill="both", expand=True)

        center_content = ctk.CTkFrame(drop_inner, fg_color="transparent")
        center_content.place(relx=0.5, rely=0.5, anchor="center")

        lbl_icon = ctk.CTkLabel(
            center_content,
            text="📥",
            font=ctk.CTkFont(size=44),
        )
        lbl_icon.pack(pady=(0, 10))

        lbl_main = ctk.CTkLabel(
            center_content,
            text="Drop images or folders here",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
        )
        lbl_main.pack(pady=(0, 4))

        lbl_sub = ctk.CTkLabel(
            center_content,
            text="or click anywhere inside this box to browse files",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_SECONDARY,
        )
        lbl_sub.pack(pady=(0, 14))

        # Format chips
        chips_frame = ctk.CTkFrame(center_content, fg_color="transparent")
        chips_frame.pack()

        formats = ["PNG", "JPG", "WEBP", "BMP", "TIFF", "GIF"]
        for f in formats:
            chip = ctk.CTkFrame(
                chips_frame,
                fg_color=COLOR_BG_DARK,
                corner_radius=6,
                border_width=1,
                border_color=COLOR_BORDER,
            )
            chip.pack(side="left", padx=3)
            ctk.CTkLabel(
                chip,
                text=f,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=COLOR_TEXT_MUTED,
                padx=8,
                pady=2,
            ).pack()

        # Click event to browse files
        drop_inner.bind("<Button-1>", lambda e: self._select_files())
        lbl_icon.bind("<Button-1>", lambda e: self._select_files())
        lbl_main.bind("<Button-1>", lambda e: self._select_files())
        lbl_sub.bind("<Button-1>", lambda e: self._select_files())

    def _render_queue_list(self):
        # Header bar for the queue
        q_header = ctk.CTkFrame(self.center_card, fg_color="transparent", height=32)
        q_header.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            q_header,
            text=f"OPTIMIZATION QUEUE ({len(self.file_queue)})",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        # Scrollable container for rows
        self.queue_container = ctk.CTkScrollableFrame(
            self.center_card,
            fg_color="transparent",
            label_text="",
        )
        self.queue_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        is_multi = len(self.file_queue) > 1
        custom_base = self.custom_slug_input.get().strip()

        for idx, item in enumerate(self.file_queue):
            row_card = ctk.CTkFrame(
                self.queue_container,
                fg_color=COLOR_BG_DARK,
                border_color=COLOR_BORDER,
                border_width=1,
                corner_radius=8,
            )
            row_card.pack(fill="x", pady=4, padx=4)
            item["widget_frame"] = row_card

            row_inner = ctk.CTkFrame(row_card, fg_color="transparent")
            row_inner.pack(fill="both", expand=True, padx=12, pady=8)

            # 1. Thumbnail (40x40)
            thumb_img = item.get("thumbnail_ctk")
            if thumb_img:
                lbl_thumb = ctk.CTkLabel(row_inner, image=thumb_img, text="", width=40, height=40)
            else:
                lbl_thumb = ctk.CTkLabel(
                    row_inner,
                    text="🖼",
                    font=ctk.CTkFont(size=18),
                    width=40,
                    height=40,
                    fg_color=COLOR_SURFACE_HOVER,
                    corner_radius=6,
                )
            lbl_thumb.pack(side="left", padx=(0, 12))

            # 2. File Name & Dimensions / Format Metadata
            meta_box = ctk.CTkFrame(row_inner, fg_color="transparent")
            meta_box.pack(side="left", fill="both", expand=True)

            file_name = Path(item["path"]).name
            lbl_name = ctk.CTkLabel(
                meta_box,
                text=file_name,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w",
            )
            lbl_name.pack(anchor="w")

            meta_str = f"{item['format'].upper()} • {item['orig_w']}×{item['orig_h']} px • {format_bytes(item['orig_size'])}"
            lbl_details = ctk.CTkLabel(
                meta_box,
                text=meta_str,
                font=ctk.CTkFont(size=11),
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w",
            )
            lbl_details.pack(anchor="w")

            # 3. Target WebP Slug Preview
            if custom_base:
                if is_multi:
                    target_slug = f"{generate_slug(custom_base)}-{idx + 1}.webp"
                else:
                    target_slug = f"{generate_slug(custom_base)}.webp"
            else:
                target_slug = f"{generate_slug(Path(item['path']).stem)}.webp"

            lbl_slug = ctk.CTkLabel(
                row_inner,
                text=f"➔ {target_slug}",
                font=ctk.CTkFont(size=11, family="Consolas"),
                text_color=COLOR_ACCENT,
            )
            lbl_slug.pack(side="left", padx=16)
            item["lbl_slug"] = lbl_slug

            # 4. Status Badge Pill
            lbl_badge = ctk.CTkLabel(
                row_inner,
                text="Pending",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=COLOR_SURFACE_HOVER,
                text_color=COLOR_TEXT_SECONDARY,
                corner_radius=6,
                width=116,
                height=26,
            )
            lbl_badge.pack(side="left", padx=(0, 8))
            item["lbl_badge"] = lbl_badge
            self._update_queue_item_status(idx)

            # 5. Remove Item Button
            btn_del = ctk.CTkButton(
                row_inner,
                text="✕",
                width=26,
                height=26,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                hover_color=COLOR_DANGER_BG,
                text_color=COLOR_TEXT_MUTED,
                corner_radius=6,
                command=lambda i=idx: self._remove_queue_item(i),
            )
            btn_del.pack(side="right")

    # =========================================================================
    # EVENT HANDLERS & HELPERS
    # =========================================================================
    def _create_thumbnail(self, file_path: str) -> Optional[ctk.CTkImage]:
        """Safely generate a 40x40 cached thumbnail for queue display"""
        try:
            with Image.open(file_path) as img:
                img.thumbnail((40, 40), Image.Resampling.LANCZOS)
                thumb = img.convert("RGBA") if img.mode in ("RGBA", "LA") else img.convert("RGB")
                return ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
        except Exception:
            return None

    def _browse_output_dir(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir.get())
        if folder:
            self.output_dir.set(folder)
            self._update_dashboard_stats()

    def _open_output_dir(self):
        target = self.output_dir.get()
        if not target:
            return
        target_path = Path(target)
        if not target_path.exists():
            try:
                target_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create directory: {e}")
                return
        try:
            os.startfile(str(target_path))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open directory: {e}")

    def _on_quality_change(self, val):
        q = int(val)
        if self.lossless_val.get():
            self.lbl_quality_val.configure(text="Lossless Mode (100%)", text_color=COLOR_SUCCESS)
        else:
            tag = "Low Size" if q < 60 else ("Balanced Web" if q <= 85 else "High Quality")
            self.lbl_quality_val.configure(text=f"{q}% ({tag})", text_color=COLOR_ACCENT)

    def _apply_quality_preset(self, val: int):
        self.lossless_val.set(False)
        self.slider_quality.configure(state="normal")
        self.quality_val.set(val)
        self._on_quality_change(val)

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

    # Dynamic Aspect Ratio Logic
    def _on_width_edited(self, *args):
        if self.lock_aspect_updating or not self.keep_aspect_val.get():
            return
        w_str = self.width_var.get().strip()
        if not w_str:
            self.lock_aspect_updating = True
            self.height_var.set("")
            self.lock_aspect_updating = False
            return
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
        if not h_str:
            self.lock_aspect_updating = True
            self.width_var.set("")
            self.lock_aspect_updating = False
            return
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

    # Queue Data Actions
    def _on_drag_drop(self, event):
        files_raw = event.data
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

            thumb = self._create_thumbnail(p)
            item = {
                "path": p,
                "orig_w": info["width"],
                "orig_h": info["height"],
                "orig_size": info["file_size"],
                "format": info["format"],
                "status": "Pending",
                "result": None,
                "thumbnail_ctk": thumb,
                "widget_frame": None,
            }
            self.file_queue.append(item)
            new_items += 1

        if new_items > 0 and self.file_queue:
            first = self.file_queue[0]
            if first["orig_w"] > 0 and first["orig_h"] > 0:
                self.current_aspect_ratio = first["orig_w"] / first["orig_h"]

        self._render_queue()
        self._update_dashboard_stats()

    def _clear_queue(self):
        self.file_queue.clear()
        self.current_aspect_ratio = 16.0 / 9.0
        self._render_queue()
        self._update_dashboard_stats()
        self.progress_bar.set(0)

    def _remove_queue_item(self, idx: int):
        if 0 <= idx < len(self.file_queue):
            del self.file_queue[idx]
            if self.file_queue:
                first = self.file_queue[0]
                if first["orig_w"] > 0 and first["orig_h"] > 0:
                    self.current_aspect_ratio = first["orig_w"] / first["orig_h"]
            else:
                self.current_aspect_ratio = 16.0 / 9.0
            self._render_queue()
            self._update_dashboard_stats()

    def _update_queue_item_status(self, idx: int):
        if not (0 <= idx < len(self.file_queue)):
            return
        item = self.file_queue[idx]
        badge = item.get("lbl_badge")
        if not badge:
            return

        status = item.get("status", "Pending")
        if status == "Pending":
            badge.configure(text="Pending", fg_color=COLOR_SURFACE_HOVER, text_color=COLOR_TEXT_SECONDARY)
        elif status == "Processing":
            badge.configure(text="Processing...", fg_color=COLOR_ACCENT_BG, text_color=COLOR_ACCENT)
        elif status == "Done" and item.get("result"):
            res = item["result"]
            badge.configure(
                text=f"{format_bytes(res['opt_size'])} (-{res['savings_pct']:.1f}%)",
                fg_color=COLOR_SUCCESS_BG,
                text_color=COLOR_SUCCESS,
            )
        else:
            badge.configure(text="Error", fg_color=COLOR_DANGER_BG, text_color=COLOR_DANGER)

    def _refresh_queue_slug_display(self):
        if not self.file_queue:
            return
        custom_base = self.custom_slug_input.get().strip()
        is_multi = len(self.file_queue) > 1

        for idx, item in enumerate(self.file_queue):
            lbl_slug = item.get("lbl_slug")
            if not lbl_slug:
                continue
            if custom_base:
                if is_multi:
                    target_slug = f"{generate_slug(custom_base)}-{idx + 1}.webp"
                else:
                    target_slug = f"{generate_slug(custom_base)}.webp"
            else:
                target_slug = f"{generate_slug(Path(item['path']).stem)}.webp"
            lbl_slug.configure(text=f"➔ {target_slug}")

    def _update_dashboard_stats(self):
        total_count = len(self.file_queue)
        target_path = self.output_dir.get()
        target_name = Path(target_path).name or target_path

        # Truncate folder name if too long for card display
        if len(target_name) > 16:
            target_name = target_name[:14] + "…"

        if self.stat_val_folder:
            self.stat_val_folder.configure(text=target_name)

        if total_count == 0:
            if self.stat_val_count:
                self.stat_val_count.configure(text="0")
                self.stat_sub_count.configure(text="Ready to optimize")
            if self.stat_val_saved:
                self.stat_val_saved.configure(text="0 KB", text_color=COLOR_TEXT_PRIMARY)
            if self.stat_val_pct:
                self.stat_val_pct.configure(text="—%", text_color=COLOR_TEXT_PRIMARY)
            return

        done_items = [i for i in self.file_queue if i["status"] == "Done" and i["result"]]
        if done_items:
            orig_total = sum(i["result"]["orig_size"] for i in done_items)
            opt_total = sum(i["result"]["opt_size"] for i in done_items)
            saved_bytes = max(0, orig_total - opt_total)
            pct = (saved_bytes / orig_total * 100.0) if orig_total > 0 else 0.0

            if self.stat_val_count:
                self.stat_val_count.configure(text=f"{len(done_items)}/{total_count}")
                self.stat_sub_count.configure(text="Completed")
            if self.stat_val_saved:
                self.stat_val_saved.configure(text=format_bytes(saved_bytes), text_color=COLOR_SUCCESS)
            if self.stat_val_pct:
                self.stat_val_pct.configure(text=f"-{pct:.1f}%", text_color=COLOR_SUCCESS)
        else:
            total_bytes = sum(i["orig_size"] for i in self.file_queue)
            if self.stat_val_count:
                self.stat_val_count.configure(text=str(total_count))
                self.stat_sub_count.configure(text=f"{format_bytes(total_bytes)} queued")
            if self.stat_val_saved:
                self.stat_val_saved.configure(text="0 KB", text_color=COLOR_TEXT_PRIMARY)
            if self.stat_val_pct:
                self.stat_val_pct.configure(text="—%", text_color=COLOR_TEXT_PRIMARY)

    # =========================================================================
    # OPTIMIZATION WORKER THREAD
    # =========================================================================
    def _start_optimization_thread(self):
        if not self.file_queue:
            messagebox.showinfo("Information", "Please add at least one image to optimize!")
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.btn_optimize_all.configure(state="disabled", text="⏳ OPTIMIZING...")
        self.progress_bar.set(0)

        thread = threading.Thread(target=self._run_optimization, daemon=True)
        thread.start()

    def _run_optimization(self):
        out_dir = self.output_dir.get()
        quality = self.quality_val.get()
        lossless = self.lossless_val.get()
        strip_exif = self.strip_exif_val.get()
        keep_aspect = self.keep_aspect_val.get()

        w_val = int(self.width_var.get().strip()) if self.width_var.get().strip().isdigit() else None
        h_val = int(self.height_var.get().strip()) if self.height_var.get().strip().isdigit() else None

        custom_base = self.custom_slug_input.get().strip()
        is_multi = len(self.file_queue) > 1
        total = len(self.file_queue)

        for idx, item in enumerate(self.file_queue):
            item["status"] = "Processing"
            self.after(0, self._update_queue_item_status, idx)

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
            self.after(0, self._update_queue_item_status, idx)
            self.after(0, self._update_dashboard_stats)

        self.is_processing = False
        self.after(
            0,
            lambda: self.btn_optimize_all.configure(
                state="normal", text="⚡ OPTIMIZE ALL IMAGES"
            ),
        )
        self.after(0, self._on_batch_complete)

    def _on_batch_complete(self):
        messagebox.showinfo(
            "Optimization Complete",
            f"All images have been successfully processed!\nSaved to: {self.output_dir.get()}",
        )


def main():
    app = WebPOptimaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
