import { useEffect, useState } from 'react'
import { Chat } from './components/Chat'
import { ContradictionPanel } from './components/ContradictionPanel'
import { MemoryPanel } from './components/MemoryPanel'
import { NetworkGraph } from './components/NetworkGraph'
import { PresenterDrawer } from './components/PresenterDrawer'
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
      <main className="grid min-h-0 flex-1 grid-cols-[55fr_45fr] gap-4 px-4 pb-4">
        <Chat />
        <div className="grid min-h-0 grid-rows-[minmax(0,1.4fr)_minmax(0,0.8fr)_minmax(0,1.1fr)] gap-4 [@media(max-height:860px)]:grid-rows-[minmax(0,1fr)_minmax(0,0.95fr)_minmax(0,1.25fr)]">
          <MemoryPanel />
          <ContradictionPanel />
          <NetworkGraph />
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
