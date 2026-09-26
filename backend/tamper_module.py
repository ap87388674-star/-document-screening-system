"""
Module 3 — Tampering Detection (core AI innovation)

Real Error Level Analysis (ELA): re-compress the image at a known JPEG
quality and diff it against the original. Regions that were pasted in or
edited after the original capture re-compress differently and light up
in the heatmap — a standard forensic technique, not a mocked score.

Also does basic EXIF metadata inspection for editing-software signatures.

For production, add a trained CNN forgery classifier (fine-tune on the
CASIA tampering dataset) alongside this signal.
"""
import io
import numpy as np
from PIL import Image, ExifTags


def error_level_analysis(image: Image.Image, quality: int = 85, amplify: int = 12) -> dict:
    image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer)

    orig_arr = np.asarray(image).astype(np.int16)
    comp_arr = np.asarray(recompressed).astype(np.int16)
    diff = np.abs(orig_arr - comp_arr)

    avg_diff = float(diff.mean())
    tamper_score = min(100, round(avg_diff * 18))

    heat = np.clip(diff.mean(axis=2) * amplify, 0, 255).astype(np.uint8)
    heatmap_img = Image.fromarray(heat, mode="L").convert("RGB")

    return {
        "tamper_score": tamper_score,
        "avg_error_level": round(avg_diff, 3),
        "heatmap_image": heatmap_img,
    }


def check_metadata(image: Image.Image) -> dict:
    exif_data = {}
    try:
        raw_exif = image.getexif()
        for tag_id, value in raw_exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            exif_data[str(tag)] = str(value)
    except Exception:
        pass

    flags = []
    software = exif_data.get("Software", "")
    if any(tool in software for tool in ["Photoshop", "GIMP", "Paint.NET"]):
        flags.append(f"Image metadata shows editing software: {software}")
    if not exif_data:
        flags.append("No EXIF metadata present (common for scans/screenshots, but also common after tools that strip metadata).")

    return {"exif": exif_data, "flags": flags}
