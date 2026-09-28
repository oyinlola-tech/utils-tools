# Deployment

One codebase, two targets. Storage, logging, and capability gating switch
based on environment variables.

## Production: Vercel frontend + cPanel backend

| | Host | Serves |
|---|---|---|
| Frontend | `tools.oyinlola.site` (Vercel) | static pages and assets from `frontend/` |
| Backend | `tools.telente.site` (cPanel) | the FastAPI app, `STORAGE_DRIVER=local` |

### Backend (cPanel)

1. **Git Version Control** — clone the repository into `~/utils-backend`.
2. **Setup Python App** — Python 3.12, application root `utils-backend`,
   application URL `tools.telente.site`, startup file `cpanel_wsgi.py`,
   entry point `application`.
3. Environment variables:
   - `APP_ENV=production`, `DEBUG=false`
   - `STORAGE_DRIVER=local`
   - `CORS_ORIGINS=https://tools.oyinlola.site`
   - `PUBLIC_SITE_URL=https://tools.oyinlola.site`
4. Add `requirements-cpanel.txt` as the configuration file, run
   **Pip Install**, then **Restart**.

Passenger speaks WSGI, so `cpanel_wsgi.py` wraps the ASGI app with
`a2wsgi`. To update: pull in Git Version Control, then restart the app.

cPanel overwrites `passenger_wsgi.py` in the application root with a stub
that loads the startup file, so the startup file must not use that name.
The server copy therefore differs from the repository; leave
`passenger_wsgi.py` unchanged here, or the next pull on the server
conflicts with it.

Pip Install can report "Unknown error occurred" after about two minutes
while it is still running in the background. Wait for it to finish before
retrying; a retry during that time fails with "Can't acquire lock".

### Frontend (Vercel)

`vercel.json` publishes `frontend/` as a static site and mirrors the page
routes FastAPI serves locally (`/tools/{id}`, `/about`, `/errors/{name}`,
`/static/*`). `.vercelignore` keeps the Python code out of the build.

API calls go straight to the backend: `frontend/assets/js/config.js` maps
the frontend host to the API origin, and the backend allows that origin
through `CORS_ORIGINS`. `/api/*`, `/sitemap.xml` and `/robots.txt` are also
proxied to the backend, which covers hosts not listed in `config.js`
(preview deployments).

To move either side to another domain, change `config.js` and
`vercel.json` (backend) or `CORS_ORIGINS` and `PUBLIC_SITE_URL` (frontend).

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./start.sh          # serves http://127.0.0.1:8000
```

Requirements:

- Python 3.10+
- Ghostscript (`gs`) for PDF compression and PDF→image tools
- Free disk space for `storage/` (uploads, jobs, downloads are cleaned by
  the job TTL sweeper)

Production-like local run (no reload):

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
```

## Vercel serverless (previous setup)

The whole app can also run as a single Vercel Python function. This needs
the earlier `vercel.json`, which built `api/index.py` and routed `/(.*)`
to it, and no `.vercelignore`:

- FastAPI serves pages, static assets, and API routes through the same
  handler.
- `api/index.py` wraps the app with `Mangum`.

### Setup

1. Import the repo into Vercel (root = repository root).
2. Create a **Vercel Blob** store and copy its read-write token.
 3. Set environment variables:
    - `STORAGE_DRIVER=vercel`
    - `BLOB_READ_WRITE_TOKEN=<token>`
    - `BLOB_STORE_ID=<store-id>` (optional, required when using multiple blob stores)
    - `BLOB_WEBHOOK_PUBLIC_KEY=<public-key>` (optional, for webhook verification)
    - `BLOB_ACCESS_MODE=public` (or `private`, matching the store)
    - `CORS_ORIGINS=https://<your-domain>.vercel.app`
    - `APP_ENV=production`, `DEBUG=false`
4. Deploy.

### What changes on Vercel

| Concern | Behavior |
|---|---|
| Storage | all files go to Vercel Blob via the `vercel` storage driver |
| Logs | file logging disabled; everything streams to stdout (Vercel dashboard) |
| Ghostscript tools | unavailable — `pdf-compressor` and `pdf-to-image` report `unavailable` via `/api/v1/capabilities` and their pages show the disabled state |
| Background tools | unavailable on the current build — `rembg` was trimmed from `api/requirements.txt` to fit the 500 MB function limit, so `background-remover` and `background-replacement` report `unavailable` and their pages show the disabled state |
| Temp files | `TEMP_DIRECTORY` / `XDG_CACHE_HOME` point under `/tmp` (serverless) |

The capabilities endpoint is the source of truth: the frontend never hardcodes
which tools exist, so the same pages work in both environments.

### Blob notes

- Storage goes through the official Vercel Python SDK (`vercel.blob`,
  pinned in `api/requirements.txt`), which handles API versioning headers,
  retries for transient failures and signed URLs.
- `BLOB_READ_WRITE_TOKEN` is read at import time; a missing token raises a
  startup error on Vercel (the local driver remains usable without it).
- `BLOB_ACCESS_MODE` must match the store's access mode (`public` or
  `private`). Private stores return time-limited signed download URLs.

## Troubleshooting

- **Startup error `BLOB_READ_WRITE_TOKEN is required`** — running with
  `STORAGE_DRIVER=vercel` outside Vercel, or the env var is unset on the
  platform.
- **`gs --version` not found** — install Ghostscript; the two `gs` tools
  will otherwise be flagged unavailable (capabilities), so pages degrade
  cleanly instead of crashing.
- **Background removal unavailable on Vercel** — `rembg` (with its
  ONNX runtime and models) is excluded from `api/requirements.txt` to stay
  under the 500 MB serverless function limit, so the two background tools
  are reported unavailable and their pages show the disabled state. They
  work fully in local mode.
