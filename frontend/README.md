# Support Orchestrator — Frontend

React 19 + TypeScript + Vite SPA for the Support Orchestrator API. Submit a
customer message, see the full LangGraph pipeline result (classification,
extraction, optional escalation, customer reply, internal handoff, and the
per-node processing trace).

## Stack

- **React 19** + **TypeScript 5** (strict)
- **Vite 6** — dev server + build
- **Tailwind CSS 3** — utility styling
- **TanStack Query 5** — API state (cache, retry, loading/error)
- **Lucide React** — icons
- **Vitest + React Testing Library** — unit tests
- **ESLint (flat config) + Prettier** — lint + format

## Quick start

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The Vite dev server proxies `/api/v1/*` to `http://localhost:8000` so you can
run the backend (`make run` from the repo root) and the SPA in parallel
without CORS configuration.

If your backend is reachable at a different URL, set it in `.env.local`:

```bash
cp .env.example .env.local   # then edit
# VITE_API_BASE_URL=https://api.example.com
```

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR + `/api` proxy |
| `npm run build` | TypeScript project build + Vite production bundle to `dist/` |
| `npm run preview` | Serve the production bundle locally |
| `npm run lint` | ESLint (TypeScript + React Hooks + React Refresh) |
| `npm run format` | Prettier write |
| `npm run format:check` | Prettier verify |
| `npm test` | Vitest single run |
| `npm run test:watch` | Vitest watch mode |

## Architecture

```
src/
├── api/
│   ├── types.ts         # TypeScript mirrors of every backend Pydantic model
│   └── client.ts        # typed fetch wrapper + ErrorResponse handling
├── hooks/
│   ├── useHealth.ts            # GET /health (polled every 30s)
│   └── useProcessSupport.ts    # POST /support/process
├── components/
│   ├── ui/              # primitives (Card, Badge, Button, Spinner)
│   ├── MessageForm.tsx
│   ├── ClassificationCard.tsx
│   ├── ExtractedInfoCard.tsx
│   ├── EscalationCard.tsx
│   ├── CustomerResponseCard.tsx
│   ├── InternalSummaryCard.tsx
│   ├── TraceTable.tsx
│   ├── ErrorBanner.tsx
│   ├── HealthIndicator.tsx
│   └── ResultDisplay.tsx
├── lib/
│   ├── cn.ts            # className helper (clsx)
│   └── samples.ts       # 5 sample messages mirroring the backend fixtures
├── App.tsx              # top-level layout + state wiring
├── main.tsx             # React root + QueryClient
└── index.css            # Tailwind directives + base styles
```

### Design choices

- **Types are hand-typed** (not generated from `/openapi.json`). A production
  version would use `openapi-typescript` to keep the front-end contract
  in lockstep with backend Pydantic changes; for the take-home, keeping the
  shape visible in one file (`src/api/types.ts`) is clearer.
- **TanStack Query everywhere there's network I/O** — gives us loading
  states, retry, cache, and consistent error handling without bespoke
  reducers.
- **`ApiError` carries the structured `ErrorResponse` envelope** so the UI
  can surface the backend's `error`, `detail`, and `request_id` fields when
  something fails.
- **The dev-server proxy means no CORS configuration is needed locally** —
  the SPA fetches relative paths (`/api/v1/...`), Vite forwards them to the
  backend. Production deployments either serve the SPA from the same origin
  or put a reverse proxy in front.
- **Strict TypeScript** — `strict`, `noUnusedLocals`, `noUnusedParameters`,
  `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`. No `any`.

### Accessibility

- Semantic HTML throughout (`header`, `main`, `footer`, `section`, `blockquote`).
- All interactive elements are real `button` / `select` / `textarea`.
- The health indicator uses `role="status"` + `aria-live="polite"`.
- The error banner uses `role="alert"`.

## Production build

```bash
npm run build
ls dist/
```

The output is a static bundle suitable for any CDN or reverse proxy.
For a single-container deployment, wire the bundle behind nginx or serve
it from FastAPI's `StaticFiles` at `/`. The Dockerfile in the repo root
covers the backend only; a `frontend/Dockerfile` is a logical next step.
