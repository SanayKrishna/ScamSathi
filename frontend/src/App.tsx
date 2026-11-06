// F0 temporary debug page: calls every api function and logs the result.
import { useEffect, useState } from 'react'
import { api } from './api'
import { config } from './config'

type Row = { name: string; ok: boolean; detail: string }

export default function App() {
  const [rows, setRows] = useState<Row[]>([])

  useEffect(() => {
    const run = async () => {
      const out: Row[] = []
      const log = async (name: string, fn: () => Promise<unknown>) => {
        try {
          const res = await fn()
          console.log(name, res)
          out.push({ name, ok: true, detail: JSON.stringify(res).slice(0, 140) })
        } catch (e) {
          console.error(name, e)
          out.push({ name, ok: false, detail: String(e) })
        }
        setRows([...out])
      }
      const conv = await api.createConversation()
      out.push({ name: 'createConversation', ok: true, detail: JSON.stringify(conv) })
      await log('sendMessage (memory on)', () => api.sendMessage(conv.conversation_id, 'Inspector Sharma, CBI', true))
      await log('sendMessage (memory off)', () => api.sendMessage(conv.conversation_id, 'Inspector Sharma, CBI', false))
      await log('getConversation', () => api.getConversation(conv.conversation_id))
      await log('endConversation', () => api.endConversation(conv.conversation_id))
      await log('getNetwork', () => api.getNetwork(conv.conversation_id))
      await log('getStats', () => api.getStats())
      const seed = await api.startSeed()
      await log('getSeedStatus', () => api.getSeedStatus(seed.job_id))
      await log('getHealth', () => api.getHealth())
      await log('getConversation (unknown, expect 404)', () => api.getConversation('conv_9999'))
    }
    void run()
  }, [])

  return (
    <main className="p-8 font-mono caption-2">
      <h1 className="heading-5 font-sans mb-4">API debug ({config.useMocks ? 'mocks' : config.apiUrl})</h1>
      {rows.map((r) => (
        <p key={r.name} className={r.ok ? 'text-ink-2' : 'text-alert'}>
          {r.ok ? 'ok ' : 'err'} {r.name}: {r.detail}
        </p>
      ))}
    </main>
  )
}
