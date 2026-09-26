"""
Module 5 — Risk Scoring Engine

Combines the three upstream signals into one explainable 0-100 score.
Weights are a starting point — tune them against labeled data once you
have real cases to validate against.
"""


def compute_risk(
    tamper_score: int,
    face_similarity: int,
    validation_score: int,
    face_detected_in_document: bool = True,
    face_detected_in_live_capture: bool = True,
) -> dict:
    face_mismatch = 100 - face_similarity
    risk = round(tamper_score * 0.4 + face_mismatch * 0.3 + validation_score * 0.3)
    risk = max(0, min(100, risk))

    escalated = False
    faces_confidently_detected = face_detected_in_document and face_detected_in_live_capture
    # A confirmed face mismatch is a critical impersonation signal on its own —
    # don't let it get diluted into "medium risk" just because the document
    # itself looks otherwise clean. Only escalate when both faces were
    # actually detected (not the whole-image fallback comparison), since an
    # undetected-face similarity score isn't trustworthy enough to act on.
    if faces_confidently_detected and face_similarity < 40 and risk < 70:
        risk = 70
        escalated = True

    if risk < 30:
        verdict = "low_risk"
        summary = "No strong indicators of forgery detected. Clear to proceed."
    elif risk < 60:
        verdict = "medium_risk"
        summary = "Some indicators present. Route to a border officer for secondary inspection."
    else:
        verdict = "high_risk"
        summary = "Multiple fraud indicators detected. Flag for mandatory secondary inspection."

    if escalated:
        summary = "Face verification failed to match a confidently-detected face — flagged as likely impersonation. " + summary

    return {
        "risk_score": risk,
        "verdict": verdict,
        "summary": summary,
        "breakdown": {
            "tamper_score": tamper_score,
            "face_mismatch": face_mismatch,
            "validation_score": validation_score,
        },
    }
