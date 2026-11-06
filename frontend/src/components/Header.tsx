import { config } from '../config'

export function Header() {
  return (
    <header className="flex h-20 shrink-0 items-center justify-between gap-6 px-6">
      <div className="flex items-center gap-3">
        <img src="/favicon.svg" alt="" className="size-8" />
        <span className="heading-6 tracking-tight">{config.personaName}</span>
      </div>
    </header>
  )
}
