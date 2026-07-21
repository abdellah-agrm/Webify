# ⚡ Webify — Modern WebP Image Optimizer & SEO Slug Generator

<p align="center">
  <img src="generative-image.png" alt="Webify Logo" width="128" height="128">
</p>

**Webify** is a high-performance, dark-themed Windows desktop application for fast, quality-controlled WebP image conversion and automated SEO slug renaming.

Built with **Python**, **CustomTkinter**, and Google's official **`libwebp`** engine via **Pillow**, Webify allows web developers, designers, and content managers to compress images by up to 85%+ while maintaining visual quality.

---

## ✨ Features

- 🎨 **Modern Dark Mode Interface**: Built with CustomTkinter for a sleek, responsive slate-dark theme (`#14161f`).
- 🎚 **Dynamic Quality Bar (1% – 100%)**: Interactive quality slider with visual indicators (*Low Size*, *Balanced Web*, *High Quality*) + a 100% **Lossless Mode** toggle.
- 📐 **Aspect-Ratio Locked Resizing (px)**: Enter Width or Height in pixels—the other dimension automatically calculates in real-time to prevent image stretching or distortion. Quick presets available for `Original`, `1920px (FHD)`, `1280px (HD)`, and `800px (Web)`.
- 🔤 **Unicode SEO Slug Generator**: Automatically transforms titles and filenames with special characters, French accents, and symbols into clean web slugs.
  - *Example*: `"CONSTRUCTION & GROS ŒUVRE"` ➔ `"construction-and-gros-oeuvre.webp"`
- 📂 **Multi-File & Folder Drag & Drop**: Process single files, batch image selections, or entire folder trees with file queue drag-and-drop support.
- 📁 **Custom Export Directory**: Set custom output folders (default: `C:\Users\...\Downloads`) with a built-in **Open Folder** button.
- ⚡ **EXIF Metadata Stripping**: Strips camera metadata by default for maximum size reduction.
- 🚀 **Multi-Threaded Queue**: Background processing keeps the UI completely smooth and responsive during batch conversions.

---

## 💻 Installation & Usage

### Option 1: Standalone Executable (Windows)
1. Download `Webify.exe` from the `dist/` directory.
2. Double-click **`Webify.exe`** to launch immediately—no Python installation required!

### Option 2: Run from Python Source
1. Clone the repository:
   ```bash
   git clone https://github.com/abdellah-agrm/Webify.git
   cd Webify
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *or double-click `install_requirements.bat` on Windows.*
3. Run the application:
   ```bash
   python app.py
   ```
   *or double-click `run_app.bat` on Windows.*

---

## 🛠 Building the Executable

To compile a standalone `.exe` binary with embedded Tcl/Tk data assets and app icon:

```bash
python build_exe.py
```

The output binary will be generated at `dist/Webify.exe`.

---

## ⚙️ Tech Stack

- **GUI Framework**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- **Image Processing Engine**: [Pillow](https://python-pillow.org/) (Google `libwebp` library wrapper)
- **Drag & Drop**: [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2)
- **Packaging**: [PyInstaller](https://pyinstaller.org/)

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
