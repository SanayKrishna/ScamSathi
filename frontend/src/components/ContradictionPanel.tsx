import { AnimatePresence, motion } from 'motion/react'
import { ArrowsLeftRight, Brain, SealCheck } from '@phosphor-icons/react'
import { chatNumber } from '../lib/format'
import { EASE } from '../lib/motion'
import { useStore, type SeenContradiction } from '../store'
import type { ContradictionKind } from '../types'
import { EmptyState } from './MemoryPanel'
import { Panel } from './Panel'

const KIND_LABEL: Record<ContradictionKind, string> = {
  case_number_changed: 'Case number changed',
  alias_shares_upi: 'UPI used by another alias',
  alias_shares_phone: 'Phone used by another alias',
  agency_changed: 'Agency changed',
}

export function ContradictionPanel() {
  const { state } = useStore()
  const { contradictions, memoryEnabled } = state

  return (
    <Panel
      title="Contradictions caught"
      meta={contradictions.length > 0 ? <span className="text-alert">{contradictions.length} in this chat</span> : null}
      bodyClassName="overflow-y-auto"
    >
      {contradictions.length === 0 ? (
        memoryEnabled ? (
          <EmptyState
            icon={<SealCheck size={28} />}
            title="None caught yet"
            text="When a scammer's story clashes with an earlier chat, it shows up here."
          />
        ) : (
          <EmptyState
            icon={<Brain size={28} />}
            title="Needs memory"
            text="Contradictions come from past chats. Turn memory on to catch them."
          />
        )
      ) : (
        <ol className="flex flex-col gap-2">
          <AnimatePresence initial={false}>
            {contradictions.map((c) => (
              <ContradictionCard key={c.key} flag={c} />
            ))}
          </AnimatePresence>
        </ol>
      )}
    </Panel>
  )
}

function ContradictionCard({ flag }: { flag: SeenContradiction }) {
  const high = flag.severity === 'high'
  const chat = chatNumber(flag.source_conversation_id)
  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: 24, scale: 0.98 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.5, ease: EASE }}
      className={`relative overflow-hidden rounded-xl border p-4 ${
        high ? 'border-alert/70 bg-alert-dim' : 'border-alert/25 bg-card'
      }`}
    >
      {high && (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-xl bg-alert/15"
          initial={{ opacity: 1 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 1.6, ease: EASE }}
        />
      )}
      <div className="relative flex items-center justify-between gap-3">
        <p className="title-2 text-alert">{KIND_LABEL[flag.kind] ?? flag.kind}</p>
        <span
          className={`rounded-full px-2 py-0.5 caption-3 uppercase tracking-wider ${
            high ? 'bg-alert text-bg' : 'border border-alert/40 text-alert'
          }`}
        >
          {flag.severity}
        </span>
      </div>
      <div className="relative mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <Claim label="Now" value={flag.claim_now} strong />
        <ArrowsLeftRight size={18} className="text-ink-3" />
        <Claim label={chat ? `Before · chat #${chat}` : 'Before'} value={flag.claim_before} />
      </div>
    </motion.li>
  )
}

function Claim({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="min-w-0 rounded-lg bg-black/30 px-3 py-2">
      <p className="caption-3 uppercase tracking-wider text-ink-3">{label}</p>
      <p className={`body-7 truncate font-mono ${strong ? 'text-ink' : 'text-ink-2'}`} title={value}>
        {value}
      </p>
    </div>
  )
}
