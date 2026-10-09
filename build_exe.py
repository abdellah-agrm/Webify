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

    # Step 1: Pre-flight check - verify dist/Webify.exe is not locked by a running instance
    dist_exe = project_dir / "dist" / "Webify.exe"
    if dist_exe.exists():
        try:
            with open(dist_exe, "a+"):
                pass
        except PermissionError:
            print("\n" + "=" * 65)
            print("[ERROR] 'dist/Webify.exe' is currently running or locked by Windows!")
            print("Please close the running Webify app and re-run python build_exe.py.")
            print("=" * 65 + "\n")
            return

    # Step 2: Ensure PyInstaller is installed
    try:
        import PyInstaller
        print(f"[OK] PyInstaller found version {PyInstaller.__version__}")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Step 3: Ensure CustomTkinter, TkinterDnD2, and Tcl/Tk assets are bundled correctly
    import customtkinter
    import tkinterdnd2

    ctk_path = Path(customtkinter.__file__).parent.resolve()
    dnd_path = Path(tkinterdnd2.__file__).parent.resolve()

    # Safely locate Tcl/Tk data directory if available
    tcl_candidates = [
        Path(sys.base_prefix) / "tcl",
        Path(sys.prefix) / "tcl",
        Path(sys.executable).parent / "tcl",
    ]
    tcl_path = next((p for p in tcl_candidates if p.exists()), None)

    print("Building standalone executable using PyInstaller...")

    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=Webify",
        "--icon=app_icon.ico",
        f"--paths={project_dir}",
        f"--add-data={ctk_path};customtkinter/",
        f"--add-data={dnd_path};tkinterdnd2/",
        "--add-data=generative-image.png;.",
        "--add-data=app_icon.ico;.",
        "--hidden-import=PIL.WebPImagePlugin",
        "--hidden-import=tkinterdnd2",
        "--hidden-import=customtkinter",
        "--clean",
        "app.py"
    ]

    if tcl_path and tcl_path.exists():
        cmd.extend([
            f"--add-data={tcl_path};_tcl_data/",
            f"--add-data={tcl_path};_tk_data/",
        ])

    print("Executing command:", " ".join(cmd))
    res = subprocess.run(cmd)

    if res.returncode == 0:
        exe_path = project_dir / "dist" / "Webify.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 50)
            print("[SUCCESS] Webify executable built successfully:")
            print(f"   Location: {exe_path}")
            print(f"   Size: {size_mb:.2f} MB")
            print("=" * 50)
        else:
            print("Build completed, but output executable was not found.")
    else:
        print(f"[ERROR] Build failed with return code {res.returncode}")


if __name__ == "__main__":
    main()
