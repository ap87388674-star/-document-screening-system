"""
Module 4 — Face Verification

Lightweight OpenCV-only implementation (Haar cascade face detection +
histogram/template correlation) so it runs with just `opencv-python`,
no dlib/cmake build step. This is a workable prototype signal, but for
real biometric accuracy and liveness detection, swap `compare_faces`
for AWS Rekognition CompareFaces, Azure Face API Verify, or a
DeepFace/ArcFace embedding comparison — see README.
"""
import os
import cv2
import numpy as np
from PIL import Image

# Prefer a cascade file bundled right next to this script (see README) over
# the one inside the installed OpenCV package — some Windows installs end up
# with an empty cv2/data folder, so this sidesteps that entirely.
_LOCAL_CASCADE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haarcascade_frontalface_default.xml")
_PACKAGE_CASCADE = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_CASCADE_PATH = _LOCAL_CASCADE if os.path.exists(_LOCAL_CASCADE) else _PACKAGE_CASCADE

_face_cascade = cv2.CascadeClassifier(_CASCADE_PATH)
_CASCADE_OK = not _face_cascade.empty()
if not _CASCADE_OK:
    print(
        f"WARNING: face-detection cascade file did not load from {_CASCADE_PATH!r}. "
        "Face verification will fall back to comparing full images instead of "
        "cropped faces. Fix: download haarcascade_frontalface_default.xml from "
        "https://github.com/opencv/opencv/raw/refs/heads/4.x/data/haarcascades/haarcascade_frontalface_default.xml "
        "and save it directly into this backend folder (next to main.py), then restart the server."
    )


def _extract_face(pil_image: Image.Image, size=(200, 200)):
    arr = cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)

    faces = ()
    if _CASCADE_OK:
        try:
            faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        except cv2.error:
            faces = ()

    if len(faces) == 0:
        face_gray = cv2.resize(gray, size)
        found = False
    else:
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        face_gray = cv2.resize(gray[y:y + h, x:x + w], size)
        found = True

    return face_gray, found


def compare_faces(doc_image: Image.Image, live_image: Image.Image) -> dict:
    face1, found1 = _extract_face(doc_image)
    face2, found2 = _extract_face(live_image)

    hist1 = cv2.calcHist([face1], [0], None, [256], [0, 256])
    hist2 = cv2.calcHist([face2], [0], None, [256], [0, 256])
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    hist_score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

    result = cv2.matchTemplate(face1.astype(np.float32), face2.astype(np.float32), cv2.TM_CCOEFF_NORMED)
    template_score = float(result.max())

    similarity = max(0, min(100, round(((hist_score + template_score) / 2) * 100)))

    return {
        "similarity_percent": similarity,
        "face_detected_in_document": found1,
        "face_detected_in_live_capture": found2,
        "note": (
            "OpenCV histogram + template correlation heuristic — for production "
            "accuracy use AWS Rekognition CompareFaces, Azure Face API Verify, or "
            "DeepFace/ArcFace embeddings with liveness detection."
        ),
    }
