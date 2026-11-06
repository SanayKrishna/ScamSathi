import { motion } from 'motion/react'
import { config } from '../config'
import { useStore } from '../store'
import { DemoMenu } from './DemoMenu'

export type View = 'call' | 'network'

interface TopBarProps {
  view: View
  onView: (v: View) => void
  onOpenPresenter: () => void
}

/**
 * Quiet, typographic bar in the Linear / Vercel docs style:
 * lowercase wordmark, plain word tabs with an underline, a mono status line,
 * and text buttons. No pills, no logo tile, no frosted glass.
 */
export function TopBar({ view, onView, onOpenPresenter }: TopBarProps) {
  return (
    <header className="relative z-30 flex h-14 shrink-0 items-stretch justify-between border-b border-hair bg-stage px-6">
      <div className="flex items-stretch gap-8">
        <span className="flex items-center title-2 font-semibold tracking-tight lowercase">{config.personaName}</span>
        <nav aria-label="View" className="flex items-stretch gap-6">
          <Tab active={view === 'call'} onClick={() => onView('call')}>
            Call
          </Tab>
          <Tab active={view === 'network'} onClick={() => onView('network')} hint="G">
            Network
          </Tab>
        </nav>
      </div>

      <div className="flex items-center gap-4">
        <Status />
        <span aria-hidden className="h-4 w-px bg-hair" />
        <button
          type="button"
          onClick={onOpenPresenter}
          title="Presenter script (P)"
          className="rounded-md px-2 py-1 body-5 text-ink-2 transition-colors hover:text-ink"
        >
          Script
        </button>
        <DemoMenu />
      </div>
    </header>
  )
}

function Tab({
  active,
  onClick,
  hint,
  children,
}: {
  active: boolean
  onClick: () => void
  hint?: string
  children: string
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`group relative flex items-center gap-2 body-5 transition-colors ${
        active ? 'text-ink' : 'text-ink-2 hover:text-ink'
      }`}
    >
      {children}
      {hint && (
        <kbd className="caption-5 rounded border border-hair px-1 font-mono text-ink-3 opacity-0 transition-opacity group-hover:opacity-100">
          {hint}
        </kbd>
      )}
      {active && (
        <motion.span
          layoutId="tab-underline"
          className="absolute right-0 -bottom-px left-0 h-0.5 bg-ink"
          transition={{ type: 'spring', stiffness: 500, damping: 40 }}
        />
      )}
    </button>
  )
}

/** "● live · memory on" in mono. The memory part is the toggle (also M). */
function Status() {
  const { state, actions } = useStore()
  const h = state.health
  const ok = h?.status === 'ok'
  const offline = h && h.hindsight === 'down' && h.llm === 'down' && h.db === 'down'
  const label = !h ? 'checking' : ok ? 'live' : offline ? 'offline' : 'degraded'
  const dot = !h ? 'bg-ink-3' : ok ? 'bg-mem' : 'bg-warn'
  const on = state.memoryEnabled
  const title = h ? `Memory ${h.hindsight}, model ${h.llm}, database ${h.db}` : 'Checking services'

  return (
    <div className="flex items-center gap-2 font-mono caption-4 text-ink-2">
      <span className="flex items-center gap-2" title={title}>
        <span className="relative flex size-2">
          {ok && <span className="absolute inset-0 animate-ping rounded-full bg-mem opacity-40" />}
          <span className={`relative size-2 rounded-full ${dot}`} />
        </span>
        {label}
      </span>
      <span className="text-ink-3">·</span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        onClick={actions.toggleMemory}
        title="Toggle memory (M)"
        className="flex items-center gap-2 rounded-md px-1 py-0.5 transition-colors hover:bg-fill-2"
      >
        <span className={on ? 'text-ink' : 'text-ink-2'}>memory {on ? 'on' : 'off'}</span>
        <span
          className={`flex h-4 w-7 items-center rounded-full p-0.5 transition-colors duration-300 ${
            on ? 'justify-end bg-mem' : 'justify-start bg-[#d1d1d6]'
          }`}
        >
          <motion.span
            layout
            transition={{ type: 'spring', stiffness: 600, damping: 36 }}
            className="size-3 rounded-full bg-white shadow-[0_1px_2px_rgb(0_0_0/0.2)]"
          />
        </span>
      </button>
    </div>
  )
}
