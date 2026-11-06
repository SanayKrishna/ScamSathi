import { AnimatePresence, motion } from 'motion/react'
import { ArrowRight, Brain, SealCheck, Warning } from '@phosphor-icons/react'
import { chatNumber } from '../lib/format'
import { EASE } from '../lib/motion'
import { useStore, type SeenContradiction } from '../store'
import type { ContradictionKind, Ioc, IocType, ScriptStage } from '../types'
import { ColumnHeading, Quiet } from './RememberColumn'

const KIND_LABEL: Record<ContradictionKind, string> = {
  case_number_changed: 'Case number changed',
  alias_shares_upi: 'UPI used by another alias',
  alias_shares_phone: 'Phone used by another alias',
  agency_changed: 'Agency changed',
}

const IOC_LABEL: Record<IocType, string> = {
  alias: 'Alias',
  upi: 'UPI',
  phone: 'Phone',
  case_number: 'Case',
  agency_claimed: 'Agency',
  script_stage: 'Stage',
}

const IOC_DOT: Record<IocType, string> = {
  alias: 'bg-ink',
  upi: 'bg-mem',
  phone: 'bg-blue',
  case_number: 'bg-alert',
  agency_claimed: 'bg-ink-3',
  script_stage: 'bg-warn',
}

const STAGE_LABEL: Record<ScriptStage, string> = {
  intro_threat: 'Intro threat',
  fake_case_number: 'Fake case number',
  video_call_demand: 'Video call demand',
  isolation: 'Isolation',
  verification_transfer: 'Verification transfer',
}

/** Right of the phone: contradictions with earlier chats, then every identifier heard in this chat. */
export function CaughtColumn() {
  const { state } = useStore()
  const { contradictions, memoryEnabled } = state
  const iocs = state.heard

  return (
    <section aria-label="Caught" className="flex min-h-0 w-full max-w-[440px] flex-col justify-self-start pt-10">
      <ColumnHeading
        title="Caught"
        sub={contradictions.length > 0 ? `${contradictions.length} ${contradictions.length === 1 ? "contradiction" : "contradictions"} in this chat` : 'Contradictions with earlier chats'}
        dot={contradictions.length > 0 ? 'bg-alert' : undefined}
      />
      <div className="-mx-12 min-h-0 flex-1 overflow-y-auto px-12 pt-1 pb-6">
        {contradictions.length === 0 ? (
          memoryEnabled ? (
            <Quiet
              icon={<SealCheck size={24} />}
              title="Nothing caught yet"
              text="When a story clashes with an earlier chat, it lands here."
            />
          ) : (
            <Quiet
              icon={<Brain size={24} />}
              title="Needs memory"
              text="Contradictions come from earlier chats. Turn memory on to catch them."
            />
          )
        ) : (
          <ol className="flex flex-col gap-3">
            <AnimatePresence initial={false}>
              {contradictions.map((c) => (
                <ContradictionCard key={c.key} flag={c} />
              ))}
            </AnimatePresence>
          </ol>
        )}

        <Identifiers iocs={iocs} />
      </div>
    </section>
  )
}

function ContradictionCard({ flag }: { flag: SeenContradiction }) {
  const high = flag.severity === 'high'
  const chat = chatNumber(flag.source_conversation_id)
  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -48, scale: 0.97 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.6, ease: EASE }}
      className={`relative rounded-2xl bg-white p-4 shadow-soft ${high ? 'ring-1 ring-alert/30' : ''}`}
    >
      <motion.span
        aria-hidden
        className="absolute top-8 -left-12 h-px w-12 origin-left bg-alert/50"
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
      />
      <motion.span
        aria-hidden
        className="absolute top-8 -left-1 size-2 -translate-y-1/2 rounded-full bg-alert"
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.3, ease: EASE, delay: 0.4 }}
      />
      {high && (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-2xl bg-alert/10"
          initial={{ opacity: 1 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 1.6, ease: EASE }}
        />
      )}

      <div className="relative flex items-center gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-alert-soft text-alert">
          <Warning size={16} weight="fill" />
        </span>
        <p className="title-3 flex-1">{KIND_LABEL[flag.kind] ?? flag.kind}</p>
        <span
          className={`rounded-full px-2 py-0.5 caption-3 ${high ? 'bg-alert text-white' : 'bg-alert-soft text-alert'}`}
        >
          {high ? 'High' : 'Low'}
        </span>
      </div>

      <div className="relative mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <Claim label={chat ? `Chat #${chat}` : 'Before'} value={flag.claim_before} muted />
        <ArrowRight size={16} className="text-ink-3" />
        <Claim label="Now" value={flag.claim_now} />
      </div>
    </motion.li>
  )
}

function Claim({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="min-w-0 rounded-lg bg-fill-2 px-3 py-2">
      <p className="caption-4 text-ink-3">{label}</p>
      <p className={`title-3 truncate font-mono ${muted ? 'text-ink-2 line-through decoration-alert/50' : 'text-ink'}`} title={value}>
        {value}
      </p>
    </div>
  )
}

function Identifiers({ iocs }: { iocs: Ioc[] }) {
  const stage = iocs.find((i) => i.type === 'script_stage')
  const rest = iocs.filter((i) => i.type !== 'script_stage')
  return (
    <div className="mt-8">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="title-3">Identifiers heard</h3>
        {stage && (
          <span className="rounded-full bg-white px-2 py-0.5 caption-4 text-ink-2 shadow-soft">
            Stage · {STAGE_LABEL[stage.value as ScriptStage] ?? stage.value}
          </span>
        )}
      </div>
      {rest.length === 0 ? (
        <p className="body-6 text-ink-3">Names, UPI handles, phones and case numbers she hears appear here.</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          <AnimatePresence initial={false}>
            {rest.map((i) => (
              <motion.li
                key={`${i.type}|${i.value}`}
                layout
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, ease: EASE }}
                className="inline-flex items-center gap-2 rounded-full bg-white py-1 pr-3 pl-2 shadow-soft"
              >
                <span className={`size-2 rounded-full ${IOC_DOT[i.type]}`} />
                <span className="caption-4 text-ink-3">{IOC_LABEL[i.type]}</span>
                <span className={`body-5 ${i.type === 'alias' || i.type === 'agency_claimed' ? 'capitalize' : 'font-mono'}`}>
                  {i.type === 'agency_claimed' && i.value.length <= 5 ? i.value.toUpperCase() : i.value}
                </span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  )
}
