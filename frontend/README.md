# MemoryBench frontend

Next.js (App Router) UI with three tabs — Chat, Memory Inspector, MemoryBench
— against the FastAPI backend in `../backend`. See the repo root
[README](../README.md) for the full project.

## Dev

```bash
cp .env.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at the backend
npm install
npm run dev
```

Requires the backend running (`uvicorn backend.app:app --port 8000` from the
repo root) — see the root README for setup.
