import { AnimatePresence, motion } from 'motion/react'
import {
  ArrowUp,
  BatteryFull,
  CellSignalFull,
  PhoneCall,
  PhoneDisconnect,
  User,
  WarningCircle,
  WifiHigh,
} from '@phosphor-icons/react'
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { config } from '../config'
import { EASE } from '../lib/motion'
import { useStore, type ChatMessage } from '../store'

const name = config.personaName

const DEGRADED_LABELS: Record<string, string> = {
  recall_unavailable: 'Memory unavailable this turn',
  extract_fallback_regex: 'Identifiers read with a simple fallback',
  reply_fallback_canned: 'Reply came from a fallback line',
}

/** Ajji's iPhone. The thread is her side of the conversation: her replies are blue, the scammer's are gray. */
export function Phone() {
  const { state, actions } = useStore()
  const { conversation, pending } = state
  const live = !!conversation && !conversation.ended

  return (
    <div className="flex h-full min-h-0 flex-col items-center gap-4">
      <p className="caption-1 text-ink-3">{name}'s phone</p>

      {/* Bezel 56px with 12px gap gives a 44px screen radius (skill B3). */}
      <div className="relative aspect-[1/2] h-[min(calc(100dvh-236px),780px)] min-h-[440px] rounded-[56px] bg-bezel p-3 shadow-phone">
        <div className="relative flex h-full flex-col overflow-hidden rounded-[44px] bg-white">
          <StatusBar />
          {conversation ? <Conversation /> : <IncomingCall onAnswer={actions.newChat} answering={pending === 'starting'} />}
          <div className="flex shrink-0 justify-center pt-1 pb-2">
            <span className="h-1 w-32 rounded-full bg-ink/90" />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <PillButton onClick={actions.endChat} disabled={!live || pending !== 'idle'} tone="light">
          <PhoneDisconnect size={16} weight="bold" />
          End chat
        </PillButton>
      </div>
    </div>
  )
}

function StatusBar() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  return (
    <div className="relative flex h-12 shrink-0 items-center justify-between px-[8%]">
      <span className="body-4 tabular-nums">
        {now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: false })}
      </span>
      <span aria-hidden className="absolute top-3 left-1/2 h-8 w-[30%] -translate-x-1/2 rounded-full bg-bezel" />
      <span className="flex items-center gap-1 text-ink">
        <CellSignalFull size={16} weight="fill" />
        <WifiHigh size={16} weight="bold" />
        <BatteryFull size={20} weight="fill" />
      </span>
    </div>
  )
}

function IncomingCall({ onAnswer, answering }: { onAnswer: () => void; answering: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6, ease: EASE }}
      className="flex flex-1 flex-col items-center justify-between px-6 pt-12 pb-12 text-center"
    >
      <div className="flex flex-col items-center gap-3">
        <span className="caption-1 text-ink-3">Incoming call</span>
        <Avatar size="lg" />
        <p className="heading-5">Unknown caller</p>
        <p className="body-6 max-w-[220px] text-ink-2">
          Answer as {name}, then type what the scammer says.
        </p>
      </div>
      <div className="flex flex-col items-center gap-2">
        <motion.button
          type="button"
          onClick={onAnswer}
          disabled={answering}
          aria-label="Answer the call and start a chat"
          whileTap={{ scale: 0.94 }}
          className="relative grid size-16 place-items-center rounded-full bg-mem text-white disabled:opacity-60"
        >
          <motion.span
            aria-hidden
            className="absolute inset-0 rounded-full bg-mem"
            animate={{ scale: [1, 1.5], opacity: [0.45, 0] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: EASE }}
          />
          <PhoneCall size={28} weight="fill" className="relative" />
        </motion.button>
        <span className="caption-1 text-ink-2">{answering ? 'Connecting...' : 'Answer'}</span>
      </div>
    </motion.div>
  )
}

function Avatar({ size = 'sm' }: { size?: 'sm' | 'lg' }) {
  const big = size === 'lg'
  return (
    <span
      className={`grid place-items-center rounded-full bg-fill text-ink-3 ${big ? 'size-24' : 'size-12'}`}
    >
      <User size={big ? 48 : 24} weight="fill" />
    </span>
  )
}

function Conversation() {
  const { state } = useStore()
  const { conversation, messages, pending } = state
  const threadRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages.length, pending])

  if (!conversation) return null

  return (
    <>
      <header className="flex shrink-0 flex-col items-center gap-1 pb-3 shadow-[0_1px_0_rgb(0_0_0/0.06)]">
        <Avatar />
        <p className="body-5">Unknown caller</p>
        <CallTimer startedAt={conversation.startedAt} ended={conversation.ended} />
      </header>

      <div ref={threadRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <p className="caption-4 mb-3 text-center text-ink-3">
          Today {new Date(conversation.startedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
        </p>
        <ol className="flex flex-col gap-1">
          <AnimatePresence initial={false}>
            {messages.map((m, i) => (
              <Bubble key={m.id} message={m} last={i === messages.length - 1 || messages[i + 1].sender !== m.sender} />
            ))}
            {pending === 'sending' && <TypingIndicator key="typing" />}
            {conversation.ended && (
              <motion.li
                key="ended"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: EASE }}
                className="mt-4 flex flex-col items-center gap-1 text-center"
              >
                <span className="rounded-full bg-fill-2 px-3 py-1 caption-4 text-ink-2">Call ended</span>
                <span className="caption-5 text-ink-3">Summary saved to memory</span>
              </motion.li>
            )}
          </AnimatePresence>
        </ol>
      </div>

      <Composer />
    </>
  )
}

function CallTimer({ startedAt, ended }: { startedAt: string; ended: boolean }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (ended) return
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [ended])
  const secs = Math.max(0, Math.floor((now - Date.parse(startedAt)) / 1000))
  const mm = String(Math.floor(secs / 60)).padStart(2, '0')
  const ss = String(secs % 60).padStart(2, '0')
  return (
    <span className="flex items-center gap-1 caption-4 text-ink-3 tabular-nums">
      {!ended && <span className="size-2 animate-pulse rounded-full bg-alert" />}
      {ended ? 'Call ended' : `Scam call · ${mm}:${ss}`}
    </span>
  )
}

function Bubble({ message, last }: { message: ChatMessage; last: boolean }) {
  const mine = message.sender === 'ajji'
  const degraded = message.degraded ?? []
  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.45, ease: EASE }}
      className={`flex flex-col ${mine ? 'items-end' : 'items-start'} ${last ? 'mb-2' : ''}`}
      style={{ transformOrigin: mine ? 'bottom right' : 'bottom left' }}
    >
      <div
        className={`max-w-[80%] whitespace-pre-wrap break-words px-4 py-2 body-3 ${
          mine
            ? `rounded-[20px] bg-blue text-white ${last ? 'rounded-br-md' : ''}`
            : `rounded-[20px] bg-fill text-ink ${last ? 'rounded-bl-md' : ''}`
        }`}
      >
        {message.text}
      </div>
      {last && (
        <span className="caption-5 mt-1 px-2 text-ink-3">
          {mine ? name : 'Scammer'}
        </span>
      )}
      {degraded.length > 0 && (
        <span
          title={degraded.map((d) => DEGRADED_LABELS[d] ?? d).join('\n')}
          className="mt-1 inline-flex items-center gap-1 px-2 caption-4 text-warn"
        >
          <WarningCircle size={12} weight="fill" />
          Fallback used
        </span>
      )}
    </motion.li>
  )
}

function TypingIndicator() {
  const { state } = useStore()
  const [slow, setSlow] = useState(false)

  // After 4 seconds, reassure the room that the turn is still running.
  useEffect(() => {
    if (!state.sentAt) return
    const wait = Math.max(0, 4000 - (Date.now() - state.sentAt))
    const t = window.setTimeout(() => setSlow(true), wait)
    return () => window.clearTimeout(t)
  }, [state.sentAt])

  return (
    <motion.li
      initial={{ opacity: 0, y: 8, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.35, ease: EASE }}
      className="flex flex-col items-end gap-1"
      style={{ transformOrigin: 'bottom right' }}
      aria-live="polite"
      aria-label={`${name} is typing`}
    >
      <div className="flex items-center gap-1 rounded-[20px] rounded-br-md bg-blue/15 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="size-2 rounded-full bg-blue"
            animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
            transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.16, ease: EASE }}
          />
        ))}
      </div>
      <AnimatePresence>
        <motion.span
          key={slow ? 'slow' : 'typing'}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, ease: EASE }}
          className="caption-5 px-2 text-ink-3"
        >
          {slow ? `${name} is looking for her glasses...` : `${name} is typing...`}
        </motion.span>
      </AnimatePresence>
    </motion.li>
  )
}

function Composer() {
  const { state, actions } = useStore()
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const { conversation, pending } = state
  const disabled = !conversation || conversation.ended
  const busy = pending !== 'idle'

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }, [text])

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
    <div className="shrink-0 px-3 pt-2">
      <label htmlFor="composer" className="sr-only">
        Type as the scammer
      </label>
      <div
        className={`flex items-end gap-1 rounded-[22px] bg-white py-1 pr-1 pl-4 shadow-[inset_0_0_0_1px_#d1d1d6] transition-shadow focus-within:shadow-[inset_0_0_0_1px_#0a84ff] ${
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
          placeholder={disabled ? 'Call ended' : 'Type as the scammer'}
          className="max-h-[120px] min-h-8 flex-1 resize-none bg-transparent py-1 body-3 text-ink outline-none placeholder:text-ink-3 focus-visible:outline-none"
        />
        <motion.button
          type="button"
          onClick={() => void submit()}
          disabled={disabled || busy || !text.trim()}
          aria-label="Send"
          whileTap={{ scale: 0.9 }}
          className="grid size-8 shrink-0 place-items-center rounded-full bg-blue text-white transition-opacity disabled:opacity-30"
        >
          <ArrowUp size={16} weight="bold" />
        </motion.button>
      </div>
    </div>
  )
}

function PillButton({
  onClick,
  disabled,
  tone,
  kbd,
  children,
}: {
  onClick: () => void
  disabled?: boolean
  tone: 'dark' | 'light'
  kbd?: string
  children: ReactNode
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      whileTap={{ scale: 0.96 }}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 button-sm transition-[opacity,background-color] disabled:pointer-events-none disabled:opacity-40 ${
        tone === 'dark' ? 'bg-ink text-white hover:bg-ink/85' : 'bg-white text-ink shadow-soft hover:bg-fill-2'
      }`}
    >
      {children}
      {kbd && <kbd className="caption-5 rounded bg-white/15 px-1 font-mono">{kbd}</kbd>}
    </motion.button>
  )
}
