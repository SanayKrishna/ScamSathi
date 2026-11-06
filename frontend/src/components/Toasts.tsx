import { AnimatePresence, motion } from 'motion/react'
import { WarningCircle, X } from '@phosphor-icons/react'
import { EASE } from '../lib/motion'
import { useStore } from '../store'

/** API errors surface here as error.message, never as raw errors (API.md "Errors"). */
export function Toasts() {
  const { state, actions } = useStore()
  return (
    <div
      aria-live="assertive"
      className="pointer-events-none fixed bottom-8 left-1/2 z-50 flex w-full max-w-lg -translate-x-1/2 flex-col items-center gap-2"
    >
      <AnimatePresence initial={false}>
        {state.toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            role="alert"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.4, ease: EASE }}
            className="pointer-events-auto flex w-full items-center gap-3 rounded-2xl border border-alert/40 bg-panel/95 py-3 pr-3 pl-4 shadow-2xl shadow-black backdrop-blur-xl"
          >
            <WarningCircle size={20} weight="fill" className="shrink-0 text-alert" />
            <p className="body-3 flex-1 text-ink">{t.message}</p>
            <button
              type="button"
              onClick={() => actions.dismissToast(t.id)}
              aria-label="Dismiss"
              className="rounded-full p-1 text-ink-3 transition-colors hover:bg-raised hover:text-ink"
            >
              <X size={16} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
