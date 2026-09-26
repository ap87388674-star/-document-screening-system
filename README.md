# AI document screening — backend

FastAPI backend implementing the four screening modules for real, plus a
risk-scoring engine. Designed to sit behind the HTML prototype you already
have — see "Wiring up the frontend" below.

## 1. Install system dependency: Tesseract OCR

`pytesseract` is a wrapper — it needs the actual Tesseract binary installed.

- **macOS**: `brew install tesseract`
- **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
- **Windows**: install from https://github.com/UB-Mannheim/tesseract/wiki, then
  add the install folder to your PATH (or set
  `pytesseract.pytesseract.tesseract_cmd` in `ocr_module.py`).

## 2. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## 3. Run the server

```bash
uvicorn main:app --reload --port 8000
```

Interactive API docs (Swagger UI) at `http://localhost:8000/docs` — you can
upload test images and try every endpoint from the browser without writing
any client code.

## 4. Test it

```bash
curl -X POST http://localhost:8000/api/screen \
  -F "document=@sample_passport.jpg" \
  -F "doc_photo=@doc_face.jpg" \
  -F "live_photo=@selfie.jpg"
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| POST | `/api/ocr` | Module 1 — OCR + field extraction |
| POST | `/api/validate` | Module 2 — format/expiry/MRZ checksum/blacklist |
| POST | `/api/tamper-detection` | Module 3 — ELA heatmap + metadata flags |
| POST | `/api/face-match` | Module 4 — document photo vs. live capture |
| POST | `/api/screen` | Runs all four modules + risk score in one call |

## Wiring up the frontend

Replace the client-side pipeline functions in the HTML prototype with a
single fetch to `/api/screen`:

```js
async function runPipelineViaBackend(docFile, docFaceFile, liveFaceFile){
  const form = new FormData();
  form.append('document', docFile);
  if(docFaceFile) form.append('doc_photo', docFaceFile);
  if(liveFaceFile) form.append('live_photo', liveFaceFile);

  const res = await fetch('http://localhost:8000/api/screen', {
    method: 'POST',
    body: form
  });
  const report = await res.json();
  // report.ocr.fields, report.validation.flags, report.tampering.heatmap_image_base64,
  // report.face_verification.similarity_percent, report.risk.risk_score
  return report;
}
```

The ELA heatmap comes back as `heatmap_image_base64` — render it directly:
`<img src="data:image/png;base64,${report.tampering.heatmap_image_base64}">`

## Known limitations (and how to fix them for production)

- **OCR field parsing** is regex-based, tuned to a fictional sample passport.
  Swap in a real MRZ parser or a cloud ID-document model — see API table below.
- **Face verification** uses OpenCV Haar-cascade + histogram correlation —
  workable for a demo, not biometric-grade. Swap for Rekognition/Face API/DeepFace.
- **Blacklist** is a local SQLite table with two fake entries — real deployments
  integrate with INTERPOL I-24/7 SLTD (law-enforcement only) or a national registry.
- **CORS is wide open** (`allow_origins=["*"]`) for local demo convenience —
  restrict it before deploying anywhere reachable.

---

## Full API reference — what to use per module in production

### Module 1 — OCR extraction
| Type | Option | Notes |
|---|---|---|
| Open source | Tesseract OCR (used here) | Free, offline, needs tuning for ID layouts |
| Open source | PaddleOCR | Strong multilingual + MRZ support |
| Open source | PassportEye / `mrz` (Python) | Purpose-built for MRZ parsing + checksum |
| Cloud | AWS Textract — `AnalyzeID` | Purpose-built for passports/driver's licenses |
| Cloud | Azure AI Document Intelligence — prebuilt ID model | Structured ID field extraction |
| Cloud | Google Cloud Vision — Document Text Detection | General OCR, needs custom field parsing |
| Cloud | OCR.space | Simple REST API, good for quick prototypes |

### Module 2 — Document validation
| Type | Option | Notes |
|---|---|---|
| Algorithm | ICAO 9303 MRZ checksum (implemented here) | Standard for passport/visa check digits |
| Library | `mrz` (npm/PyPI) | Standardized MRZ field + format validation |
| Database | INTERPOL I-24/7 SLTD | Stolen/Lost Travel Documents — law enforcement only |
| Database | National passport-issuing-authority APIs | Country-specific, usually gov-restricted |

### Module 3 — Tampering detection
| Type | Option | Notes |
|---|---|---|
| Algorithm | Error Level Analysis (implemented here) | Recompression diff, real forensic technique |
| Library | Pillow / ExifTool | Metadata analysis (editing software signatures) |
| Model | CASIA-trained forgery-detection CNN | Fine-tune a pretrained model on the CASIA tampering dataset |
| Model hub | Hugging Face image-forgery / deepfake-detection models | Pretrained starting points |
| Commercial (bundles OCR+tamper+face) | Onfido, Jumio, Au10tix, IDnow | Industry-standard KYC/AML document verification platforms |

### Module 4 — Face verification
| Type | Option | Notes |
|---|---|---|
| Prototype | OpenCV Haar cascade + histogram (implemented here) | No dlib/cmake build needed |
| Open source | `face_recognition` (dlib-based) | More accurate, needs dlib compiled |
| Open source | DeepFace (wraps FaceNet/ArcFace/VGG-Face) | Good offline accuracy, heavier install |
| Cloud | AWS Rekognition — `CompareFaces` | Production-grade face match |
| Cloud | Azure Face API — `Verify` | Production-grade face match + liveness options |
| Cloud | Face++ (Megvii) — Compare API | Alternative commercial option |
| Liveness | Azure Face Liveness Detection | Anti-spoofing (prevents photo-of-a-photo attacks) |
