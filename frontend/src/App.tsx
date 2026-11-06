import { Chat } from './components/Chat'
import { Header } from './components/Header'
import { Panel } from './components/Panel'
import { config } from './config'
import { StoreProvider } from './store'

export default function App() {
  return (
    <StoreProvider>
      <div className="flex h-screen flex-col overflow-hidden">
        <Header />
        <main className="grid min-h-0 flex-1 grid-cols-[55fr_45fr] gap-4 px-4 pb-4">
          <Chat />
          <div className="grid min-h-0 grid-rows-[minmax(0,1.15fr)_minmax(0,0.85fr)_minmax(0,1.2fr)] gap-4">
            <Panel title={`What ${config.personaName} remembers`}>{null}</Panel>
            <Panel title="Contradictions caught">{null}</Panel>
            <Panel title="Scam network">{null}</Panel>
          </div>
        </main>
      </div>
    </StoreProvider>
  )
}
