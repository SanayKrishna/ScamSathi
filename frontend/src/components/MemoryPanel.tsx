import { AnimatePresence, motion } from 'motion/react'
import { Brain, CloudSlash, MagnifyingGlass, Sparkle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { config } from '../config'
import { chatNumber } from '../lib/format'
import { EASE } from '../lib/motion'
import { useStore } from '../store'
import type { RecalledMemory } from '../types'
import { Panel } from './Panel'

const name = config.personaName

export function MemoryPanel() {
  const { state } = useStore()
  const { lastResponse, memoryEnabled, responseSeq, pending } = state
  const memories = lastResponse?.memory_enabled ? lastResponse.recalled_memories : []
  const recallDown = lastResponse?.degraded.includes('recall_unavailable') ?? false

  let body: ReactNode
  if (!memoryEnabled) {
    body = (
      <EmptyState
        key="off"
        icon={<Brain size={28} />}
        title="Memory is off"
        text={`${name} only knows this chat.`}
      />
    )
  } else if (pending === 'sending') {
    body = <Skeleton key="loading" />
  } else if (!lastResponse || !lastResponse.memory_enabled) {
    body = (
      <EmptyState
        key="idle"
        icon={<MagnifyingGlass size={28} />}
        title="Listening"
        text="Send a scammer message. Anything she remembers about them appears here."
      />
    )
  } else if (recallDown) {
    body = (
      <EmptyState
        key="down"
        icon={<CloudSlash size={28} />}
        title="Memory unavailable"
        text="Recall failed for this message, so she answered from this chat only."
      />
    )
  } else if (memories.length === 0) {
    body = (
      <EmptyState
        key="none"
        icon={<MagnifyingGlass size={28} />}
        title="Nothing recalled for this message"
        text="No past chat matches what this scammer just said."
      />
    )
  } else {
    body = (
      <motion.ol key={`list-${responseSeq}`} className="flex flex-col gap-2">
        {memories.map((m, i) => (
          <MemoryCard key={`${responseSeq}-${i}`} memory={m} index={i} />
        ))}
      </motion.ol>
    )
  }

  return (
    <Panel
      title={`What ${name} remembers`}
      meta={
        memoryEnabled && memories.length > 0 && pending !== 'sending' ? (
          <span className="inline-flex items-center gap-2 text-mem">
            <Sparkle size={14} weight="fill" />
            {memories.length} recalled
          </span>
        ) : null
      }
      bodyClassName="overflow-y-auto"
    >
      <AnimatePresence mode="wait" initial={false}>
        {body}
      </AnimatePresence>
    </Panel>
  )
}

function MemoryCard({ memory, index }: { memory: RecalledMemory; index: number }) {
  const chat = chatNumber(memory.source_conversation_id)
  return (
    <motion.li
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE, delay: index * 0.12 }}
      className="rounded-xl border border-line/60 bg-card p-4"
    >
      <p className="body-7 text-ink">{memory.text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <p className="body-3 flex-1 text-ink-3">{memory.why_relevant}</p>
        {chat && (
          <span className="rounded-full border border-mem/30 bg-mem-dim/40 px-2 py-0.5 caption-4 text-mem">
            from chat #{chat}
          </span>
        )}
        {!chat && (
          <span className="rounded-full border border-line px-2 py-0.5 caption-4 text-ink-3">pattern</span>
        )}
      </div>
    </motion.li>
  )
}

export function EmptyState({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.4, ease: EASE }}
      className="flex h-full min-h-32 flex-col items-center justify-center gap-2 px-6 text-center"
    >
      <div className="mb-1 grid size-12 place-items-center rounded-full bg-card text-ink-3">{icon}</div>
      <p className="title-2 text-ink-2">{title}</p>
      <p className="body-3 max-w-[360px] text-ink-3">{text}</p>
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
      className="flex flex-col gap-2"
      aria-label="Recalling"
    >
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-xl border border-line/40 bg-card p-4">
          <div className="h-4 w-11/12 animate-pulse rounded-full bg-raised" />
          <div className="mt-2 h-4 w-2/3 animate-pulse rounded-full bg-raised" />
          <div className="mt-4 h-3 w-1/3 animate-pulse rounded-full bg-raised/70" />
        </div>
      ))}
    </motion.div>
  )
}
