// Mirrors API.md exactly. If API.md changes, change this file in the same commit.

// ── Shared types ────────────────────────────────────────────────

export type IocType =
  | 'phone'
  | 'upi'
  | 'alias'
  | 'case_number'
  | 'agency_claimed'
  | 'script_stage'

export type ScriptStage =
  | 'intro_threat'
  | 'fake_case_number'
  | 'video_call_demand'
  | 'isolation'
  | 'verification_transfer'

export interface Ioc {
  type: IocType
  value: string
}

export interface RecalledMemory {
  text: string
  why_relevant: string
  source_conversation_id: string | null
  matched_ioc: Ioc | null
}

export type ContradictionKind =
  | 'case_number_changed'
  | 'alias_shares_upi'
  | 'alias_shares_phone'
  | 'agency_changed'

export interface ContradictionFlag {
  kind: ContradictionKind
  claim_now: string
  claim_before: string
  source_conversation_id: string
  severity: 'low' | 'high'
}

export type Sender = 'scammer' | 'ajji'

export interface Message {
  id: number
  sender: Sender
  text: string
  created_at: string
}

export interface ApiError {
  error: {
    code: ApiErrorCode | string
    message: string
  }
}

export type ApiErrorCode =
  | 'invalid_message'
  | 'reset_not_confirmed'
  | 'conversation_not_found'
  | 'conversation_ended'
  | 'seed_already_running'
  | 'turn_timeout'
  | 'internal'

// ── 1. Create conversation ──────────────────────────────────────

export interface CreateConversationResponse {
  conversation_id: string
  persona: string
  started_at: string
  opening_line: string
}

// ── 2. Send a scammer message ───────────────────────────────────

export interface SendMessageRequest {
  sender: 'scammer'
  text: string
  memory_enabled: boolean
}

export type DegradedReason =
  | 'recall_unavailable'
  | 'extract_fallback_regex'
  | 'reply_fallback_canned'

export interface Timings {
  extract: number
  recall: number
  reply: number
  retain: number
  total: number
}

export interface SendMessageResponse {
  conversation_id: string
  scammer_message_id: number
  reply: Message
  memory_enabled: boolean
  recalled_memories: RecalledMemory[]
  extracted_iocs: Ioc[]
  contradiction_flags: ContradictionFlag[]
  script_stage: ScriptStage | null
  timings_ms: Timings
  degraded: (DegradedReason | string)[]
}

// ── 3. End conversation ─────────────────────────────────────────

export interface ConversationSummary {
  aliases: string[]
  agencies_claimed: string[]
  case_numbers: string[]
  upi_ids: string[]
  phones: string[]
  stages_reached: ScriptStage[]
  tactics: string[]
}

export interface EndConversationResponse {
  conversation_id: string
  ended_at: string
  duration_seconds: number
  summary: ConversationSummary
}

// ── 4. Conversation history ─────────────────────────────────────

export interface ConversationHistory {
  conversation_id: string
  persona: string
  started_at: string
  ended_at: string | null
  messages: Message[]
}

// ── 5. Network graph ────────────────────────────────────────────

export type NodeType = 'alias' | 'upi' | 'phone' | 'agency_claimed'

export interface NetworkNode {
  id: string
  type: NodeType
  label: string
  first_seen: string
  count: number
  ring_id: string | null
  in_current: boolean
}

export type EdgeRelation = 'uses_upi' | 'uses_phone' | 'claims_agency' | 'gave_case_number'

export interface NetworkEdge {
  source: string
  target: string
  relation: EdgeRelation
  weight: number
}

export interface NetworkResponse {
  nodes: NetworkNode[]
  edges: NetworkEdge[]
}

// ── 6. Stats ────────────────────────────────────────────────────

export interface StatsResponse {
  conversations: number
  total_minutes_wasted_estimate: number
  minutes_is_estimate: boolean
  unique_aliases: number
  unique_upi: number
  unique_phones: number
  rings_detected: number
  contradictions_caught: number
  memories_in_bank: number
}

// ── 7. Demo controls ────────────────────────────────────────────

export type SeedStatus = 'running' | 'done' | 'failed'

export interface SeedStartedResponse {
  job_id: string
  status: SeedStatus
  conversations_planned: number
}

export interface SeedStatusResponse {
  job_id: string
  status: SeedStatus
  conversations_done: number
  conversations_planned: number
  error: string | null
}

export interface ResetResponse {
  status: 'reset'
  bank_id: string
}

// ── 8. Health ───────────────────────────────────────────────────

export type DepStatus = 'ok' | 'down'

export interface HealthResponse {
  status: 'ok' | 'degraded'
  hindsight: DepStatus
  llm: DepStatus
  db: DepStatus
}
