import { useStore } from '../store'
import { AnimatedNumber } from './AnimatedNumber'

export function StatStrip() {
  const { state } = useStore()
  const s = state.stats
  const items: { label: string; value: number | undefined; suffix?: string; tone?: string }[] = [
    { label: 'conversations', value: s?.conversations },
    { label: 'minutes wasted', value: s?.total_minutes_wasted_estimate, suffix: s?.minutes_is_estimate !== false ? 'est.' : undefined },
    { label: 'rings detected', value: s?.rings_detected },
    { label: 'contradictions caught', value: s?.contradictions_caught, tone: 'text-alert' },
  ]
  return (
    <dl className="mx-auto flex items-center rounded-full bg-white px-2 py-2 shadow-soft">
      {items.map((it, i) => (
        <div key={it.label} className="flex items-center">
          {i > 0 && <span aria-hidden className="mx-1 h-6 w-px bg-hair" />}
          <div className="flex items-baseline gap-2 px-4">
            <dd className={`heading-6 tabular-nums ${it.tone ?? 'text-ink'}`}>
              {it.value === undefined ? (
                <span className="inline-block h-6 w-8 animate-pulse rounded-md bg-fill-2 align-middle" />
              ) : (
                <AnimatedNumber value={it.value} />
              )}
            </dd>
            <dt className="caption-2 whitespace-nowrap text-ink-2">
              {it.label}
              {it.suffix && it.value !== undefined && <span className="ml-1 text-ink-3">{it.suffix}</span>}
            </dt>
          </div>
        </div>
      ))}
    </dl>
  )
}
