"""
Webify - Executable Build Script
Compiles the application into a standalone Windows binary (Webify.exe) with custom app icon.
"""
import os
import sys
import subprocess
from pathlib import Path


def main():
    print("=== Webify Builder ===")
    project_dir = Path(__file__).parent.resolve()
    os.chdir(project_dir)

    # Step 1: Ensure PyInstaller is installed
    try:
        import PyInstaller
        print(f"✓ PyInstaller found version {PyInstaller.__version__}")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Step 2: Ensure CustomTkinter, TkinterDnD2, and Tcl/Tk assets are bundled correctly
    import customtkinter
    import tkinterdnd2

    ctk_path = Path(customtkinter.__file__).parent.resolve()
    dnd_path = Path(tkinterdnd2.__file__).parent.resolve()
    tcl_path = Path(sys.base_prefix) / "tcl"

    print(f"Building standalone executable using PyInstaller...")

    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=Webify",
        "--icon=app_icon.ico",
        f"--add-data={ctk_path};customtkinter/",
        f"--add-data={dnd_path};tkinterdnd2/",
        f"--add-data={tcl_path};_tcl_data/",
        f"--add-data={tcl_path};_tk_data/",
        "--add-data=generative-image.png;.",
        "--add-data=app_icon.ico;.",
        "--clean",
        "app.py"
    ]

    print("Executing command:", " ".join(cmd))
    res = subprocess.run(cmd)

    if res.returncode == 0:
        exe_path = project_dir / "dist" / "Webify.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 50)
            print(f"🎉 SUCCESS! Webify executable built successfully:")
            print(f"   Location: {exe_path}")
            print(f"   Size: {size_mb:.2f} MB")
            print("=" * 50)
        else:
            print("Build completed, but output executable was not found.")
    else:
        print(f"❌ Build failed with return code {res.returncode}")


if __name__ == "__main__":
    main()
