import { AnimatePresence, motion } from 'motion/react'
import { ArrowUp, Plus, StopCircle, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'
import { config } from '../config'
import { EASE, rise } from '../lib/motion'
import { clockTime } from '../lib/format'
import { useStore, type ChatMessage } from '../store'

const name = config.personaName

const DEGRADED_LABELS: Record<string, string> = {
  recall_unavailable: 'Memory unavailable this turn',
  extract_fallback_regex: 'Identifiers read with a simple fallback',
  reply_fallback_canned: 'Reply came from a fallback line',
}

export function Chat() {
  const { state, actions } = useStore()
  const { conversation, messages, pending } = state
  const threadRef = useRef<HTMLDivElement>(null)

  // Auto scroll to the newest message.
  useLayoutEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages.length, pending])

  return (
    <section className="flex min-h-0 flex-col rounded-3xl border border-line/60 bg-panel">
      <ChatHeader />
      <div ref={threadRef} className="relative min-h-0 flex-1 overflow-y-auto px-6 py-6">
        {!conversation ? (
          <EmptyChat onStart={actions.newChat} starting={pending === 'starting'} />
        ) : (
          <ol className="flex flex-col gap-4">
            <AnimatePresence initial={false}>
              {messages.map((m) => (
                <Bubble key={m.id} message={m} />
              ))}
              {pending === 'sending' && <TypingIndicator key="typing" />}
              {conversation.ended && (
                <motion.li key="ended" {...rise} className="flex items-center gap-3 py-2">
                  <span className="h-px flex-1 bg-line" />
                  <span className="caption-1 text-ink-3">Chat ended. Summary saved to memory.</span>
                  <span className="h-px flex-1 bg-line" />
                </motion.li>
              )}
            </AnimatePresence>
          </ol>
        )}
      </div>
      <Composer />
    </section>
  )
}

function ChatHeader() {
  const { state, actions } = useStore()
  const { conversation, pending } = state
  const live = conversation && !conversation.ended

  return (
    <header className="flex items-center justify-between gap-4 border-b border-line/60 px-6 py-4">
      <div className="flex items-center gap-3">
        <div className="relative grid size-10 place-items-center rounded-full bg-raised title-3">
          {name.slice(0, 1)}
          {live && (
            <span className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-panel bg-mem" />
          )}
        </div>
        <div>
          <p className="title-2">{name}</p>
          <p className="caption-2 text-ink-3">
            {conversation ? (
              <>
                <span className="font-mono">{conversation.id}</span>
                {conversation.ended ? ' · ended' : ' · on a call'}
              </>
            ) : (
              '72, retired schoolteacher, Bengaluru'
            )}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={actions.endChat}
          disabled={!live || pending !== 'idle'}
          className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-2 button-sm text-ink-2 transition-[background-color,color,opacity] hover:bg-raised hover:text-ink active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40"
        >
          <StopCircle size={16} weight="bold" />
          End chat
        </button>
        <button
          type="button"
          onClick={actions.newChat}
          disabled={pending !== 'idle'}
          className="inline-flex items-center gap-2 rounded-full bg-ink px-3 py-2 button-sm text-bg transition-[opacity,transform] hover:opacity-90 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40"
        >
          <Plus size={16} weight="bold" />
          New chat
          <kbd className="caption-5 rounded bg-black/10 px-1 font-mono">N</kbd>
        </button>
      </div>
    </header>
  )
}

function Bubble({ message }: { message: ChatMessage }) {
  const isAjji = message.sender === 'ajji'
  const degraded = message.degraded ?? []
  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, ease: EASE }}
      className={`flex flex-col gap-1 ${isAjji ? 'items-end' : 'items-start'}`}
    >
      <span className="caption-4 px-1 text-ink-3">
        {isAjji ? name : 'Scammer'}
        <span className="mx-1 opacity-50">·</span>
        {clockTime(message.created_at)}
      </span>
      <div
        className={`max-w-[78%] whitespace-pre-wrap break-words px-4 py-3 body-7 ${
          isAjji
            ? 'rounded-3xl rounded-br-md bg-ink text-bg'
            : 'rounded-3xl rounded-bl-md border border-line/60 bg-card text-ink'
        }`}
      >
        {message.text}
      </div>
      {degraded.length > 0 && (
        <span
          title={degraded.map((d) => DEGRADED_LABELS[d] ?? d).join('\n')}
          className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 caption-5 text-ink-3"
        >
          <WarningCircle size={12} />
          Fallback used
        </span>
      )}
    </motion.li>
  )
}

function TypingIndicator() {
  const { state } = useStore()
  const [slow, setSlow] = useState(false)

  // F5: after 4 seconds, reassure the room that the turn is still running.
  useEffect(() => {
    if (!state.sentAt) return
    const wait = Math.max(0, 4000 - (Date.now() - state.sentAt))
    const t = window.setTimeout(() => setSlow(true), wait)
    return () => window.clearTimeout(t)
  }, [state.sentAt])

  return (
    <motion.li {...rise} className="flex flex-col items-end gap-1" aria-live="polite">
      <span className="caption-4 px-1 text-ink-3">{name} is typing</span>
      <div className="flex items-center gap-1 rounded-3xl rounded-br-md bg-raised px-4 py-4">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="size-2 rounded-full bg-ink-2"
            animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
            transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.16, ease: EASE }}
          />
        ))}
      </div>
      <AnimatePresence>
        {slow && (
          <motion.span {...rise} className="caption-2 px-1 text-ink-3">
            {name} is looking for her glasses...
          </motion.span>
        )}
      </AnimatePresence>
    </motion.li>
  )
}

function EmptyChat({ onStart, starting }: { onStart: () => void; starting: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: EASE }}
      className="flex h-full flex-col items-center justify-center gap-6 text-center"
    >
      <h1 className="heading-3 hero-text max-w-[680px]">
        Every scammer she meets
        <br />
        makes her sharper
      </h1>
      <p className="body-7 max-w-[520px] text-ink-3">
        Type as the scammer. {name} stalls, collects their identifiers, and remembers them across every chat.
      </p>
      <button
        type="button"
        onClick={onStart}
        disabled={starting}
        className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-3 button-md text-bg transition-[opacity,transform] hover:opacity-90 active:scale-[0.98] disabled:opacity-40"
      >
        <Plus size={18} weight="bold" />
        {starting ? 'Dialling...' : 'Start a chat'}
      </button>
    </motion.div>
  )
}

function Composer() {
  const { state, actions } = useStore()
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const { conversation, pending } = state
  const disabled = !conversation || conversation.ended
  const busy = pending !== 'idle'

  // Autosize up to four lines.
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, 136)}px`
  }, [text])

  // Focus the input whenever a chat becomes active or a reply lands.
  useEffect(() => {
    if (!disabled && !busy) ref.current?.focus()
  }, [disabled, busy, conversation?.id])

  const submit = async () => {
    if (busy || disabled || !text.trim()) return
    const draft = text
    setText('')
    const ok = await actions.send(draft)
    if (!ok) setText(draft)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void submit()
    }
  }

  return (
    <div className="border-t border-line/60 p-4">
      <label htmlFor="composer" className="caption-3 mb-2 block px-2 uppercase tracking-wider text-ink-3">
        Type as the scammer
      </label>
      <div
        className={`flex items-end gap-2 rounded-3xl border border-line bg-card p-2 transition-[border-color,opacity] focus-within:border-ink-3 ${
          disabled ? 'opacity-50' : ''
        }`}
      >
        <textarea
          id="composer"
          ref={ref}
          rows={1}
          value={text}
          disabled={disabled}
          maxLength={2000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={
            !conversation
              ? 'Start a chat first'
              : conversation.ended
                ? 'This chat has ended. Start a new one.'
                : 'Madam, this is Inspector Sharma from CBI...'
          }
          className="max-h-[136px] min-h-10 flex-1 resize-none bg-transparent px-3 py-2 body-7 text-ink outline-none placeholder:text-ink-3 focus-visible:outline-none"
        />
        <motion.button
          type="button"
          onClick={() => void submit()}
          disabled={disabled || busy || !text.trim()}
          aria-label="Send"
          whileTap={{ scale: 0.94 }}
          className="grid size-10 shrink-0 place-items-center rounded-full bg-ink text-bg transition-opacity disabled:opacity-30"
        >
          <ArrowUp size={20} weight="bold" />
        </motion.button>
      </div>
      <p className="caption-5 mt-2 px-2 text-ink-3">Enter to send · Shift + Enter for a new line</p>
    </div>
  )
}
