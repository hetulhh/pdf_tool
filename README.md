# pdf_tool

A lightweight Flask PDF conversion and manipulation API for Render.

## Features

### Conversion
| Endpoint | Description |
|---|---|
| `POST /pdf/to-excel` | Convert PDF to `.xlsx` |
| `POST /pdf/to-word` | Convert PDF to `.docx` |
| `POST /pdf/to-text` | Extract PDF text as `.txt` |
| `POST /pdf/metadata` | Return PDF metadata and page dimensions |

### Manipulation *(new)*
| Endpoint | Description |
|---|---|
| `POST /pdf/merge` | Merge multiple PDFs into one |
| `POST /pdf/split` | Split a PDF into page-range segments (returned as `.zip`) |
| `POST /pdf/rotate` | Rotate all or specific pages |
| `POST /pdf/compress` | Losslessly compress a PDF |

### Async job queue *(new)*
| Endpoint | Description |
|---|---|
| `GET /jobs/<job_id>` | Poll job status |
| `GET /jobs/<job_id>/result` | Download result when `status == "done"` |
| `GET /jobs` | List all in-memory jobs |

---

## Authentication

All endpoints require an `X-API-Key` header matching the `PDF_API_KEY` environment variable.

---

## Upload formats

Send a PDF as one of:
- `multipart/form-data` with field name `file`
- `application/json` with key `pdf_base64` (base64 string)
- Raw binary body

---

## Async mode

Append `?async=true` to any manipulation or conversion endpoint.  
The server returns **202 Accepted** immediately with a job ID:

```json
{
  "job_id": "3f2a...",
  "status": "pending",
  "status_url": "/jobs/3f2a...",
  "result_url": "/jobs/3f2a.../result"
}
```

Poll `GET /jobs/<job_id>` until `status` is `done` or `failed`, then fetch the file from `GET /jobs/<job_id>/result`.

Jobs are kept in memory for **30 minutes** after completion and then automatically reaped.

---

## Endpoint reference

### POST /pdf/merge

Send **multiple** PDFs to merge in order.

**multipart/form-data** (multiple `file` fields):
```bash
curl -X POST "http://localhost:10000/pdf/merge?filename=merged.pdf" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@doc1.pdf" \
  -F "file=@doc2.pdf" \
  --output merged.pdf
```

**JSON** (array of base64 strings):
```bash
curl -X POST "http://localhost:10000/pdf/merge" \
  -H "X-API-Key: $PDF_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"files": ["<base64_pdf_1>", "<base64_pdf_2>"]}' \
  --output merged.pdf
```

Response headers: `X-Total-Pages`, `X-Documents-Merged`

---

### POST /pdf/split

Split a PDF by page ranges. Returns a `.zip` containing one PDF per range.

```bash
curl -X POST "http://localhost:10000/pdf/split?ranges=1-3,5-7" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@document.pdf" \
  --output parts.zip
```

**JSON body**:
```json
{ "ranges": [[1, 3], [5, 7]] }
```

Ranges are **1-based and inclusive**. A single page is written as `4-4` or `4`.  
Response header: `X-Parts`

---

### POST /pdf/rotate

```bash
# Rotate all pages 90°
curl -X POST "http://localhost:10000/pdf/rotate?angle=90" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@document.pdf" \
  --output rotated.pdf

# Rotate only pages 1 and 3 by 180°
curl -X POST "http://localhost:10000/pdf/rotate?angle=180&pages=1,3" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@document.pdf" \
  --output rotated.pdf
```

**Query params**:
- `angle` — required; 90, 180, or 270
- `pages` — optional comma-separated 1-based page numbers; omit to rotate all

Response headers: `X-Pages-Rotated`, `X-Angle`

---

### POST /pdf/compress

```bash
curl -X POST "http://localhost:10000/pdf/compress?filename=small.pdf" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@document.pdf" \
  --output small.pdf
```

Response headers: `X-Original-Size`, `X-Compressed-Size`, `X-Savings-Percent`

> **Note**: Compression is lossless (stream re-compression + unused object removal).  
> Image downsampling (for bigger gains) requires `pikepdf` and is not included by default.

---

### GET /jobs/<job_id>

```bash
curl -H "X-API-Key: $PDF_API_KEY" \
  "http://localhost:10000/jobs/3f2a..."
```

```json
{
  "id": "3f2a...",
  "status": "done",
  "created_at": 1718000000.0,
  "updated_at": 1718000005.3,
  "content_type": "application/pdf",
  "filename": "merged.pdf",
  "headers": { "X-Total-Pages": "12" },
  "error": null,
  "status_url": "/jobs/3f2a...",
  "result_url": "/jobs/3f2a.../result"
}
```

**Status values**: `pending` → `running` → `done | failed`

---

### GET /jobs/<job_id>/result

Downloads the file when `status == "done"`. Returns 202 if still processing, 500 if failed.

```bash
curl -H "X-API-Key: $PDF_API_KEY" \
  "http://localhost:10000/jobs/3f2a.../result" \
  --output result.pdf
```

---

## Health check

```bash
GET /health   →  { "status": "ok" }
```

---

## Deployment (Render)

The `render.yaml` is pre-configured. Set `PDF_API_KEY` manually in the Render dashboard.

Generate a key locally:
```bash
python main.py genkey
```

### Concurrency note
The job queue runs up to **4 background threads** inside the gunicorn worker. For very large files or high concurrency, increase `--workers` in `render.yaml` or migrate the queue to Redis + Celery.