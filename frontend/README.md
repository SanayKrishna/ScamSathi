# Ajji frontend

React 19, Vite, TypeScript, Tailwind v4, Motion and react-force-graph-2d. Light, Apple style: white and light gray surfaces, soft shadows, iOS system accents. The visual rules come from `.claude/skills/landing-page-design` (Part B): Geist, Tailwind type scale and spacing tokens, and one easing curve.

**Layout.** The Call view puts Ajji's iPhone in the centre (an incoming call, then an iMessage thread). What she remembers flies out to the left, contradictions and identifiers she heard to the right, and stats sit in a strip underneath. The Network view (`G`) shows the scam rings full screen.

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
| `GET /health` | Dot in the top bar, polled every 15 s | Green when all ok, amber "Degraded" when one is down |
| `GET /stats` | Stat strip under the stage | All four numbers render; "est." shows next to minutes |
| `POST /conversations` | New chat / Answer on the incoming call | `opening_line` appears as the first bubble |
| `POST /conversations/{id}/message` | Composer inside the phone | Reply appears; She remembers and Caught fill when memory is on and stay quiet when it is off; Identifiers heard fills either way |
| `POST /conversations/{id}/end` | End chat, and before New chat | "Call ended" in the thread; composer disabled |
| `GET /conversations/{id}` | Page reload mid chat | The thread is restored |
| `GET /network?conversation_id=` | Network view, refreshed after each message | Rings form; nodes in this chat get a blue ring |
| `POST /demo/seed`, `GET /demo/seed/{job_id}` | Demo menu (⋯ in the top bar) | Progress bar advances to done |
| `POST /demo/reset` | Demo menu, type RESET | Stats drop to zero |
| Errors (`ApiError`) | Toast at the bottom | `error.message` shows, never a raw error |

A turn slower than 4 seconds shows "<name> is looking for her glasses..." under the typing indicator.

## Keyboard shortcuts

`M` toggles memory, `N` starts a new chat, `G` switches between Call and Network, and `P` opens the walkthrough script. They work when focus is outside the text box. `Esc` leaves the text box, and `Alt + key` works while typing. Checked at 1920x1080 and 1366x768 with no overflow.

## Structure

```
src/
├── api.ts          one function per endpoint, real and mock clients
├── types.ts        every shape from API.md
├── store.tsx       single useReducer store and actions
├── config.ts       env
├── mocks/          fixtures from API.md
└── components/     TopBar, Phone, RememberColumn, CaughtColumn, StatStrip, NetworkView, DemoMenu, PresenterDrawer, Toasts
```
