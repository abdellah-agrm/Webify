"""
WebP Optima Pro - Optimization Engine
Handles image loading, aspect ratio calculation, LANCZOS high-quality resizing,
EXIF orientation auto-rotation, RGBA transparency preservation, and WebP compression via Pillow / libwebp.
"""
import os
import math
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageOps

from slugify import generate_slug


def calculate_aspect_dimensions(
    orig_w: int,
    orig_h: int,
    new_w: Optional[int] = None,
    new_h: Optional[int] = None,
    keep_aspect: bool = True
) -> Tuple[int, int]:
    """
    Calculates target width and height.
    If keep_aspect is True:
      - If new_w is provided, new_h is calculated proportionally.
      - If new_h is provided, new_w is calculated proportionally.
    """
    if orig_w <= 0 or orig_h <= 0:
        return (new_w or 100, new_h or 100)

    if not keep_aspect:
        final_w = new_w if new_w and new_w > 0 else orig_w
        final_h = new_h if new_h and new_h > 0 else orig_h
        return (final_w, final_h)

    # Keep aspect ratio
    aspect = orig_w / orig_h

    if new_w and new_w > 0 and (not new_h or new_h <= 0):
        final_w = new_w
        final_h = max(1, int(round(new_w / aspect)))
    elif new_h and new_h > 0 and (not new_w or new_w <= 0):
        final_h = new_h
        final_w = max(1, int(round(new_h * aspect)))
    elif new_w and new_w > 0 and new_h and new_h > 0:
        # Both provided while keeping aspect - scale to fit within bounds
        scale = min(new_w / orig_w, new_h / orig_h)
        final_w = max(1, int(round(orig_w * scale)))
        final_h = max(1, int(round(orig_h * scale)))
    else:
        final_w, final_h = orig_w, orig_h

    return (final_w, final_h)


def get_image_info(image_path: str) -> Optional[Dict[str, Any]]:
    """Quickly returns original width, height, format, and file size."""
    try:
        file_size = os.path.getsize(image_path)
        with Image.open(image_path) as img:
            # Handle orientation for dimension reporting
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            fmt = img.format or "UNKNOWN"
            return {
                "width": w,
                "height": h,
                "format": fmt,
                "file_size": file_size,
            }
    except Exception as e:
        return None


def optimize_to_webp(
    input_path: str,
    output_dir: str,
    custom_name: Optional[str] = None,
    target_w: Optional[int] = None,
    target_h: Optional[int] = None,
    keep_aspect: bool = True,
    quality: int = 82,
    lossless: bool = False,
    strip_exif: bool = True,
    compression_method: int = 6
) -> Dict[str, Any]:
    """
    Converts and optimizes an image file to WebP format.

    Returns a result dict with success status, file paths, dimensions, sizes, and savings.
    """
    input_file = Path(input_path)
    if not input_file.exists():
        return {"success": False, "error": f"File not found: {input_path}"}

    try:
        orig_size = input_file.stat().st_size

        with Image.open(input_path) as img:
            # Auto-rotate based on EXIF orientation tag before processing
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            orig_w, orig_h = img.size

            # Calculate target dimensions
            final_w, final_h = calculate_aspect_dimensions(
                orig_w, orig_h, target_w, target_h, keep_aspect
            )

            # Resize if dimensions differ
            if (final_w, final_h) != (orig_w, orig_h):
                img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)

            # Preserve mode/alpha channel
            if img.mode in ("P", "PA"):
                img = img.convert("RGBA")
            elif img.mode not in ("RGB", "RGBA", "L", "LA"):
                img = img.convert("RGB")

            # Determine target filename slug
            if custom_name and custom_name.strip():
                slug_base = generate_slug(custom_name.strip())
            else:
                # Use original filename without extension
                slug_base = generate_slug(input_file.stem)

            # Ensure output directory exists
            out_dir_path = Path(output_dir)
            out_dir_path.mkdir(parents=True, exist_ok=True)

            # Handle filename collisions in output directory
            dest_path = out_dir_path / f"{slug_base}.webp"
            counter = 1
            while dest_path.exists():
                # Avoid overwriting unless it's the exact same target path being re-optimized
                if dest_path.resolve() == input_file.resolve():
                    dest_path = out_dir_path / f"{slug_base}-opt.webp"
                    break
                dest_path = out_dir_path / f"{slug_base}-{counter}.webp"
                counter += 1

            # Prepare save options for WebP
            save_kw = {
                "format": "WEBP",
                "quality": max(1, min(100, quality)),
                "lossless": lossless,
                "method": compression_method,  # 0=fastest, 6=best compression
            }

            if not lossless:
                # Retain color exactness where possible
                save_kw["exact"] = False

            img.save(str(dest_path), **save_kw)

            opt_size = dest_path.stat().st_size
            savings_pct = max(0.0, ((orig_size - opt_size) / orig_size) * 100.0) if orig_size > 0 else 0.0

            return {
                "success": True,
                "input_path": str(input_file),
                "output_path": str(dest_path),
                "output_filename": dest_path.name,
                "orig_size": orig_size,
                "opt_size": opt_size,
                "savings_pct": savings_pct,
                "orig_dims": (orig_w, orig_h),
                "opt_dims": (final_w, final_h),
            }

    except Exception as e:
        return {
            "success": False,
            "input_path": input_path,
            "error": str(e)
        }


def format_bytes(size_in_bytes: int) -> str:
    """Formats bytes into human-readable string (KB, MB, etc)."""
    if size_in_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = int(math.floor(math.log(size_in_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_in_bytes / p, 2)
    return f"{s} {units[i]}"
