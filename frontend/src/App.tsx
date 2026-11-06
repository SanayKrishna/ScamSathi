import { useEffect, useState } from 'react'
import { CaughtColumn } from './components/CaughtColumn'
import { NetworkView } from './components/NetworkView'
import { Phone } from './components/Phone'
import { RememberColumn } from './components/RememberColumn'
import { PresenterDrawer } from './components/PresenterDrawer'
import { StatStrip } from './components/StatStrip'
import { Toasts } from './components/Toasts'
import { TopBar, type View } from './components/TopBar'
import { StoreProvider, useStore } from './store'

export default function App() {
  return (
    <StoreProvider>
      <Shell />
    </StoreProvider>
  )
}

function Shell() {
  const [presenter, setPresenter] = useState(false)
  const [view, setView] = useState<View>('call')
  useShortcuts({
    togglePresenter: () => setPresenter((p) => !p),
    closePresenter: () => setPresenter(false),
    toggleView: () => setView((v) => (v === 'call' ? 'network' : 'call')),
  })

  return (
    <div className="flex h-screen min-h-[720px] flex-col overflow-hidden">
      <TopBar view={view} onView={setView} onOpenPresenter={() => setPresenter(true)} />
      <main className="relative flex min-h-0 flex-1 flex-col">
        {view === 'call' ? (
          <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] gap-12 px-10 pt-6">
            <RememberColumn />
            <Phone />
            <CaughtColumn />
          </div>
        ) : (
          <NetworkView />
        )}
        <div className="flex shrink-0 justify-center py-4">
          <StatStrip />
        </div>
      </main>
      <Toasts />
      <PresenterDrawer open={presenter} onClose={() => setPresenter(false)} />
    </div>
  )
}

/**
 * M toggles memory, N starts a new chat, P opens the presenter script, G switches Call and Network.
 * Plain keys work when focus is outside a text field; Alt + key works everywhere.
 * Escape leaves the text box (or closes the drawer).
 */
function useShortcuts({
  togglePresenter,
  closePresenter,
  toggleView,
}: {
  togglePresenter: () => void
  closePresenter: () => void
  toggleView: () => void
}) {
  const { actions } = useStore()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.repeat || e.ctrlKey || e.metaKey) return
      const target = e.target as HTMLElement | null
      const typing = !!target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.isContentEditable)

      if (e.key === 'Escape') {
        closePresenter()
        if (typing && target?.id === 'composer') target.blur()
        return
      }
      if (typing && !e.altKey) return

      switch (e.code) {
        case 'KeyM':
          e.preventDefault()
          actions.toggleMemory()
          break
        case 'KeyN':
          e.preventDefault()
          void actions.newChat()
          break
        case 'KeyP':
          e.preventDefault()
          togglePresenter()
          break
        case 'KeyG':
          e.preventDefault()
          toggleView()
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [actions, togglePresenter, closePresenter, toggleView])
}
