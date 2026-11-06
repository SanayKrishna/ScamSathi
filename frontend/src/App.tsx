import { Chat } from './components/Chat'
import { Header } from './components/Header'
import { ContradictionPanel } from './components/ContradictionPanel'
import { MemoryPanel } from './components/MemoryPanel'
import { Panel } from './components/Panel'
import { StoreProvider } from './store'

export default function App() {
  return (
    <StoreProvider>
      <div className="flex h-screen flex-col overflow-hidden">
        <Header />
        <main className="grid min-h-0 flex-1 grid-cols-[55fr_45fr] gap-4 px-4 pb-4">
          <Chat />
          <div className="grid min-h-0 grid-rows-[minmax(0,1.4fr)_minmax(0,0.8fr)_minmax(0,1.1fr)] gap-4">
            <MemoryPanel />
            <ContradictionPanel />
            <Panel title="Scam network">{null}</Panel>
          </div>
        </main>
      </div>
    </StoreProvider>
  )
}
