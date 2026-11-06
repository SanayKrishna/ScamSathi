# Ajji frontend

React 19, Vite, TypeScript, Tailwind v4, Motion and react-force-graph-2d. The visual rules come from `.claude/skills/landing-page-design` (Part B): Geist, flat dark surfaces, Tailwind type scale and spacing tokens, and one easing curve.

## Run

```bash
cp .env.example .env   # VITE_USE_MOCKS=true by default
npm install
npm run dev            # http://localhost:5173
npm run build          # type check and production build
```

| Env | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | FastAPI backend |
| `VITE_USE_MOCKS` | `true` | `true` serves `src/mocks/*.json`, `false` calls the backend |
| `VITE_PERSONA_NAME` | `Ajji` | Persona display name. Rename here only |

On mocks, put `/degraded` anywhere in a scammer message to preview the degraded reply.

## Switching to the live backend

1. Start the backend on port 8000. CORS must allow `http://localhost:5173`.
2. In `.env`, set `VITE_USE_MOCKS=false` (and `VITE_API_URL` if the backend is elsewhere).
3. Restart `npm run dev` (Vite reads env at startup).
4. Walk the checklist below. If the backend returns something different from `API.md`, **write the differences down rather than quietly adapting the frontend**. Both sides then decide which one changes.

### Endpoint checklist

| Endpoint | Where the UI uses it | Check |
|---|---|---|
| `GET /health` | Header dot, polled every 15 s | Green when all ok, amber "Degraded" when one is down |
| `GET /stats` | Header tiles | All four numbers render; "est." shows next to minutes |
| `POST /conversations` | New chat / Start a chat | `opening_line` appears as the first bubble |
| `POST /conversations/{id}/message` | Composer | Reply appears; memory panel and contradiction cards fill when memory is on and stay empty when it is off |
| `POST /conversations/{id}/end` | End chat, and before New chat | "Chat ended" divider; composer disabled |
| `GET /conversations/{id}` | Page reload mid chat | The thread is restored |
| `GET /network?conversation_id=` | Network panel, after each message | Rings form; nodes in this chat get a white ring |
| `POST /demo/seed`, `GET /demo/seed/{job_id}` | Demo menu (sliders icon) | Progress bar advances to done |
| `POST /demo/reset` | Demo menu, type RESET | Stats drop to zero |
| Errors (`ApiError`) | Toast at the bottom | `error.message` shows, never a raw error |

A turn slower than 4 seconds shows "<name> is looking for her glasses..." under the typing indicator.

## Structure

```
src/
├── api.ts          one function per endpoint, real and mock clients
├── types.ts        every shape from API.md
├── store.tsx       single useReducer store and actions
├── config.ts       env
├── mocks/          fixtures from API.md
└── components/     Header, Chat, MemoryPanel, ContradictionPanel, NetworkGraph, DemoMenu, Toasts
```
