import type { ReactNode } from 'react'

interface PanelProps {
  title: ReactNode
  meta?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}

/** Rounded 24px surface with 12px padding, so inner cards use 12px radius (skill B3). */
export function Panel({ title, meta, children, className = '', bodyClassName = '' }: PanelProps) {
  return (
    <section className={`flex min-h-0 flex-col rounded-3xl border border-line/60 bg-panel p-3 ${className}`}>
      <header className="flex items-center justify-between gap-3 px-2 pb-3 pt-1">
        <h2 className="title-3 text-ink-2">{title}</h2>
        {meta && <div className="caption-4 text-ink-3">{meta}</div>}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  )
}
