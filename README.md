"# pdf_tool

A lightweight Flask PDF conversion API for Render.

## Features

- `POST /pdf/to-excel` — convert a PDF to `.xlsx`
- `POST /pdf/to-word` — convert a PDF to `.docx`
- `POST /pdf/to-text` — extract PDF text as `.txt`
- `POST /pdf/metadata` — return PDF metadata and page dimensions

## API Usage

### Authentication

All `/pdf/*` endpoints require an `X-API-Key` header matching the `PDF_API_KEY` environment variable.

### Upload formats

Send the PDF as one of:

- `multipart/form-data` with field name `file`
- `application/json` with key `pdf_base64`
- raw binary body

### Optional filename override

You can provide `filename` as a query parameter or JSON body field to customize the downloaded file name.

### Example: PDF → Excel

```bash
curl -X POST "http://localhost:10000/pdf/to-excel?filename=report.xlsx" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@document.pdf" --output report.xlsx
```

### Example: PDF → Text

```bash
curl -X POST "http://localhost:10000/pdf/to-text?filename=extracted.txt" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@document.pdf" --output extracted.txt
```

### Example: PDF metadata

```bash
curl -X POST "http://localhost:10000/pdf/metadata" \
  -H "X-API-Key: $PDF_API_KEY" \
  -F "file=@document.pdf"
```

## Health check

- `GET /health` — returns `{ "status": "ok" }`
" 
