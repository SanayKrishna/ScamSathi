// Single useReducer store for the whole app (prompts.md F1: no other state library).

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'
import { api, ApiClientError } from './api'
import type {
  ContradictionFlag,
  Ioc,
  HealthResponse,
  Message,
  NetworkResponse,
  SendMessageResponse,
  StatsResponse,
} from './types'

export interface ChatMessage extends Message {
  degraded?: string[]
}

export interface Conversation {
  id: string
  startedAt: string
  ended: boolean
}

export interface SeenContradiction extends ContradictionFlag {
  key: string
}

export interface Toast {
  id: number
  message: string
}

export interface State {
  conversation: Conversation | null
  messages: ChatMessage[]
  lastResponse: SendMessageResponse | null
  /** Bumps on every response so panels can replay their entrance animation. */
  responseSeq: number
  contradictions: SeenContradiction[]
  /** Unique identifiers extracted across this conversation, newest first. */
  heard: Ioc[]
  memoryEnabled: boolean
  network: NetworkResponse | null
  stats: StatsResponse | null
  health: HealthResponse | null
  pending: 'idle' | 'starting' | 'sending' | 'ending'
  sentAt: number | null
  toasts: Toast[]
}

const initialState: State = {
  conversation: null,
  messages: [],
  lastResponse: null,
  responseSeq: 0,
  contradictions: [],
  heard: [],
  memoryEnabled: true,
  network: null,
  stats: null,
  health: null,
  pending: 'idle',
  sentAt: null,
  toasts: [],
}

type Action =
  | { type: 'pending'; pending: State['pending'] }
  | { type: 'conversation_started'; id: string; startedAt: string; opening: Message }
  | { type: 'conversation_loaded'; id: string; startedAt: string; ended: boolean; messages: Message[] }
  | { type: 'scammer_sent'; message: ChatMessage }
  | { type: 'reply_received'; response: SendMessageResponse; scammerTempId: number }
  | { type: 'send_failed'; scammerTempId: number }
  | { type: 'conversation_ended' }
  | { type: 'toggle_memory' }
  | { type: 'set_memory'; enabled: boolean }
  | { type: 'network'; network: NetworkResponse }
  | { type: 'stats'; stats: StatsResponse }
  | { type: 'health'; health: HealthResponse }
  | { type: 'toast'; toast: Toast }
  | { type: 'dismiss_toast'; id: number }

const MAX_CONTRADICTIONS = 5

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'pending':
      return { ...state, pending: action.pending }
    case 'conversation_started':
      return {
        ...state,
        conversation: { id: action.id, startedAt: action.startedAt, ended: false },
        messages: [action.opening],
        lastResponse: null,
        contradictions: [],
        heard: [],
        pending: 'idle',
      }
    case 'conversation_loaded':
      return {
        ...state,
        conversation: { id: action.id, startedAt: action.startedAt, ended: action.ended },
        messages: action.messages,
        heard: [],
        pending: 'idle',
      }
    case 'scammer_sent':
      return { ...state, messages: [...state.messages, action.message], pending: 'sending', sentAt: Date.now() }
    case 'reply_received': {
      const r = action.response
      const fresh = r.contradiction_flags.map((f) => ({
        ...f,
        key: `${f.kind}|${f.claim_now}|${f.claim_before}|${f.source_conversation_id}`,
      }))
      const known = new Set(fresh.map((f) => f.key))
      const contradictions = [...fresh, ...state.contradictions.filter((c) => !known.has(c.key))].slice(
        0,
        MAX_CONTRADICTIONS,
      )
      const seen = new Set(state.heard.map((i) => `${i.type}|${i.value}`))
      const heard = [...r.extracted_iocs.filter((i) => !seen.has(`${i.type}|${i.value}`)), ...state.heard]
      return {
        ...state,
        heard,
        messages: [
          ...state.messages.map((m) => (m.id === action.scammerTempId ? { ...m, id: r.scammer_message_id } : m)),
          { ...r.reply, degraded: r.degraded },
        ],
        lastResponse: r,
        responseSeq: state.responseSeq + 1,
        contradictions,
        pending: 'idle',
        sentAt: null,
      }
    }
    case 'send_failed':
      return {
        ...state,
        messages: state.messages.filter((m) => m.id !== action.scammerTempId),
        pending: 'idle',
        sentAt: null,
      }
    case 'conversation_ended':
      return state.conversation
        ? { ...state, conversation: { ...state.conversation, ended: true }, pending: 'idle' }
        : state
    case 'toggle_memory':
      return { ...state, memoryEnabled: !state.memoryEnabled }
    case 'set_memory':
      return { ...state, memoryEnabled: action.enabled }
    case 'network':
      return { ...state, network: action.network }
    case 'stats':
      return { ...state, stats: action.stats }
    case 'health':
      return { ...state, health: action.health }
    case 'toast':
      return { ...state, toasts: [...state.toasts.slice(-2), action.toast] }
    case 'dismiss_toast':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) }
  }
}

// ── Actions ─────────────────────────────────────────────────────

interface Actions {
  newChat: () => Promise<void>
  endChat: () => Promise<void>
  send: (text: string) => Promise<boolean>
  toggleMemory: () => void
  refresh: () => Promise<void>
  notify: (message: string) => void
  dismissToast: (id: number) => void
}

const StoreContext = createContext<{ state: State; actions: Actions } | null>(null)

const SESSION_KEY = 'ajji.conversation'

function errorMessage(e: unknown): string {
  if (e instanceof ApiClientError) return e.message
  return 'Something went wrong. Try again.'
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const stateRef = useRef(state)
  stateRef.current = state
  const toastId = useRef(0)
  const tempId = useRef(-1)

  const notify = useCallback((message: string) => {
    const id = ++toastId.current
    dispatch({ type: 'toast', toast: { id, message } })
    window.setTimeout(() => dispatch({ type: 'dismiss_toast', id }), 5000)
  }, [])

  const refresh = useCallback(async () => {
    const convId = stateRef.current.conversation?.id
    const [network, stats, health] = await Promise.allSettled([
      api.getNetwork(convId),
      api.getStats(),
      api.getHealth(),
    ])
    if (network.status === 'fulfilled') dispatch({ type: 'network', network: network.value })
    if (stats.status === 'fulfilled') dispatch({ type: 'stats', stats: stats.value })
    if (health.status === 'fulfilled') dispatch({ type: 'health', health: health.value })
    else
      dispatch({
        type: 'health',
        health: { status: 'degraded', hindsight: 'down', llm: 'down', db: 'down' },
      })
  }, [])

  const newChat = useCallback(async () => {
    const s = stateRef.current
    if (s.pending !== 'idle') return
    dispatch({ type: 'pending', pending: 'starting' })
    try {
      // Close the previous chat first so its summary is retained.
      if (s.conversation && !s.conversation.ended) {
        await api.endConversation(s.conversation.id).catch(() => undefined)
      }
      const res = await api.createConversation()
      sessionStorage.setItem(SESSION_KEY, res.conversation_id)
      dispatch({
        type: 'conversation_started',
        id: res.conversation_id,
        startedAt: res.started_at,
        opening: { id: tempId.current--, sender: 'ajji', text: res.opening_line, created_at: res.started_at },
      })
      void refresh()
    } catch (e) {
      dispatch({ type: 'pending', pending: 'idle' })
      notify(errorMessage(e))
    }
  }, [notify, refresh])

  const endChat = useCallback(async () => {
    const s = stateRef.current
    if (!s.conversation || s.conversation.ended || s.pending !== 'idle') return
    dispatch({ type: 'pending', pending: 'ending' })
    try {
      await api.endConversation(s.conversation.id)
      dispatch({ type: 'conversation_ended' })
      void refresh()
    } catch (e) {
      dispatch({ type: 'pending', pending: 'idle' })
      notify(errorMessage(e))
    }
  }, [notify, refresh])

  const send = useCallback(
    async (raw: string) => {
      const s = stateRef.current
      const text = raw.trim()
      if (!text || !s.conversation || s.conversation.ended || s.pending !== 'idle') return false
      if (text.length > 2000) {
        notify('Message is too long. Keep it under 2000 characters.')
        return false
      }
      const id = tempId.current--
      dispatch({
        type: 'scammer_sent',
        message: { id, sender: 'scammer', text, created_at: new Date().toISOString() },
      })
      try {
        const response = await api.sendMessage(s.conversation.id, text, s.memoryEnabled)
        dispatch({ type: 'reply_received', response, scammerTempId: id })
        void refresh()
        return true
      } catch (e) {
        dispatch({ type: 'send_failed', scammerTempId: id })
        if (e instanceof ApiClientError && e.code === 'conversation_ended') dispatch({ type: 'conversation_ended' })
        notify(errorMessage(e))
        return false
      }
    },
    [notify, refresh],
  )

  const toggleMemory = useCallback(() => dispatch({ type: 'toggle_memory' }), [])
  const dismissToast = useCallback((id: number) => dispatch({ type: 'dismiss_toast', id }), [])

  // Boot: restore the conversation after a page reload, then load panels.
  useEffect(() => {
    let cancelled = false
    const boot = async () => {
      const saved = sessionStorage.getItem(SESSION_KEY)
      if (saved) {
        try {
          const h = await api.getConversation(saved)
          if (!cancelled) {
            dispatch({
              type: 'conversation_loaded',
              id: h.conversation_id,
              startedAt: h.started_at,
              ended: h.ended_at !== null,
              messages: h.messages,
            })
          }
        } catch {
          sessionStorage.removeItem(SESSION_KEY)
        }
      }
      if (!cancelled) void refresh()
    }
    void boot()
    const timer = window.setInterval(() => {
      api
        .getHealth()
        .then((health) => dispatch({ type: 'health', health }))
        .catch(() =>
          dispatch({ type: 'health', health: { status: 'degraded', hindsight: 'down', llm: 'down', db: 'down' } }),
        )
    }, 15000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [refresh])

  const actions = useMemo<Actions>(
    () => ({ newChat, endChat, send, toggleMemory, refresh, notify, dismissToast }),
    [newChat, endChat, send, toggleMemory, refresh, notify, dismissToast],
  )

  const value = useMemo(() => ({ state, actions }), [state, actions])
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}

export function useStore() {
  const ctx = useContext(StoreContext)
  if (!ctx) throw new Error('useStore must be used inside StoreProvider')
  return ctx
}
