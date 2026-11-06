import { AnimatePresence, motion } from 'motion/react'
import { PhoneCall, PhoneDisconnect, Sparkle, Warning } from '@phosphor-icons/react'
import { useEffect, useState, type ReactNode } from 'react'
import { config } from '../config'
import { EASE } from '../lib/motion'
import { useStore } from '../store'
import { DemoMenu } from './DemoMenu'

export type View = 'call' | 'network'

interface TopBarProps {
  view: View
  onView: (v: View) => void
  onOpenPresenter: () => void
}

const name = config.personaName

/**
 * A Dynamic Island in the middle of the bar carries the live call state and the
 * memory switch. Everything else is plain text: wordmark left, links right.
 */
export function TopBar({ view, onView, onOpenPresenter }: TopBarProps) {
  return (
    <header className="relative z-30 grid h-16 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-6 bg-stage px-6">
      <span className="title-2 font-semibold tracking-tight lowercase">{name}</span>

      <Island />

      <nav className="flex items-center justify-end gap-1">
        <TextLink active={view === 'call'} onClick={() => onView('call')}>
          Call
        </TextLink>
        <TextLink active={view === 'network'} onClick={() => onView('network')} title="Network (G)">
          Network
        </TextLink>
        <span aria-hidden className="mx-2 h-4 w-px bg-hair" />
        <TextLink onClick={onOpenPresenter} title="Presenter script (P)">
          Script
        </TextLink>
        <DemoMenu />
      </nav>
    </header>
  )
}

function TextLink({
  active,
  onClick,
  title,
  children,
}: {
  active?: boolean
  onClick: () => void
  title?: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-current={active ? 'page' : undefined}
      className={`relative rounded-md px-2 py-1 body-5 transition-colors ${
        active ? 'text-ink' : 'text-ink-2 hover:text-ink'
      }`}
    >
      {children}
      {active && (
        <motion.span
          layoutId="nav-dot"
          className="absolute -bottom-1 left-1/2 size-1 -translate-x-1/2 rounded-full bg-ink"
          transition={{ type: 'spring', stiffness: 500, damping: 40 }}
        />
      )}
    </button>
  )
}

// ── Dynamic Island ──────────────────────────────────────────────

type Flash = { tone: 'mem' | 'alert'; text: string } | null

const SPRING = { type: 'spring', stiffness: 420, damping: 34 } as const

function Island() {
  const { state } = useStore()
  const { conversation, pending, lastResponse, responseSeq, health } = state
  const flash = useFlash(responseSeq, lastResponse)
  const seconds = useCallSeconds(conversation?.startedAt, conversation?.ended ?? true)
  const degraded = health && health.status !== 'ok'

  let key: string
  let content: ReactNode
  if (flash) {
    key = `flash-${responseSeq}`
    content = (
      <span className="flex items-center gap-2">
        {flash.tone === 'alert' ? (
          <Warning size={16} weight="fill" className="text-alert" />
        ) : (
          <Sparkle size={16} weight="fill" className="text-mem" />
        )}
        <span className="body-5 whitespace-nowrap">{flash.text}</span>
      </span>
    )
  } else if (pending === 'starting') {
    key = 'ringing'
    content = (
      <span className="flex items-center gap-2">
        <motion.span
          animate={{ rotate: [0, -14, 14, -10, 10, 0] }}
          transition={{ duration: 0.9, repeat: Infinity, ease: EASE }}
          className="text-mem"
        >
          <PhoneCall size={16} weight="fill" />
        </motion.span>
        <span className="body-5">Ringing…</span>
      </span>
    )
  } else if (pending === 'sending') {
    key = 'thinking'
    content = (
      <span className="flex items-center gap-2">
        <Wave />
        <span className="body-5 whitespace-nowrap">
          {state.memoryEnabled ? 'Recalling memory…' : `${name} is replying…`}
        </span>
      </span>
    )
  } else if (conversation && !conversation.ended) {
    key = 'oncall'
    content = (
      <span className="flex items-center gap-2">
        <span className="size-2 animate-pulse rounded-full bg-alert" />
        <span className="body-5 whitespace-nowrap">Unknown caller</span>
        <span className="body-5 font-mono text-white/60 tabular-nums">{clock(seconds)}</span>
      </span>
    )
  } else if (conversation?.ended) {
    key = 'ended'
    content = (
      <span className="flex items-center gap-2">
        <PhoneDisconnect size={16} weight="fill" className="text-white/60" />
        <span className="body-5 whitespace-nowrap">Call ended · summary saved</span>
      </span>
    )
  } else {
    key = 'idle'
    content = (
      <span className="flex items-center gap-2">
        <span className={`size-2 rounded-full ${degraded ? 'bg-warn' : 'bg-white/40'}`} />
        <span className="body-5 whitespace-nowrap text-white/80">
          {degraded ? 'Backend degraded' : 'Waiting for a call'}
        </span>
      </span>
    )
  }

  return (
    <motion.div
      layout
      transition={SPRING}
      style={{ borderRadius: 999 }}
      className="flex h-10 items-center gap-3 bg-bezel py-1 pr-1 pl-4 text-white shadow-[0_8px_24px_rgb(0_0_0/0.18)]"
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={key}
          layout
          initial={{ opacity: 0, filter: 'blur(4px)', scale: 0.96 }}
          animate={{ opacity: 1, filter: 'blur(0px)', scale: 1 }}
          exit={{ opacity: 0, filter: 'blur(4px)', scale: 0.96 }}
          transition={{ duration: 0.3, ease: EASE }}
          className="flex items-center"
        >
          {content}
        </motion.span>
      </AnimatePresence>
      <MemoryChip />
    </motion.div>
  )
}

function MemoryChip() {
  const { state, actions } = useStore()
  const on = state.memoryEnabled
  return (
    <motion.button
      layout
      type="button"
      role="switch"
      aria-checked={on}
      onClick={actions.toggleMemory}
      title="Toggle memory (M)"
      whileTap={{ scale: 0.95 }}
      className={`flex h-8 items-center gap-2 rounded-full px-3 caption-3 tracking-wide transition-colors duration-300 ${
        on ? 'bg-mem text-bezel' : 'bg-white/12 text-white/70 hover:bg-white/20'
      }`}
    >
      <span className={`size-2 rounded-full transition-colors ${on ? 'bg-bezel' : 'bg-white/40'}`} />
      MEMORY {on ? 'ON' : 'OFF'}
    </motion.button>
  )
}

function Wave() {
  return (
    <span className="flex h-4 items-center gap-0.5" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <motion.span
          key={i}
          className="w-0.5 rounded-full bg-blue"
          animate={{ height: [4, 14, 6, 12, 4] }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.12, ease: EASE }}
        />
      ))}
    </span>
  )
}

// ── Hooks ───────────────────────────────────────────────────────

/** After each reply, briefly expand the island with what memory found. */
function useFlash(seq: number, res: ReturnType<typeof useStore>['state']['lastResponse']): Flash {
  const [flash, setFlash] = useState<Flash>(null)
  useEffect(() => {
    if (!res || seq === 0) return
    let next: Flash = null
    const c = res.contradiction_flags.length
    const m = res.recalled_memories.length
    const caught = c === 1 ? 'contradiction caught' : `${c} contradictions caught`
    if (c > 0 && res.memory_enabled && m > 0) next = { tone: 'alert', text: `Recalled ${m} · ${caught}` }
    else if (c > 0) next = { tone: 'alert', text: caught.replace(/^c/, 'C') }
    else if (res.memory_enabled && m > 0) next = { tone: 'mem', text: `Recalled ${m} ${m === 1 ? 'fact' : 'facts'} from earlier chats` }
    if (!next) return
    setFlash(next)
    const t = window.setTimeout(() => setFlash(null), 3200)
    return () => window.clearTimeout(t)
  }, [seq, res])
  return flash
}

function useCallSeconds(startedAt: string | undefined, stopped: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (stopped) return
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [stopped])
  return startedAt ? Math.max(0, Math.floor((now - Date.parse(startedAt)) / 1000)) : 0
}

function clock(secs: number) {
  return `${String(Math.floor(secs / 60)).padStart(2, '0')}:${String(secs % 60).padStart(2, '0')}`
}
