import { AnimatePresence, motion } from 'motion/react'
import { ArrowCounterClockwise, CaretDown, Database } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { api, ApiClientError } from '../api'
import { EASE } from '../lib/motion'
import { useStore } from '../store'
import type { SeedStatusResponse } from '../types'

export function DemoMenu() {
  const { actions } = useStore()
  const [open, setOpen] = useState(false)
  const [seed, setSeed] = useState<SeedStatusResponse | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [resetting, setResetting] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const pollRef = useRef<number | null>(null)

  // Close on outside click or Escape.
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  useEffect(
    () => () => {
      if (pollRef.current) window.clearTimeout(pollRef.current)
    },
    [],
  )

  const seeding = seed?.status === 'running'

  const poll = (jobId: string) => {
    pollRef.current = window.setTimeout(async () => {
      try {
        const s = await api.getSeedStatus(jobId)
        setSeed(s)
        if (s.status === 'running') poll(jobId)
        else {
          setNote(s.status === 'done' ? `Seeded ${s.conversations_done} conversations.` : `Seed failed. ${s.error ?? ''}`)
          void actions.refresh()
        }
      } catch (e) {
        setSeed(null)
        setNote(e instanceof ApiClientError ? e.message : 'Lost track of the seed job.')
      }
    }, 1500)
  }

  const startSeed = async () => {
    setNote(null)
    try {
      const res = await api.startSeed()
      setSeed({ ...res, conversations_done: 0, error: null })
      poll(res.job_id)
    } catch (e) {
      setNote(e instanceof ApiClientError ? e.message : 'Could not start the seed.')
    }
  }

  const reset = async () => {
    if (confirmText !== 'RESET') return
    setResetting(true)
    setNote(null)
    try {
      const res = await api.resetDemo()
      setNote(`Memory bank ${res.bank_id} was wiped and recreated.`)
      setConfirmText('')
      void actions.refresh()
    } catch (e) {
      setNote(e instanceof ApiClientError ? e.message : 'Reset failed.')
    } finally {
      setResetting(false)
    }
  }

  const pct = seed ? Math.round((seed.conversations_done / Math.max(1, seed.conversations_planned)) * 100) : 0

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Demo controls"
        title="Demo controls"
        className={`relative flex items-center gap-1 rounded-md px-2 py-1 body-5 transition-colors ${
          open ? 'bg-fill-2 text-ink' : 'text-ink-2 hover:text-ink'
        }`}
      >
        Demo
        <CaretDown size={12} weight="bold" className={`transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
        {seeding && <span className="absolute -top-0.5 -right-0.5 size-2 animate-pulse rounded-full bg-mem" />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="dialog"
            aria-label="Demo controls"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.3, ease: EASE }}
            className="absolute top-full right-0 z-50 mt-3 w-96 origin-top-right rounded-3xl bg-white/90 p-3 shadow-lift backdrop-blur-2xl"
          >
            <p className="caption-3 px-3 pt-2 pb-3 uppercase tracking-wider text-ink-3">Demo controls</p>

            <div className="rounded-xl bg-fill-2 p-4">
              <div className="flex items-start gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white text-blue shadow-soft">
                  <Database size={16} weight="bold" />
                </span>
                <div className="flex-1">
                  <p className="title-3">Seed past conversations</p>
                  <p className="body-6 text-ink-2">Runs about 20 simulated scam chats so memory has history.</p>
                </div>
              </div>
              {seed && (
                <div className="mt-3">
                  <div className="h-2 overflow-hidden rounded-full bg-white">
                    <motion.div
                      className="h-full origin-left rounded-full bg-blue"
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: pct / 100 }}
                      transition={{ duration: 0.5, ease: EASE }}
                    />
                  </div>
                  <p className="caption-5 mt-2 text-ink-2 tabular-nums">
                    {seed.conversations_done} of {seed.conversations_planned} · {seed.status}
                  </p>
                </div>
              )}
              <button
                type="button"
                onClick={startSeed}
                disabled={seeding}
                className="mt-3 w-full rounded-full bg-blue px-3 py-2 button-sm text-white transition-[opacity,transform] hover:opacity-90 active:scale-[0.98] disabled:opacity-40"
              >
                {seeding ? 'Seeding...' : 'Start seed'}
              </button>
            </div>

            <div className="mt-2 rounded-xl bg-fill-2 p-4">
              <div className="flex items-start gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white text-alert shadow-soft">
                  <ArrowCounterClockwise size={16} weight="bold" />
                </span>
                <div className="flex-1">
                  <p className="title-3">Reset everything</p>
                  <p className="body-6 text-ink-2">Wipes the database and the memory bank. Type RESET to confirm.</p>
                </div>
              </div>
              <div className="mt-3 flex gap-2">
                <input
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && void reset()}
                  placeholder="RESET"
                  aria-label="Type RESET to confirm"
                  className="min-w-0 flex-1 rounded-full bg-white px-3 py-2 body-6 font-mono text-ink shadow-soft outline-none placeholder:text-ink-3/60 focus:ring-2 focus:ring-alert/40"
                />
                <button
                  type="button"
                  onClick={reset}
                  disabled={confirmText !== 'RESET' || resetting}
                  className="rounded-full bg-alert px-3 py-2 button-sm text-white transition-[opacity,transform] hover:opacity-90 active:scale-[0.98] disabled:opacity-30"
                >
                  {resetting ? 'Resetting...' : 'Reset'}
                </button>
              </div>
            </div>

            <AnimatePresence>
              {note && (
                <motion.p
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3, ease: EASE }}
                  className="caption-2 px-3 pt-3 pb-1 text-ink-2"
                >
                  {note}
                </motion.p>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
