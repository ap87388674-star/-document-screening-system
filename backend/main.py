"""
AI-Based Fake Identity & Document Screening System — backend API

Run with:  uvicorn main:app --reload --port 8000
Docs at:   http://localhost:8000/docs
"""
import base64
import io
from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from ocr_module import extract_text, parse_fields
from validation_module import validate_document
from tamper_module import error_level_analysis, check_metadata
from face_module import compare_faces
from risk_module import compute_risk
from db import init_db, get_blacklist, log_scan

app = FastAPI(title="AI Document Screening API", version="1.0.0")

# Demo-only: allow any origin so the local HTML frontend can call this API
# directly from a file:// or localhost page. Lock this down to your real
# frontend's origin before deploying anywhere.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


def _load(file: UploadFile) -> Image.Image:
    return Image.open(io.BytesIO(file.file.read()))


def _img_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/ocr")
async def ocr_endpoint(document: UploadFile = File(...)):
    image = _load(document)
    raw_text = extract_text(image)
    fields = parse_fields(raw_text)
    return {"raw_text": raw_text, "fields": fields}


@app.post("/api/validate")
async def validate_endpoint(fields: dict = Body(...)):
    blacklist = get_blacklist()
    return validate_document(fields, blacklist)


@app.post("/api/tamper-detection")
async def tamper_endpoint(document: UploadFile = File(...)):
    image = _load(document)
    ela_result = error_level_analysis(image)
    meta_result = check_metadata(image)
    return {
        "tamper_score": ela_result["tamper_score"],
        "avg_error_level": ela_result["avg_error_level"],
        "heatmap_image_base64": _img_to_b64(ela_result["heatmap_image"]),
        "metadata_flags": meta_result["flags"],
    }


@app.post("/api/face-match")
async def face_match_endpoint(doc_photo: UploadFile = File(...), live_photo: UploadFile = File(...)):
    doc_img = _load(doc_photo)
    live_img = _load(live_photo)
    return compare_faces(doc_img, live_img)


@app.post("/api/screen")
async def screen_endpoint(
    document: UploadFile = File(...),
    doc_photo: UploadFile = File(None),
    live_photo: UploadFile = File(None),
):
    """Full pipeline in one call — this is what the frontend's 'Run screening
    pipeline' button should hit instead of doing everything client-side."""
    doc_image = _load(document)

    raw_text = extract_text(doc_image)
    fields = parse_fields(raw_text)

    blacklist = get_blacklist()
    validation = validate_document(fields, blacklist)

    ela_result = error_level_analysis(doc_image)
    meta_result = check_metadata(doc_image)

    if doc_photo is not None and live_photo is not None:
        face_result = compare_faces(_load(doc_photo), _load(live_photo))
    else:
        face_result = {
            "similarity_percent": 50,
            "note": "No face photos supplied — neutral score used.",
        }

    risk = compute_risk(
        tamper_score=ela_result["tamper_score"],
        face_similarity=face_result["similarity_percent"],
        validation_score=validation["validation_score"],
        face_detected_in_document=face_result.get("face_detected_in_document", False),
        face_detected_in_live_capture=face_result.get("face_detected_in_live_capture", False),
    )

    log_scan(fields.get("passport_number"), risk["risk_score"], risk["verdict"])

    return {
        "ocr": {"raw_text": raw_text, "fields": fields},
        "validation": validation,
        "tampering": {
            "tamper_score": ela_result["tamper_score"],
            "avg_error_level": ela_result["avg_error_level"],
            "heatmap_image_base64": _img_to_b64(ela_result["heatmap_image"]),
            "metadata_flags": meta_result["flags"],
        },
        "face_verification": face_result,
        "risk": risk,
    }
