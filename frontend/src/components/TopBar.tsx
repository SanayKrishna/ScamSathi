import { motion } from 'motion/react'
import { Graph, Phone, Presentation } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
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

export function TopBar({ view, onView, onOpenPresenter }: TopBarProps) {
  return (
    <header className="relative z-30 grid h-16 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-4 bg-white/80 px-6 shadow-[0_1px_0_rgb(0_0_0/0.06)] backdrop-blur-xl">
      <div className="flex min-w-0 items-center gap-3">
        <img src="/favicon.svg" alt="" className="size-8" />
        <div className="min-w-0 leading-none">
          <p className="title-1 font-semibold tracking-tight">{config.personaName}</p>
        </div>
        <span className="caption-2 hidden truncate text-ink-3 xl:block">Remembers every scammer she talks to</span>
      </div>

      <Segmented view={view} onView={onView} />

      <div className="flex items-center justify-end gap-2">
        <HealthDot />
        <MemorySwitch />
        <IconButton label="Presenter script (P)" onClick={onOpenPresenter}>
          <Presentation size={20} />
        </IconButton>
        <DemoMenu />
      </div>
    </header>
  )
}

function Segmented({ view, onView }: { view: View; onView: (v: View) => void }) {
  const items: { id: View; label: string; icon: ReactNode; key: string }[] = [
    { id: 'call', label: 'Call', icon: <Phone size={16} weight="bold" />, key: '' },
    { id: 'network', label: 'Network', icon: <Graph size={16} weight="bold" />, key: 'G' },
  ]
  return (
    <div role="tablist" aria-label="View" className="flex rounded-full bg-fill-2 p-1">
      {items.map((it) => {
        const active = view === it.id
        return (
          <button
            key={it.id}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onView(it.id)}
            className={`relative flex items-center gap-2 rounded-full px-4 py-2 button-sm transition-colors ${
              active ? 'text-ink' : 'text-ink-2 hover:text-ink'
            }`}
          >
            {active && (
              <motion.span
                layoutId="segmented-pill"
                className="absolute inset-0 rounded-full bg-white shadow-soft"
                transition={{ type: 'spring', stiffness: 500, damping: 40 }}
              />
            )}
            <span className="relative flex items-center gap-2">
              {it.icon}
              {it.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export function MemorySwitch() {
  const { state, actions } = useStore()
  const on = state.memoryEnabled
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={actions.toggleMemory}
      title="Toggle memory (M)"
      className={`flex items-center gap-3 rounded-full py-1 pr-1 pl-4 transition-[background-color] duration-500 active:scale-[0.98] ${
        on ? 'bg-mem-soft' : 'bg-fill-2'
      }`}
    >
      <span className={`button-sm whitespace-nowrap transition-colors duration-500 ${on ? 'text-[#1f8a3b]' : 'text-ink-2'}`}>
        Memory {on ? 'on' : 'off'}
      </span>
      <span
        className={`relative flex h-8 w-12 items-center rounded-full p-0.5 transition-[background-color] duration-500 ${
          on ? 'justify-end bg-mem' : 'justify-start bg-[#d1d1d6]'
        }`}
      >
        <motion.span
          layout
          transition={{ type: 'spring', stiffness: 600, damping: 36 }}
          className="size-7 rounded-full bg-white shadow-[0_2px_6px_rgb(0_0_0/0.2)]"
        />
      </span>
    </button>
  )
}

function HealthDot() {
  const { state } = useStore()
  const h = state.health
  const ok = h?.status === 'ok'
  const offline = h && h.hindsight === 'down' && h.llm === 'down' && h.db === 'down'
  const text = !h ? 'Checking' : ok ? 'All systems ok' : offline ? 'Backend offline' : 'Degraded'
  const title = h ? `Memory ${h.hindsight}, model ${h.llm}, database ${h.db}` : 'Checking services'
  return (
    <div className="flex items-center gap-2 px-2" title={title}>
      <span className="relative flex size-2">
        {ok && <span className="absolute inset-0 animate-ping rounded-full bg-mem opacity-50" />}
        <span className={`relative size-2 rounded-full ${!h ? 'bg-ink-3' : ok ? 'bg-mem' : 'bg-warn'}`} />
      </span>
      <span className="caption-1 hidden whitespace-nowrap text-ink-2 2xl:inline">{text}</span>
    </div>
  )
}

export function IconButton({
  label,
  onClick,
  children,
  active = false,
}: {
  label: string
  onClick: () => void
  children: ReactNode
  active?: boolean
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      whileTap={{ scale: 0.94 }}
      transition={{ duration: 0.2, ease: EASE }}
      className={`grid size-10 place-items-center rounded-full transition-colors ${
        active ? 'bg-fill text-ink' : 'text-ink-2 hover:bg-fill-2 hover:text-ink'
      }`}
    >
      {children}
    </motion.button>
  )
}
