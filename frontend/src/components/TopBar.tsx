import { motion } from 'motion/react'
import type { ReactNode } from 'react'
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
 * Modelled on the Notion Calendar site header: logo mark left, plain dark
 * links in the centre, the memory switch and a solid black Script button right.
 */
export function TopBar({ view, onView, onOpenPresenter }: TopBarProps) {
  return (
    <header className="relative z-30 grid h-16 shrink-0 grid-cols-[1fr_auto_1fr] items-center bg-white px-6 shadow-[0_1px_0_rgb(0_0_0/0.05)]">
      <div className="flex items-center gap-2">
        <img src="/favicon.svg" alt="" className="size-8" />
        <span className="title-2 font-semibold tracking-tight">{config.personaName}</span>
      </div>

      <nav aria-label="Main" className="flex items-center gap-1">
        <NavLink active={view === 'call'} onClick={() => onView('call')}>
          Call
        </NavLink>
        <NavLink active={view === 'network'} onClick={() => onView('network')} title="Network (G)">
          Network
        </NavLink>
        <DemoMenu />
      </nav>

      <div className="flex items-center justify-end gap-2">
        <MemoryToggle />
        <motion.button
          type="button"
          onClick={onOpenPresenter}
          whileTap={{ scale: 0.97 }}
          title="Presenter script (P)"
          className="rounded-lg bg-ink px-4 py-2 button-sm text-white transition-[background-color] hover:bg-ink/85"
        >
          Script
        </motion.button>
      </div>
    </header>
  )
}

function NavLink({
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
      className={`rounded-lg px-3 py-2 body-3 transition-colors hover:bg-fill-2 ${
        active ? 'font-medium text-ink' : 'text-ink/80 hover:text-ink'
      }`}
    >
      {children}
    </button>
  )
}

/** Sits where Notion has "Log in": quiet text with a small switch. M toggles it too. */
function MemoryToggle() {
  const { state, actions } = useStore()
  const on = state.memoryEnabled
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={actions.toggleMemory}
      title="Toggle memory (M)"
      className="flex items-center gap-2 rounded-lg px-3 py-2 body-3 text-ink transition-colors hover:bg-fill-2"
    >
      Memory {on ? 'on' : 'off'}
      <span
        className={`flex h-5 w-8 items-center rounded-full p-0.5 transition-colors duration-300 ${
          on ? 'justify-end bg-mem' : 'justify-start bg-[#d1d1d6]'
        }`}
      >
        <motion.span
          layout
          transition={{ type: 'spring', stiffness: 600, damping: 36 }}
          className="size-4 rounded-full bg-white shadow-[0_1px_2px_rgb(0_0_0/0.25)]"
        />
      </span>
    </button>
  )
}
