import { AnimatePresence, motion } from 'motion/react'
import { Brain, CloudSlash, Ear, Sparkle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { config } from '../config'
import { chatNumber } from '../lib/format'
import { EASE } from '../lib/motion'
import { useStore } from '../store'
import type { RecalledMemory } from '../types'

const name = config.personaName

/** Left of the phone: what Ajji recalled from earlier chats for the latest message. */
export function RememberColumn() {
  const { state } = useStore()
  const { lastResponse, memoryEnabled, responseSeq, pending } = state
  const memories = lastResponse?.memory_enabled ? lastResponse.recalled_memories : []
  const recallDown = lastResponse?.degraded.includes('recall_unavailable') ?? false

  let body: ReactNode
  if (!memoryEnabled) {
    body = <Quiet key="off" icon={<Brain size={24} />} title="Memory is off" text={`${name} only knows this chat.`} />
  } else if (pending === 'sending') {
    body = <Skeleton key="loading" />
  } else if (!lastResponse || !lastResponse.memory_enabled) {
    body = (
      <Quiet
        key="idle"
        icon={<Ear size={24} />}
        title="Listening"
        text="When she recognises a scammer from an earlier chat, it shows up here."
      />
    )
  } else if (recallDown) {
    body = (
      <Quiet
        key="down"
        icon={<CloudSlash size={24} />}
        title="Memory unavailable"
        text="Recall failed for this message, so she answered from this chat only."
        tone="warn"
      />
    )
  } else if (memories.length === 0) {
    body = (
      <Quiet
        key="none"
        icon={<Ear size={24} />}
        title="Nothing recalled"
        text="No earlier chat matches what this scammer just said."
      />
    )
  } else {
    body = (
      <motion.ol key={`list-${responseSeq}`} className="flex flex-col gap-3">
        {memories.map((m, i) => (
          <MemoryCard key={`${responseSeq}-${i}`} memory={m} index={i} />
        ))}
      </motion.ol>
    )
  }

  return (
    <section aria-label={`What ${name} remembers`} className="flex min-h-0 w-full max-w-[440px] flex-col justify-self-end pt-10">
      <ColumnHeading
        title="She remembers"
        sub={
          memoryEnabled && memories.length > 0 && pending !== 'sending'
            ? `${memories.length} facts from earlier chats`
            : 'From earlier chats'
        }
        dot={memoryEnabled ? 'bg-mem' : 'bg-ink-3'}
      />
      <div className="-mx-12 min-h-0 flex-1 overflow-y-auto px-12 pt-1 pb-6">
        <AnimatePresence mode="wait" initial={false}>
          {body}
        </AnimatePresence>
      </div>
    </section>
  )
}

function MemoryCard({ memory, index }: { memory: RecalledMemory; index: number }) {
  const chat = chatNumber(memory.source_conversation_id)
  const delay = index * 0.12
  return (
    <motion.li
      initial={{ opacity: 0, x: 48, scale: 0.97 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      transition={{ duration: 0.6, ease: EASE, delay }}
      className="relative rounded-2xl bg-white p-4 shadow-soft"
    >
      {/* Connector toward the phone. */}
      <motion.span
        aria-hidden
        className="absolute top-8 -right-12 h-px w-12 origin-right bg-mem/50"
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: 0.5, ease: EASE, delay: delay + 0.1 }}
      />
      <motion.span
        aria-hidden
        className="absolute top-8 -right-1 size-2 -translate-y-1/2 rounded-full bg-mem"
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.3, ease: EASE, delay: delay + 0.4 }}
      />
      <p className="body-3 text-ink">{memory.text}</p>
      <div className="mt-3 flex items-center gap-2">
        <Sparkle size={14} weight="fill" className="shrink-0 text-mem" />
        <p className="caption-2 flex-1 text-ink-2">{memory.why_relevant}</p>
        {chat ? (
          <span className="shrink-0 rounded-full bg-mem-soft px-2 py-0.5 caption-3 text-[#1f8a3b]">Chat #{chat}</span>
        ) : (
          <span className="shrink-0 rounded-full bg-fill-2 px-2 py-0.5 caption-3 text-ink-2">Pattern</span>
        )}
      </div>
    </motion.li>
  )
}

export function ColumnHeading({ title, sub, dot }: { title: string; sub: string; dot?: string }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <div>
        <h2 className="heading-5 tracking-tight">{title}</h2>
        <p className="caption-2 mt-1 flex items-center gap-2 text-ink-2">
          {dot && <span className={`size-2 rounded-full ${dot}`} />}
          {sub}
        </p>
      </div>
    </div>
  )
}

export function Quiet({
  icon,
  title,
  text,
  tone,
}: {
  icon: ReactNode
  title: string
  text: string
  tone?: 'warn'
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.4, ease: EASE }}
      className="flex flex-col items-start gap-3 rounded-2xl bg-white/60 p-6"
    >
      <span
        className={`grid size-10 place-items-center rounded-full bg-white shadow-soft ${
          tone === 'warn' ? 'text-warn' : 'text-ink-3'
        }`}
      >
        {icon}
      </span>
      <div>
        <p className="title-3 text-ink">{title}</p>
        <p className="body-6 mt-1 text-ink-2">{text}</p>
      </div>
    </motion.div>
  )
}

function Skeleton() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3, ease: EASE }}
      className="flex flex-col gap-3"
      aria-label="Recalling"
    >
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-2xl bg-white p-4 shadow-soft">
          <div className="h-4 w-11/12 animate-pulse rounded-full bg-fill-2" />
          <div className="mt-2 h-4 w-2/3 animate-pulse rounded-full bg-fill-2" />
          <div className="mt-4 h-3 w-1/3 animate-pulse rounded-full bg-fill-2" />
        </div>
      ))}
    </motion.div>
  )
}
