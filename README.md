# RegLens AI

Compliance assistant for Indian businesses: ask questions over regulations and your own documents (with cited
sources), screen regulations against your business profile, run assessments, and track risks, reminders and reports.

```
frontend/   React 18 + TypeScript + Vite (hash-routed SPA, white + orange theme)
backend/    FastAPI + SQLAlchemy (SQLite by default) + BM25 retrieval, all routes under /api
```

## Run locally (two terminals)

```bash
# 1) backend  ->  http://localhost:8000  (docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000

# 2) frontend ->  http://localhost:5173  (Vite proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Five sample regulations (RBI KYC, RBI Digital Lending, DPDP Act, SEBI LODR, GST returns) are loaded on first start
from `backend/seed/regulations/`. They are short **demo summaries** - replace them with official texts.
Drop more `.txt` files there (see the header format in the existing ones) or upload PDFs under Regulations.

## Single-process / production

```bash
cd frontend && npm install && npm run build           # creates frontend/dist
cd ../backend && ENV=production JWT_SECRET=<long random> uvicorn app.main:app --port 8000
```
FastAPI serves `frontend/dist` itself, so one process serves UI and API. Or use Docker:
`JWT_SECRET=<long random> docker compose up --build` (data persists in a volume).

## Configuration (`backend/.env`)

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | Token signing key. **Required** when `ENV=production`. |
| `DATABASE_URL` | Default SQLite. Any SQLAlchemy URL works (e.g. `postgresql+psycopg://...`, add the driver). |
| `GOOGLE_CLIENT_ID` | Enables the Google sign-in button (frontend reads it from `/api/config`). |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Optional Claude answer generation, grounded only in retrieved passages. Anthropic is preferred when both providers are configured. |
| `GROQ_API_KEY` / `GROQ_MODEL` | Optional Groq answer generation. Without either provider key, Ask returns cited extractive answers from retrieved passages. |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_TIMEOUT_SECONDS` | Optional vector search and indexing. Vector writes are sent in batches; the timeout defaults to 60 seconds. SQL search remains available if Qdrant is unavailable. |
| `CORS_ORIGINS`, `MAX_UPLOAD_MB` | Allowed origins and upload size cap. |

## How data flows

1. **Ingest** - upload / URL / seed -> text extraction (pypdf, HTML or TXT) -> ~900-char overlapping chunks -> `chunks` table. URL import blocks private/loopback addresses (SSRF).
2. **Ask** - BM25 index per workspace (regulations + Library files switched on for Ask), cached in memory and invalidated on any change -> top passages -> answer with `[n]` citations -> logged to history. A "not found" answer is returned when passages don't cover the question.
3. **Business Profile -> applicability** - rule engine (`services/company.py`) decides Applicable / Not Applicable / Unknown per regulator and says what information is missing.
4. **Assessments** - one finding per regulation; scores recompute on every edit; evidence must be real Library files and must be admin-verified to close an evidence gap; completing freezes the assessment and files non-compliant findings into the **Risk register** (no duplicates) and raises an alert.
5. **Alerts** - reminders and overdue risks become alerts (idempotent). The sidebar badge polls `/api/alerts/unread-count`.
6. **Reports** - snapshot is stored at creation time and rendered to PDF on download.

Every query is scoped by workspace. The account `zairahussain27@gmail.com` is the sole administrator and the only account that can add regulations; uploaded regulations are private to that workspace. Seeded regulations are platform-wide and read-only.

## Tests

```bash
cd backend && pytest -q        # end-to-end API tests (auth, isolation, ask, uploads, assessments, reports, alerts)
cd frontend && npm test && npm run build
```

## Deploy to Render and Vercel

The repository includes a Render Blueprint at [`render.yaml`](./render.yaml) and a
Vercel SPA rewrite at [`frontend/vercel.json`](./frontend/vercel.json).

### 1. Deploy the backend on Render

1. Push this repository to GitHub and create a new **Web Service** in Render from
   `zairahussain27/reglens-ai`.
2. Select **Blueprint** if Render detects `render.yaml`, or configure the service
   manually with:
   - Root directory: `backend`
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/api/health`
3. Set these environment variables in Render:
   - `ENV=production`
   - `JWT_SECRET`: a long random value (the Blueprint can generate it)
   - `CORS_ORIGINS`: the final Vercel URL, such as
     `https://reglens-ai.vercel.app`
   - `GOOGLE_CLIENT_ID`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `QDRANT_URL`, and
     `QDRANT_API_KEY` only when those integrations are used.
4. Keep the persistent disk mounted at `/data`. The default SQLite database and
   uploaded files are stored there. For production scale, replace `DATABASE_URL`
   with a managed PostgreSQL URL and keep `/data` for uploaded files.

After deployment, verify `https://<render-service>.onrender.com/api/health`
returns `{"status":"ok"}` and copy the service URL.

### 2. Deploy the frontend on Vercel

1. Import `zairahussain27/reglens-ai` into Vercel.
2. Set **Root Directory** to `frontend`.
3. Vercel should detect Vite. Use:
   - Build command: `npm run build`
   - Output directory: `dist`
4. Add the environment variable
   `VITE_API_BASE_URL=https://<render-service>.onrender.com/api`.
5. Deploy, then set the resulting Vercel URL as Render's `CORS_ORIGINS` value
   and redeploy the backend.

Do not commit `.env` files, API keys, database files, `node_modules`, or
`frontend/dist`; these are excluded by `.gitignore`.
