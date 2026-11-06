import { AnimatePresence, motion } from 'motion/react'
import { X } from '@phosphor-icons/react'
import { config } from '../config'
import { EASE } from '../lib/motion'
import { useStore } from '../store'

const name = config.personaName

// The 60 second demo script from architecture.md section 4.
const STEPS: { title: string; body: string; memory: 'on' | 'off' }[] = [
  {
    title: 'Memory off, generic panic',
    body: `Turn memory OFF. Type as "Inspector Sharma, CBI, case DL/4410". ${name} panics generically. The memory panel stays empty.`,
    memory: 'off',
  },
  {
    title: 'Flip memory on, same opener',
    body: 'Turn memory ON, start a new chat and send the exact same opener.',
    memory: 'on',
  },
  {
    title: 'The memory panel fills',
    body: `"UPI sharma.verify@fakebank used by Officer Verma in chat #4". A red card: case number changed, MH/2291 in chat #7.`,
    memory: 'on',
  },
  {
    title: `${name} probes the contradiction`,
    body: '"Sir, last week your colleague said MH/2291. Which one I write down?"',
    memory: 'on',
  },
  {
    title: 'A ring is exposed',
    body: 'The graph links Sharma and Verma through one mule account.',
    memory: 'on',
  },
]

const SHORTCUTS: [string, string][] = [
  ['M', 'Toggle memory'],
  ['N', 'New chat'],
  ['P', 'This script'],
  ['Esc', 'Leave the text box so shortcuts work'],
  ['Alt + key', 'Same shortcuts while typing'],
]

export function PresenterDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { state } = useStore()
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: EASE }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]"
          />
          <motion.aside
            key="drawer"
            role="dialog"
            aria-label="Presenter script"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.5, ease: EASE }}
            className="fixed top-4 right-4 bottom-4 z-50 flex w-[440px] flex-col overflow-hidden rounded-3xl border border-line bg-panel/95 shadow-2xl shadow-black backdrop-blur-xl"
          >
            <header className="flex items-center justify-between px-6 pt-6 pb-4">
              <div>
                <p className="caption-3 uppercase tracking-wider text-ink-3">Presenter script</p>
                <h2 className="heading-6 mt-1">The 60 second demo</h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-full p-2 text-ink-3 transition-colors hover:bg-raised hover:text-ink"
              >
                <X size={18} />
              </button>
            </header>

            <ol className="flex-1 space-y-2 overflow-y-auto px-4">
              {STEPS.map((s, i) => (
                <motion.li
                  key={s.title}
                  initial={{ opacity: 0, x: 24 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, ease: EASE, delay: 0.1 + i * 0.06 }}
                  className="flex gap-4 rounded-xl bg-card p-4"
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-raised title-4 tabular-nums">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="title-3">{s.title}</p>
                      <span
                        className={`rounded-full px-2 py-0.5 caption-3 ${
                          s.memory === 'on' ? 'bg-mem/15 text-mem' : 'bg-raised text-ink-3'
                        }`}
                      >
                        {s.memory === 'on' ? 'MEMORY ON' : 'MEMORY OFF'}
                      </span>
                    </div>
                    <p className="body-6 mt-1 text-ink-2">{s.body}</p>
                  </div>
                </motion.li>
              ))}
            </ol>

            <footer className="border-t border-line/60 px-6 py-4">
              <p className="caption-3 mb-2 uppercase tracking-wider text-ink-3">
                Shortcuts · memory is {state.memoryEnabled ? 'on' : 'off'}
              </p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                {SHORTCUTS.map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt>
                      <kbd className="rounded border border-line bg-card px-2 py-0.5 caption-4 font-mono">{k}</kbd>
                    </dt>
                    <dd className="body-6 text-ink-2">{v}</dd>
                  </div>
                ))}
              </dl>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
