# Ajji API contract

The single source of truth between backend and frontend. If the code and this file disagree, fix one of them the same day. Change this file in its own commit so both people see it.

- Base URL (dev): `http://localhost:8000`
- Frontend env: `VITE_API_URL=http://localhost:8000`, `VITE_USE_MOCKS=true|false`
- All bodies are JSON. All timestamps are ISO 8601 UTC strings (`2026-11-06T10:42:00Z`).
- IDs are strings. Conversation IDs look like `conv_0007`. IOC IDs look like `upi:sharma.verify@fakebank` (type + value, so they're stable across reseeds).
- CORS: backend allows `http://localhost:5173` (Vite default).

Mock fixtures for every response live in `frontend/src/mocks/`. Filenames are listed under each endpoint.

---

## Shared types

```ts
type IocType =
  | "phone"
  | "upi"
  | "alias"
  | "case_number"
  | "agency_claimed"
  | "script_stage";

type ScriptStage =
  | "intro_threat"
  | "fake_case_number"
  | "video_call_demand"
  | "isolation"
  | "verification_transfer";

interface Ioc {
  type: IocType;
  value: string;          // normalised: lowercase UPI, digits-only phone, trimmed alias
}

interface RecalledMemory {
  text: string;           // the fact as Hindsight returned it
  why_relevant: string;   // one line, shown in the memory panel
  source_conversation_id: string | null;
  matched_ioc: Ioc | null; // the IOC that triggered this recall, if any
}

interface ContradictionFlag {
  kind: "case_number_changed" | "alias_shares_upi" | "alias_shares_phone" | "agency_changed";
  claim_now: string;
  claim_before: string;
  source_conversation_id: string;
  severity: "low" | "high";
}

interface Message {
  id: number;
  sender: "scammer" | "ajji";
  text: string;
  created_at: string;
}

interface ApiError {
  error: {
    code: string;         // machine-readable, see Errors
    message: string;      // human-readable, safe to show in UI
  };
}
```

---

## 1. Create conversation

`POST /conversations`

Request body: none, or optional:

```json
{ "persona": "ajji" }
```

Response `201`:

```json
{
  "conversation_id": "conv_0021",
  "persona": "ajji",
  "started_at": "2026-11-06T10:40:00Z",
  "opening_line": "Hello? Who is speaking? My grandson usually picks up the phone."
}
```

Mock: `create_conversation.json`

---

## 2. Send a scammer message (the main endpoint)

`POST /conversations/{conversation_id}/message`

Request:

```json
{
  "sender": "scammer",
  "text": "Madam, this is Inspector Sharma from CBI Mumbai. Your Aadhaar is linked to money laundering. Case number DL/4410.",
  "memory_enabled": true
}
```

| Field | Type | Rules |
|---|---|---|
| `sender` | `"scammer"` | Only value accepted for now |
| `text` | string | 1 to 2000 chars after trim, else `400 invalid_message` |
| `memory_enabled` | boolean | `false` skips recall and contradiction checks; retain still runs |

Response `200` (memory on):

```json
{
  "conversation_id": "conv_0021",
  "scammer_message_id": 41,
  "reply": {
    "id": 42,
    "sender": "ajji",
    "text": "Aiyyo, sir! But last week your colleague told me case is MH/2291. Which one I should write down? My pen is not working also.",
    "created_at": "2026-11-06T10:42:03Z"
  },
  "memory_enabled": true,
  "recalled_memories": [
    {
      "text": "'Officer Verma' (claimed CBI) asked for transfer to UPI sharma.verify@fakebank in conversation conv_0004.",
      "why_relevant": "Same UPI handle the scammer is likely to push",
      "source_conversation_id": "conv_0004",
      "matched_ioc": { "type": "alias", "value": "inspector sharma" }
    },
    {
      "text": "Inspector Sharma gave case number MH/2291 in conversation conv_0007.",
      "why_relevant": "Same alias, different case number",
      "source_conversation_id": "conv_0007",
      "matched_ioc": { "type": "alias", "value": "inspector sharma" }
    },
    {
      "text": "This ring moves to a video-call demand within 3 messages of the case number.",
      "why_relevant": "Predicts the next script stage",
      "source_conversation_id": null,
      "matched_ioc": null
    }
  ],
  "extracted_iocs": [
    { "type": "alias", "value": "inspector sharma" },
    { "type": "agency_claimed", "value": "cbi" },
    { "type": "case_number", "value": "DL/4410" },
    { "type": "script_stage", "value": "fake_case_number" }
  ],
  "contradiction_flags": [
    {
      "kind": "case_number_changed",
      "claim_now": "Case DL/4410",
      "claim_before": "Case MH/2291",
      "source_conversation_id": "conv_0007",
      "severity": "high"
    }
  ],
  "script_stage": "fake_case_number",
  "timings_ms": { "extract": 410, "recall": 620, "reply": 980, "retain": 0, "total": 2010 },
  "degraded": []
}
```

Response `200` (memory off): same shape, with `recalled_memories: []`, `contradiction_flags: []`, `memory_enabled: false`. The frontend must not treat empty arrays as errors.

| Field | Notes |
|---|---|
| `timings_ms.retain` | `0` because retain runs after the response is sent (background task) |
| `degraded` | List of what failed but didn't crash the turn: `"recall_unavailable"`, `"extract_fallback_regex"`, `"reply_fallback_canned"`. Show a small muted badge in the UI when non-empty |

Mocks: `message_memory_on.json`, `message_memory_off.json`, `message_degraded.json`

---

## 3. End conversation

`POST /conversations/{conversation_id}/end`

Writes the conversation summary to Hindsight. Call it when the user clicks "End chat" or before starting a new one.

Response `200`:

```json
{
  "conversation_id": "conv_0021",
  "ended_at": "2026-11-06T10:55:10Z",
  "duration_seconds": 910,
  "summary": {
    "aliases": ["inspector sharma"],
    "agencies_claimed": ["cbi"],
    "case_numbers": ["DL/4410"],
    "upi_ids": ["sharma.verify@fakebank"],
    "phones": ["5550142233"],
    "stages_reached": ["intro_threat", "fake_case_number", "video_call_demand"],
    "tactics": ["urgency", "isolation: told not to tell family"]
  }
}
```

Calling `end` twice returns the same body (idempotent).

Mock: `end_conversation.json`

---

## 4. Get conversation history

`GET /conversations/{conversation_id}`

Used when the page reloads mid-demo.

Response `200`:

```json
{
  "conversation_id": "conv_0021",
  "persona": "ajji",
  "started_at": "2026-11-06T10:40:00Z",
  "ended_at": null,
  "messages": [
    { "id": 40, "sender": "ajji", "text": "Hello? Who is speaking?", "created_at": "2026-11-06T10:40:00Z" },
    { "id": 41, "sender": "scammer", "text": "Madam, this is Inspector Sharma from CBI...", "created_at": "2026-11-06T10:42:00Z" },
    { "id": 42, "sender": "ajji", "text": "Aiyyo, sir! But last week...", "created_at": "2026-11-06T10:42:03Z" }
  ]
}
```

Mock: `get_conversation.json`

---

## 5. Network graph

`GET /network`

Optional query: `?conversation_id=conv_0021` marks nodes seen in that conversation with `"in_current": true`, so the UI can highlight them.

Response `200`:

```json
{
  "nodes": [
    { "id": "alias:inspector sharma", "type": "alias", "label": "Inspector Sharma", "first_seen": "2026-11-05T14:00:00Z", "count": 3, "ring_id": "ring_1", "in_current": true },
    { "id": "alias:officer verma", "type": "alias", "label": "Officer Verma", "first_seen": "2026-11-05T14:20:00Z", "count": 2, "ring_id": "ring_1", "in_current": false },
    { "id": "upi:sharma.verify@fakebank", "type": "upi", "label": "sharma.verify@fakebank", "first_seen": "2026-11-05T14:21:00Z", "count": 4, "ring_id": "ring_1", "in_current": false },
    { "id": "agency_claimed:cbi", "type": "agency_claimed", "label": "CBI", "first_seen": "2026-11-05T14:00:00Z", "count": 9, "ring_id": null, "in_current": true }
  ],
  "edges": [
    { "source": "alias:inspector sharma", "target": "upi:sharma.verify@fakebank", "relation": "uses_upi", "weight": 2 },
    { "source": "alias:officer verma", "target": "upi:sharma.verify@fakebank", "relation": "uses_upi", "weight": 2 },
    { "source": "alias:inspector sharma", "target": "agency_claimed:cbi", "relation": "claims_agency", "weight": 3 }
  ]
}
```

| Field | Notes |
|---|---|
| `relation` | `uses_upi`, `uses_phone`, `claims_agency`, `gave_case_number` |
| `ring_id` | Connected component with 2 or more aliases; `null` for shared hubs like agency names, which are excluded from ring detection so "CBI" doesn't merge every ring into one |
| Node types shown | `alias`, `upi`, `phone`, `agency_claimed`. `case_number` and `script_stage` are not graph nodes |

Mock: `network.json`

---

## 6. Stats

`GET /stats`

Response `200`:

```json
{
  "conversations": 21,
  "total_minutes_wasted_estimate": 214,
  "minutes_is_estimate": true,
  "unique_aliases": 10,
  "unique_upi": 6,
  "unique_phones": 7,
  "rings_detected": 3,
  "contradictions_caught": 14,
  "memories_in_bank": 312
}
```

`minutes_is_estimate` is always `true` for simulated data. The UI shows "est." next to the number.

Mock: `stats.json`

---

## 7. Demo controls

`POST /demo/seed`

Runs the simulator: about 20 conversations with memory on. Slow (minutes), so it runs as a background job.

Response `202`:

```json
{ "job_id": "seed_01", "status": "running", "conversations_planned": 20 }
```

`GET /demo/seed/{job_id}`

```json
{ "job_id": "seed_01", "status": "running", "conversations_done": 7, "conversations_planned": 20, "error": null }
```

`status`: `running`, `done`, `failed`.

`POST /demo/reset`

Wipes SQLite and deletes and recreates the Hindsight bank `scam-intel`. Requires a confirmation flag so nobody wipes the seeded bank by accident mid-demo:

```json
{ "confirm": "RESET" }
```

Response `200`:

```json
{ "status": "reset", "bank_id": "scam-intel" }
```

Mocks: `seed_started.json`, `seed_status.json`, `reset.json`

Run the seed once before use, and do not reset a bank you want to keep.

---

## 8. Health

`GET /health`

```json
{ "status": "ok", "hindsight": "ok", "llm": "ok", "db": "ok" }
```

Any dependency can be `"down"`; `status` becomes `"degraded"`. The frontend header shows a dot: green for ok, amber for degraded.

Mock: `health.json`

---

## Errors

Every non-2xx response uses the `ApiError` shape:

```json
{ "error": { "code": "conversation_not_found", "message": "That conversation doesn't exist. Start a new one." } }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `invalid_message` | Empty text, over 2000 chars, wrong `sender` |
| 400 | `reset_not_confirmed` | `/demo/reset` without `"confirm": "RESET"` |
| 404 | `conversation_not_found` | Unknown `conversation_id` |
| 409 | `conversation_ended` | Message sent to an ended conversation |
| 409 | `seed_already_running` | Second seed while one is running |
| 504 | `turn_timeout` | A turn took over 8 seconds even after fallbacks |
| 500 | `internal` | Anything else. Message must not leak stack traces |

The message endpoint should almost never fail: LLM and Hindsight failures degrade the turn (see `degraded`) instead of returning an error.

---

## Change log

| Date | Change |
|---|---|
| 2026-11-05 | v1 |
