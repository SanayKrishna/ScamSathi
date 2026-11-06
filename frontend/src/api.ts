// One function per endpoint in API.md. VITE_USE_MOCKS switches between the
// real backend and the fixtures in src/mocks/.

import { config } from './config'
import type {
  ApiError,
  ConversationHistory,
  CreateConversationResponse,
  EndConversationResponse,
  HealthResponse,
  Message,
  NetworkResponse,
  ResetResponse,
  SeedStartedResponse,
  SeedStatusResponse,
  SendMessageRequest,
  SendMessageResponse,
  StatsResponse,
} from './types'

import createConversationMock from './mocks/create_conversation.json'
import endConversationMock from './mocks/end_conversation.json'
import errorNotFoundMock from './mocks/error_not_found.json'
import getConversationMock from './mocks/get_conversation.json'
import healthMock from './mocks/health.json'
import messageDegradedMock from './mocks/message_degraded.json'
import messageMemoryOffMock from './mocks/message_memory_off.json'
import messageMemoryOnMock from './mocks/message_memory_on.json'
import networkMock from './mocks/network.json'
import resetMock from './mocks/reset.json'
import seedStartedMock from './mocks/seed_started.json'
import seedStatusMock from './mocks/seed_status.json'
import statsMock from './mocks/stats.json'

// ── Errors ──────────────────────────────────────────────────────

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
  }
}

const NETWORK_ERROR_MESSAGE = 'Could not reach the server. Check that the backend is running.'

// ── Real client ─────────────────────────────────────────────────

async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${config.apiUrl}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiClientError(0, 'network_error', NETWORK_ERROR_MESSAGE)
  }

  if (!res.ok) {
    let parsed: ApiError | null = null
    try {
      parsed = (await res.json()) as ApiError
    } catch {
      /* non JSON error body */
    }
    const code = parsed?.error?.code ?? 'internal'
    const message = parsed?.error?.message ?? `Request failed (${res.status}).`
    throw new ApiClientError(res.status, code, message)
  }

  return (await res.json()) as T
}

const enc = encodeURIComponent

const real = {
  createConversation: () =>
    request<CreateConversationResponse>('POST', '/conversations', { persona: 'ajji' }),
  sendMessage: (conversationId: string, text: string, memoryEnabled: boolean) =>
    request<SendMessageResponse>('POST', `/conversations/${enc(conversationId)}/message`, {
      sender: 'scammer',
      text,
      memory_enabled: memoryEnabled,
    } satisfies SendMessageRequest),
  endConversation: (conversationId: string) =>
    request<EndConversationResponse>('POST', `/conversations/${enc(conversationId)}/end`),
  getConversation: (conversationId: string) =>
    request<ConversationHistory>('GET', `/conversations/${enc(conversationId)}`),
  getNetwork: (conversationId?: string) =>
    request<NetworkResponse>(
      'GET',
      conversationId ? `/network?conversation_id=${enc(conversationId)}` : '/network',
    ),
  getStats: () => request<StatsResponse>('GET', '/stats'),
  startSeed: () => request<SeedStartedResponse>('POST', '/demo/seed'),
  getSeedStatus: (jobId: string) => request<SeedStatusResponse>('GET', `/demo/seed/${enc(jobId)}`),
  resetDemo: () => request<ResetResponse>('POST', '/demo/reset', { confirm: 'RESET' }),
  getHealth: () => request<HealthResponse>('GET', '/health'),
}

// ── Mock client ─────────────────────────────────────────────────
// Serves fixtures after a 400–900 ms delay. Keeps a little in memory state
// (ids, ended conversations, seed progress) so the UI behaves like the real thing.

const delay = () => new Promise((r) => setTimeout(r, 400 + Math.random() * 500))
const clone = <T>(v: unknown) => structuredClone(v) as T
const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')

let mockConvCounter = 21
let mockMessageId = 100
let mockStats = clone<StatsResponse>(statsMock)
let mockSeed: { jobId: string; done: number; planned: number } | null = null
const mockConversations = new Map<
  string,
  { history: ConversationHistory; ended: EndConversationResponse | null }
>()

function mockNotFound(): never {
  const e = errorNotFoundMock as ApiError
  throw new ApiClientError(404, e.error.code, e.error.message)
}

const mock: typeof real = {
  async createConversation() {
    await delay()
    const res = clone<CreateConversationResponse>(createConversationMock)
    res.conversation_id = `conv_${String(mockConvCounter++).padStart(4, '0')}`
    res.started_at = nowIso()
    mockConversations.set(res.conversation_id, {
      history: {
        conversation_id: res.conversation_id,
        persona: res.persona,
        started_at: res.started_at,
        ended_at: null,
        messages: [
          { id: mockMessageId++, sender: 'ajji', text: res.opening_line, created_at: res.started_at },
        ],
      },
      ended: null,
    })
    mockStats = { ...mockStats, conversations: mockStats.conversations + 1 }
    return res
  },

  async sendMessage(conversationId, text, memoryEnabled) {
    const trimmed = text.trim()
    if (!trimmed || trimmed.length > 2000) {
      throw new ApiClientError(400, 'invalid_message', 'Message must be between 1 and 2000 characters.')
    }
    const conv = mockConversations.get(conversationId)
    if (!conv) mockNotFound()
    if (conv.ended) {
      throw new ApiClientError(409, 'conversation_ended', 'This chat has ended. Start a new one.')
    }
    await delay()

    // Type "/degraded" in a message to preview the degraded fixture.
    const fixture = trimmed.includes('/degraded')
      ? messageDegradedMock
      : memoryEnabled
        ? messageMemoryOnMock
        : messageMemoryOffMock
    const res = clone<SendMessageResponse>(fixture)
    const scammer: Message = { id: mockMessageId++, sender: 'scammer', text: trimmed, created_at: nowIso() }
    res.conversation_id = conversationId
    res.scammer_message_id = scammer.id
    res.reply = { ...res.reply, id: mockMessageId++, created_at: nowIso() }
    conv.history.messages.push(scammer, res.reply)
    mockStats = {
      ...mockStats,
      total_minutes_wasted_estimate: mockStats.total_minutes_wasted_estimate + 1,
      contradictions_caught: mockStats.contradictions_caught + res.contradiction_flags.length,
      memories_in_bank: mockStats.memories_in_bank + 1,
    }
    return res
  },

  async endConversation(conversationId) {
    const conv = mockConversations.get(conversationId)
    if (!conv) mockNotFound()
    await delay()
    if (!conv.ended) {
      const res = clone<EndConversationResponse>(endConversationMock)
      res.conversation_id = conversationId
      res.ended_at = nowIso()
      res.duration_seconds = Math.max(
        1,
        Math.round((Date.parse(res.ended_at) - Date.parse(conv.history.started_at)) / 1000),
      )
      conv.ended = res
      conv.history.ended_at = res.ended_at
    }
    return conv.ended
  },

  async getConversation(conversationId) {
    await delay()
    const conv = mockConversations.get(conversationId)
    if (conv) return clone<ConversationHistory>(conv.history)
    if (conversationId === getConversationMock.conversation_id) {
      return clone<ConversationHistory>(getConversationMock)
    }
    mockNotFound()
  },

  async getNetwork(conversationId) {
    await delay()
    const res = clone<NetworkResponse>(networkMock)
    if (!conversationId) res.nodes.forEach((n) => (n.in_current = false))
    return res
  },

  async getStats() {
    await delay()
    return { ...mockStats }
  },

  async startSeed() {
    await delay()
    if (mockSeed && mockSeed.done < mockSeed.planned) {
      throw new ApiClientError(409, 'seed_already_running', 'A seed job is already running.')
    }
    const res = clone<SeedStartedResponse>(seedStartedMock)
    mockSeed = { jobId: res.job_id, done: 0, planned: res.conversations_planned }
    return res
  },

  async getSeedStatus(jobId) {
    await delay()
    const base = clone<SeedStatusResponse>(seedStatusMock)
    if (!mockSeed || mockSeed.jobId !== jobId) return { ...base, job_id: jobId }
    mockSeed.done = Math.min(mockSeed.planned, mockSeed.done + 3)
    return {
      ...base,
      job_id: jobId,
      conversations_done: mockSeed.done,
      conversations_planned: mockSeed.planned,
      status: mockSeed.done >= mockSeed.planned ? 'done' : 'running',
    }
  },

  async resetDemo() {
    await delay()
    mockStats = { ...clone<StatsResponse>(statsMock), conversations: 0, total_minutes_wasted_estimate: 0, unique_aliases: 0, unique_upi: 0, unique_phones: 0, rings_detected: 0, contradictions_caught: 0, memories_in_bank: 0 }
    return clone<ResetResponse>(resetMock)
  },

  async getHealth() {
    await delay()
    return clone<HealthResponse>(healthMock)
  },
}

export const api = config.useMocks ? mock : real
export type Api = typeof real
