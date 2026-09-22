# REST API Reference

The RAG POC exposes a REST API powered by **FastAPI**. Interactive Swagger documentation is automatically available at `http://127.0.0.1:8000/docs` when the application is running.

---

## Base URL
```
http://127.0.0.1:8000
```

---

## Endpoints Overview

| Method | Path | Description |
|:---|:---|:---|
| `POST` | `/api/query` | Ask a question and receive a grounded answer with citations |
| `POST` | `/api/ingest` | Upload new documents or trigger processing of pending documents |
| `GET` | `/api/documents` | List all documents and their ingestion status |
| `DELETE` | `/api/documents/{file_name}` | Delete a document and purge its chunks from ChromaDB |
| `GET` | `/api/stats` | Retrieve system summary statistics |
| `GET` | `/api/health` | Service health and model configuration check |
| `GET` | `/` | Web UI Chat Interface (HTML) |
| `GET` | `/documents` | Web UI Document Management Dashboard (HTML) |

---

## 1. Query Documents

### `POST /api/query`
Submits a natural language query, performs semantic vector retrieval against ChromaDB, generates an answer via low-level `gemma-4-26b-a4b-it` (with automatic fallback to `gemini-3-flash-preview`, `gemini-3.5-flash`, or `gemini-3.6-flash`), and returns the answer with deduplicated source citations.

#### Request Headers
```http
Content-Type: application/json
```

#### Request Body Schema (`QueryRequest`)
```json
{
  "question": "string (required, min length: 1)"
}
```

#### Example Request
```bash
curl -X POST "http://127.0.0.1:8000/api/query" \
     -H "Content-Type: application/json" \
     -d '{"question": "What is the refund policy for enterprise customers?"}'
```

#### Response Body Schema (`QueryResponse`)
```json
{
  "answer": "According to the Enterprise Agreement (page 7), enterprise customers may request a prorated refund within thirty (30) days of initial purchase or renewal...",
  "sources": [
    {
      "file_name": "enterprise_sla.md",
      "page_number": 1,
      "section_heading": "2. Refund and Cancellation Policy",
      "distance": 0.1824
    }
  ],
  "query": "What is the refund policy for enterprise customers?",
  "model": "gemma-4-26b-a4b-it",
  "chunks_retrieved": 5
}
```

#### Status Codes
- `200 OK`: Query answered successfully.
- `422 Unprocessable Entity`: Missing or empty `question` field.

---

## 2. Ingest Documents

### `POST /api/ingest`
Uploads one or more files to `data/documents/` and immediately ingests them into ChromaDB. If called without any files, it scans `data/documents/` and processes all un-ingested or recently modified files.

#### Request Headers
```http
Content-Type: multipart/form-data
```

#### Request Body
- `files` *(optional, file or array of files)*: Document files (`.pdf`, `.docx`, `.xlsx`, `.png`, `.jpg`, `.jpeg`, `.txt`, `.md`).

#### Example Request (Upload Files)
```bash
curl -X POST "http://127.0.0.1:8000/api/ingest" \
     -F "files=@C:/Documents/quarterly_report.pdf" \
     -F "files=@C:/Documents/pricing_sheet.xlsx"
```

#### Example Request (Process All Pending)
```bash
curl -X POST "http://127.0.0.1:8000/api/ingest"
```

#### Response Body Schema (`IngestResponse`)
```json
{
  "processed": 2,
  "chunks": 34,
  "errors": []
}
```

If any files fail during processing:
```json
{
  "processed": 1,
  "chunks": 18,
  "errors": [
    {
      "file": "corrupted_file.pdf",
      "error": "Docling failed to parse PDF structure: Stream has ended unexpectedly"
    }
  ]
}
```

---

## 3. List Documents

### `GET /api/documents`
Returns metadata and ingestion status for all files located in the `data/documents/` directory.

#### Example Request
```bash
curl -X GET "http://127.0.0.1:8000/api/documents"
```

#### Response Body Schema (`list[DocumentInfo]`)
```json
[
  {
    "name": "enterprise_sla.md",
    "path": "C:\\MyProjects\\RAG\\data\\documents\\enterprise_sla.md",
    "extension": ".md",
    "size_bytes": 1104,
    "modified_at": "2026-09-22T12:52:11.234567+00:00",
    "ingested": true,
    "ingested_at": "2026-09-22T13:04:29.123456+00:00",
    "chunk_count": 4
  },
  {
    "name": "quarterly_financials.xlsx",
    "path": "C:\\MyProjects\\RAG\\data\\documents\\quarterly_financials.xlsx",
    "extension": ".xlsx",
    "size_bytes": 5642,
    "modified_at": "2026-09-22T13:03:07.890123+00:00",
    "ingested": true,
    "ingested_at": "2026-09-22T13:04:30.456789+00:00",
    "chunk_count": 2
  }
]
```

---

## 4. Delete Document

### `DELETE /api/documents/{file_name}`
Deletes a document from the filesystem (`data/documents/{file_name}`), purges all of its associated vector chunks from ChromaDB, and removes its entry from the manifest.

#### Path Parameters
- `file_name` *(string, required)*: The filename to delete (e.g., `enterprise_sla.md`).

#### Example Request
```bash
curl -X DELETE "http://127.0.0.1:8000/api/documents/enterprise_sla.md"
```

#### Response Body
```json
{
  "message": "Deleted 'enterprise_sla.md'",
  "chunks_removed": 4
}
```

#### Status Codes
- `200 OK`: File and associated vector chunks successfully removed.
- `404 Not Found`: If `file_name` does not exist in `data/documents/`.

---

## 5. System Statistics

### `GET /api/stats`
Returns an overview of files, indexing progress, and chunk counts.

#### Example Request
```bash
curl -X GET "http://127.0.0.1:8000/api/stats"
```

#### Response Body Schema (`StatsResponse`)
```json
{
  "total_files": 4,
  "ingested_files": 4,
  "pending_files": 0,
  "total_chunks": 18
}
```

---

## 6. Health Check

### `GET /api/health`
Verifies server health, loaded Gemini models, and connection status.

#### Example Request
```bash
curl -X GET "http://127.0.0.1:8000/api/health"
```

#### Response Body Schema (`HealthResponse`)
```json
{
  "status": "ok",
  "gemini_model": "gemma-4-26b-a4b-it",
  "embed_model": "gemini-embedding-2",
  "documents_dir": "C:\\MyProjects\\RAG\\data\\documents",
  "total_chunks": 18
}
```
