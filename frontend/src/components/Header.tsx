import { animate, motion, useMotionValue, useTransform } from 'motion/react'
import { Presentation } from '@phosphor-icons/react'
import { useEffect } from 'react'
import { config } from '../config'
import { EASE } from '../lib/motion'
import { useStore } from '../store'
import { DemoMenu } from './DemoMenu'

export function Header({ onOpenPresenter }: { onOpenPresenter: () => void }) {
  const { state } = useStore()
  const { stats } = state

  return (
    <header className="flex h-24 shrink-0 items-center justify-between gap-6 px-6">
      <div className="flex min-w-0 items-center gap-3">
        <img src="/favicon.svg" alt="" className="size-10" />
        <div className="min-w-0">
          <p className="heading-5 tracking-tight">{config.personaName}</p>
          <p className="caption-2 hidden truncate text-ink-3 2xl:block">Remembers every scammer she talks to</p>
        </div>
      </div>

      <dl className="flex items-stretch gap-2">
        <Stat label="Conversations" value={stats?.conversations} />
        <Stat
          label="Minutes wasted"
          value={stats?.total_minutes_wasted_estimate}
          suffix={stats?.minutes_is_estimate !== false ? 'est.' : undefined}
        />
        <Stat label="Rings detected" value={stats?.rings_detected} />
        <Stat label="Contradictions" value={stats?.contradictions_caught} tone="alert" />
      </dl>

      <div className="flex items-center gap-3">
        <HealthDot />
        <MemoryToggle />
        <button
          type="button"
          onClick={onOpenPresenter}
          title="Presenter script (P)"
          aria-label="Presenter script"
          className="grid size-14 place-items-center rounded-full border border-line/60 text-ink-2 transition-[background-color,color] hover:bg-panel hover:text-ink active:scale-[0.98]"
        >
          <Presentation size={22} />
        </button>
        <DemoMenu />
      </div>
    </header>
  )
}

function Stat({
  label,
  value,
  suffix,
  tone,
}: {
  label: string
  value: number | undefined
  suffix?: string
  tone?: 'alert'
}) {
  return (
    <div className="flex min-w-36 flex-col justify-center rounded-2xl border border-line/60 bg-panel px-4 py-2">
      <dt className="caption-4 whitespace-nowrap text-ink-3">{label}</dt>
      <dd className={`flex items-baseline gap-1 heading-4 tabular-nums ${tone === 'alert' ? 'text-alert' : 'text-ink'}`}>
        {value === undefined ? (
          <span className="block h-9 w-16 animate-pulse rounded-lg bg-raised" />
        ) : (
          <AnimatedNumber value={value} />
        )}
        {suffix && value !== undefined && <span className="caption-1 text-ink-3">{suffix}</span>}
      </dd>
    </div>
  )
}

function AnimatedNumber({ value }: { value: number }) {
  const mv = useMotionValue(value)
  const text = useTransform(mv, (v) => Math.round(v).toLocaleString())
  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.9, ease: EASE })
    return () => controls.stop()
  }, [mv, value])
  return <motion.span>{text}</motion.span>
}

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
      className={`relative flex h-14 w-56 items-center rounded-full border p-1 transition-[background-color,border-color] duration-500 active:scale-[0.98] ${
        on ? 'border-mem/60 bg-mem/15' : 'border-line bg-panel'
      }`}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 500, damping: 38 }}
        className={`absolute top-1 bottom-1 w-12 rounded-full ${on ? 'right-1 bg-mem' : 'left-1 bg-ink-3'}`}
        style={{ boxShadow: on ? '0 0 24px rgba(74, 222, 128, 0.45)' : 'none' }}
      />
      <span
        className={`flex flex-1 items-center justify-center gap-2 button-md tracking-wide transition-[padding,color] duration-500 ${
          on ? 'pr-12 text-mem' : 'pl-12 text-ink-2'
        }`}
      >
        MEMORY {on ? 'ON' : 'OFF'}
        <kbd className="caption-5 rounded border border-current/30 px-1 font-mono opacity-60">M</kbd>
      </span>
    </button>
  )
}

function HealthDot() {
  const { state } = useStore()
  const h = state.health
  const ok = h?.status === 'ok'
  const label = !h
    ? 'Checking services'
    : `Memory ${h.hindsight}, model ${h.llm}, database ${h.db}`
  return (
    <div className="flex items-center gap-2 rounded-full border border-line/60 px-3 py-2" title={label}>
      <span className="relative flex size-2">
        {ok && <span className="absolute inset-0 animate-ping rounded-full bg-mem opacity-60" />}
        <span className={`relative size-2 rounded-full ${!h ? 'bg-ink-3' : ok ? 'bg-mem' : 'bg-warn'}`} />
      </span>
      <span className="caption-1 hidden whitespace-nowrap text-ink-2 2xl:inline">
        {!h
          ? 'Checking'
          : ok
            ? 'All systems ok'
            : h.hindsight === 'down' && h.llm === 'down' && h.db === 'down'
              ? 'Backend offline'
              : 'Degraded'}
      </span>
    </div>
  )
}
