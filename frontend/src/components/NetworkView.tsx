import { AnimatePresence, motion } from 'motion/react'
import { Graph, X } from '@phosphor-icons/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { forceCollide, forceX, forceY } from 'd3-force-3d'
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from 'react-force-graph-2d'
import { shortDate } from '../lib/format'
import { EASE } from '../lib/motion'
import { useStore } from '../store'
import type { EdgeRelation, NetworkNode, NodeType } from '../types'
import { Quiet } from './RememberColumn'

// ── Visual constants (light) ────────────────────────────────────

const NODE_COLOR: Record<NodeType, string> = {
  alias: '#1d1d1f',
  upi: '#34c759',
  phone: '#0a84ff',
  agency_claimed: '#aeaeb2',
}

const NODE_LABEL: Record<NodeType, string> = {
  alias: 'Alias',
  upi: 'UPI',
  phone: 'Phone',
  agency_claimed: 'Agency',
}

const RELATION_LABEL: Record<EdgeRelation, string> = {
  uses_upi: 'uses UPI',
  uses_phone: 'uses phone',
  claims_agency: 'claims agency',
  gave_case_number: 'gave case number',
}

const RING_TINTS = ['52, 199, 89', '10, 132, 255', '255, 159, 10', '175, 82, 222', '255, 59, 48']
const HIGHLIGHT = '#0a84ff'
const PULSE_MS = 2000
const FONT = "'Geist Variable', ui-sans-serif, system-ui, sans-serif"

type GNode = NodeObject<NetworkNode>
type GLink = LinkObject<GNode, { relation: EdgeRelation; weight: number }>

const radius = (n: NetworkNode) => 5 + Math.sqrt(Math.min(6, Math.max(1, n.count))) * 2.4
const ringIndex = (ringId: string) => Math.max(0, Number(/\d+/.exec(ringId)?.[0] ?? 1) - 1)
const ringTint = (ringId: string) => RING_TINTS[ringIndex(ringId) % RING_TINTS.length]

// ── Component ───────────────────────────────────────────────────

export function NetworkView() {
  const { state } = useStore()
  const { network } = state
  const wrapRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<ForceGraphMethods<GNode, GLink> | undefined>(undefined)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [selected, setSelected] = useState<GNode | null>(null)
  const [hoverLink, setHoverLink] = useState<GLink | null>(null)
  const [pulsing, setPulsing] = useState(false)

  const cache = useRef(new Map<string, GNode>())
  const pulses = useRef(new Map<string, number>())
  const fitted = useRef(false)
  const seenOnce = useRef(false)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ width: Math.floor(width), height: Math.floor(height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Merge new data into cached node objects so existing nodes keep their positions.
  const graphData = useMemo(() => {
    if (!network) return { nodes: [] as GNode[], links: [] as GLink[] }
    const next = new Map<string, GNode>()
    const fresh: string[] = []
    for (const n of network.nodes) {
      const prev = cache.current.get(n.id)
      if (prev) {
        Object.assign(prev, n)
        next.set(n.id, prev)
      } else {
        next.set(n.id, { ...n })
        fresh.push(n.id)
      }
    }
    const links: GLink[] = network.edges
      .filter((e) => next.has(e.source) && next.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, relation: e.relation, weight: e.weight }))

    for (const id of fresh) {
      const node = next.get(id)!
      const edge = network.edges.find((e) => e.source === id || e.target === id)
      const otherId = edge ? (edge.source === id ? edge.target : edge.source) : null
      const other = otherId ? cache.current.get(otherId) : undefined
      if (other?.x !== undefined && other.y !== undefined) {
        node.x = other.x + (Math.random() - 0.5) * 20
        node.y = other.y + (Math.random() - 0.5) * 20
      }
      if (seenOnce.current) pulses.current.set(id, performance.now())
    }
    seenOnce.current = true
    if (fresh.length > 0)
      for (const n of next.values()) {
        n.fx = undefined
        n.fy = undefined
      }

    cache.current = next
    return { nodes: [...next.values()], links }
  }, [network])

  useEffect(() => {
    if (pulses.current.size === 0) return
    setPulsing(true)
    const t = window.setTimeout(() => {
      pulses.current.clear()
      setPulsing(false)
    }, PULSE_MS + 100)
    return () => window.clearTimeout(t)
  }, [graphData])

  useEffect(() => {
    if (selected && !cache.current.has(String(selected.id))) setSelected(null)
  }, [graphData, selected])

  const graphReady = size.width > 0 && graphData.nodes.length > 0

  // Gentle charge, short links and a weak pull to the centre so rings sit close together.
  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    const charge = fg.d3Force('charge') as unknown as
      | { strength: (v: number) => { distanceMax: (v: number) => void } }
      | undefined
    charge?.strength(-260).distanceMax(700)
    const link = fg.d3Force('link') as unknown as { distance?: (d: number) => void } | undefined
    link?.distance?.(56)
    fg.d3Force('x', forceX<GNode>(0).strength(0.03) as never)
    fg.d3Force('y', forceY<GNode>(0).strength(0.06) as never)
    fg.d3Force('collide', forceCollide<GNode>((n) => radius(n) + (n.type === 'alias' ? 34 : 22)) as never)
    fg.d3ReheatSimulation()
  }, [graphReady])

  // Freeze once settled so nothing drifts during the demo.
  const onEngineStop = useCallback(() => {
    for (const n of cache.current.values()) {
      n.fx = n.x
      n.fy = n.y
    }
    if (cache.current.size > 0) {
      fgRef.current?.zoomToFit(fitted.current ? 600 : 400, 96)
      fitted.current = true
    }
  }, [])

  const drawHulls = useCallback(
    (ctx: CanvasRenderingContext2D, scale: number) => {
      const rings = new Map<string, GNode[]>()
      for (const n of graphData.nodes) {
        if (!n.ring_id || n.x === undefined || n.y === undefined) continue
        const list = rings.get(n.ring_id) ?? []
        list.push(n)
        rings.set(n.ring_id, list)
      }
      for (const [ringId, nodes] of rings) {
        const tint = ringTint(ringId)
        const hull = convexHull(nodes.map((n) => [n.x!, n.y!] as [number, number]))
        ctx.save()
        ctx.beginPath()
        hull.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)))
        ctx.closePath()
        ctx.lineJoin = 'round'
        ctx.lineCap = 'round'
        ctx.lineWidth = 48
        // Solid pastel (tint blended onto white) so stroke and fill don't stack.
        const solid = pastel(tint, 0.1)
        ctx.strokeStyle = solid
        ctx.fillStyle = solid
        ctx.stroke()
        ctx.fill()
        const top = hull.reduce((a, b) => (b[1] < a[1] ? b : a), hull[0])
        const cx = hull.reduce((s, p) => s + p[0], 0) / hull.length
        ctx.font = `600 ${12 / scale}px ${FONT}`
        ctx.fillStyle = `rgba(${tint}, 1)`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText(ringId.replace('_', ' ').toUpperCase(), cx, top[1] - 32)
        ctx.restore()
      }
    },
    [graphData],
  )

  const drawNode = useCallback((node: GNode, ctx: CanvasRenderingContext2D, scale: number) => {
    const x = node.x ?? 0
    const y = node.y ?? 0
    const r = radius(node)
    const color = NODE_COLOR[node.type] ?? '#999'

    const started = pulses.current.get(String(node.id))
    if (started !== undefined) {
      const t = (performance.now() - started) / PULSE_MS
      if (t < 1) {
        for (const offset of [0, 0.5]) {
          const p = (t * 2 + offset) % 1
          ctx.beginPath()
          ctx.arc(x, y, r + p * 22, 0, Math.PI * 2)
          ctx.strokeStyle = hexA(color, (1 - p) * 0.6)
          ctx.lineWidth = 2 / scale
          ctx.stroke()
        }
      }
    }

    if (node.in_current) {
      ctx.beginPath()
      ctx.arc(x, y, r + 5, 0, Math.PI * 2)
      ctx.strokeStyle = HIGHLIGHT
      ctx.lineWidth = 2.5 / scale
      ctx.stroke()
    }

    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
    ctx.lineWidth = 2 / scale
    ctx.strokeStyle = '#ffffff'
    ctx.stroke()

    if (node.type !== 'phone' || node.in_current) {
      const px = node.type === 'alias' ? 14 : 12
      ctx.font = `${node.type === 'alias' ? 600 : 500} ${px / scale}px ${FONT}`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.lineWidth = 4 / scale
      ctx.strokeStyle = 'rgba(255,255,255,0.9)'
      ctx.strokeText(node.label, x, y + r + 5 / scale)
      ctx.fillStyle = node.type === 'alias' ? '#1d1d1f' : '#6e6e73'
      ctx.fillText(node.label, x, y + r + 5 / scale)
    }
  }, [])

  const drawLinkLabel = useCallback(
    (link: GLink, ctx: CanvasRenderingContext2D, scale: number) => {
      if (link !== hoverLink) return
      const s = link.source as GNode
      const t = link.target as GNode
      if (s.x === undefined || t.x === undefined || s.y === undefined || t.y === undefined) return
      const text = RELATION_LABEL[link.relation] ?? link.relation
      const mx = (s.x + t.x) / 2
      const my = (s.y + t.y) / 2
      ctx.font = `500 ${12 / scale}px ${FONT}`
      const w = ctx.measureText(text).width + 16 / scale
      const h = 22 / scale
      ctx.fillStyle = '#1d1d1f'
      ctx.beginPath()
      ctx.roundRect(mx - w / 2, my - h / 2, w, h, h / 2)
      ctx.fill()
      ctx.fillStyle = '#ffffff'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(text, mx, my)
    },
    [hoverLink],
  )

  const rings = useMemo(() => summariseRings(network?.nodes ?? []), [network])
  const nodeCount = network?.nodes.length ?? 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE }}
      className="flex min-h-0 flex-1 flex-col px-10 pt-6"
    >
      <div className="mb-4 flex items-end justify-between gap-6">
        <div>
          <h1 className="heading-4 tracking-tight">Scam network</h1>
          <p className="body-6 mt-1 text-ink-2">
            Aliases, mule UPI accounts and phones, linked across every chat she has had.
          </p>
        </div>
        {network && (
          <p className="caption-1 text-ink-2">
            {nodeCount} identifiers · {rings.length} {rings.length === 1 ? 'ring' : 'rings'}
          </p>
        )}
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden rounded-3xl bg-white shadow-soft">
        <div ref={wrapRef} className="absolute inset-0">
          {!network ? (
            <GraphSkeleton />
          ) : nodeCount === 0 ? (
            <div className="grid h-full place-items-center">
              <Quiet
                icon={<Graph size={24} />}
                title="No scammers yet"
                text="Aliases, UPI handles and phones appear here as she collects them."
              />
            </div>
          ) : (
            size.width > 0 && (
              <ForceGraph2D<GNode, GLink>
                ref={fgRef}
                graphData={graphData}
                width={size.width}
                height={size.height}
                backgroundColor="rgba(0,0,0,0)"
                nodeId="id"
                nodeCanvasObject={drawNode}
                nodePointerAreaPaint={(node, color, ctx) => {
                  ctx.fillStyle = color
                  ctx.beginPath()
                  ctx.arc(node.x ?? 0, node.y ?? 0, radius(node) + 5, 0, Math.PI * 2)
                  ctx.fill()
                }}
                linkColor={(l) => (l === hoverLink ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0.14)')}
                linkWidth={(l) => (l === hoverLink ? 2 : Math.min(3, 0.8 + l.weight * 0.4))}
                linkCanvasObjectMode={() => 'after'}
                linkCanvasObject={drawLinkLabel}
                linkHoverPrecision={6}
                onLinkHover={(l) => setHoverLink(l ?? null)}
                onNodeClick={(n) => setSelected(n)}
                onBackgroundClick={() => setSelected(null)}
                onRenderFramePre={drawHulls}
                onEngineStop={onEngineStop}
                cooldownTicks={220}
                warmupTicks={0}
                d3VelocityDecay={0.35}
                enableNodeDrag={false}
                autoPauseRedraw={!pulsing && !hoverLink}
                minZoom={0.5}
                maxZoom={2.2}
              />
            )
          )}
        </div>

        {network && nodeCount > 0 && <Legend />}
        {rings.length > 0 && <RingList rings={rings} />}

        <AnimatePresence>
          {selected && <NodeDetail key={String(selected.id)} node={selected} onClose={() => setSelected(null)} />}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

// ── Overlays ────────────────────────────────────────────────────

interface RingSummary {
  id: string
  aliases: string[]
  links: string[]
}

function summariseRings(nodes: NetworkNode[]): RingSummary[] {
  const map = new Map<string, RingSummary>()
  for (const n of nodes) {
    if (!n.ring_id) continue
    const r = map.get(n.ring_id) ?? { id: n.ring_id, aliases: [], links: [] }
    if (n.type === 'alias') r.aliases.push(n.label)
    else if (n.type === 'upi' || n.type === 'phone') r.links.push(n.label)
    map.set(n.ring_id, r)
  }
  return [...map.values()].sort((a, b) => ringIndex(a.id) - ringIndex(b.id))
}

function RingList({ rings }: { rings: RingSummary[] }) {
  return (
    <div className="pointer-events-none absolute top-4 left-4 flex w-72 flex-col gap-2">
      {rings.map((r, i) => (
        <motion.div
          key={r.id}
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, ease: EASE, delay: 0.2 + i * 0.08 }}
          className="rounded-2xl bg-white/85 p-4 shadow-soft backdrop-blur-xl"
        >
          <div className="flex items-center gap-2">
            <span className="size-2 rounded-full" style={{ background: `rgb(${ringTint(r.id)})` }} />
            <p className="title-4">{r.id.replace('_', ' ').replace(/^\w/, (c) => c.toUpperCase())}</p>
            <span className="caption-5 ml-auto text-ink-3">
              {r.aliases.length} {r.aliases.length === 1 ? 'alias' : 'aliases'}
            </span>
          </div>
          <p className="body-5 mt-2">{r.aliases.join(' and ')}</p>
          {r.links.length > 0 && (
            <p className="caption-2 mt-1 text-ink-2">
              share <span className="font-mono text-ink">{r.links.join(', ')}</span>
            </p>
          )}
        </motion.div>
      ))}
    </div>
  )
}

function NodeDetail({ node, onClose }: { node: GNode; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 4, scale: 0.97 }}
      transition={{ duration: 0.3, ease: EASE }}
      className="absolute top-4 right-4 w-72 rounded-2xl bg-white/90 p-4 shadow-lift backdrop-blur-xl"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex items-center gap-2 caption-3 uppercase tracking-wider text-ink-3">
          <span className="size-2 rounded-full" style={{ background: NODE_COLOR[node.type] }} />
          {NODE_LABEL[node.type]}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-m-1 rounded-full p-1 text-ink-3 transition-colors hover:bg-fill-2 hover:text-ink"
        >
          <X size={14} />
        </button>
      </div>
      <p className={`title-1 mt-2 break-all ${node.type === 'upi' || node.type === 'phone' ? 'font-mono' : ''}`}>
        {node.label}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3">
        <div>
          <dt className="caption-5 text-ink-3">Seen</dt>
          <dd className="body-5 tabular-nums">{node.count} times</dd>
        </div>
        <div>
          <dt className="caption-5 text-ink-3">First seen</dt>
          <dd className="body-5">{shortDate(node.first_seen)}</dd>
        </div>
        {node.ring_id && (
          <div className="col-span-2">
            <dt className="caption-5 text-ink-3">Ring</dt>
            <dd className="body-5">{node.ring_id.replace('_', ' ')}</dd>
          </div>
        )}
        {node.in_current && (
          <div className="col-span-2">
            <span className="rounded-full bg-blue/10 px-2 py-0.5 caption-3 text-blue">In this chat</span>
          </div>
        )}
      </dl>
    </motion.div>
  )
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-4 left-4 flex flex-wrap gap-4 rounded-full bg-white/85 px-4 py-2 shadow-soft backdrop-blur-xl">
      {(Object.keys(NODE_COLOR) as NodeType[]).map((t) => (
        <span key={t} className="inline-flex items-center gap-2 caption-4 text-ink-2">
          <span className="size-2 rounded-full" style={{ background: NODE_COLOR[t] }} />
          {NODE_LABEL[t]}
        </span>
      ))}
      <span className="inline-flex items-center gap-2 caption-4 text-ink-2">
        <span className="size-3 rounded-full border-2 border-blue" />
        This chat
      </span>
      <span className="caption-4 text-ink-3">Hover a line, click a dot</span>
    </div>
  )
}

function GraphSkeleton() {
  const dots = [
    [36, 40], [45, 30], [52, 55], [40, 62], [62, 42], [70, 60], [58, 26],
  ]
  return (
    <div className="absolute inset-0" aria-label="Loading network">
      {dots.map(([x, y], i) => (
        <span
          key={i}
          className="absolute size-4 animate-pulse rounded-full bg-fill-2"
          style={{ left: `${x}%`, top: `${y}%`, animationDelay: `${i * 120}ms` }}
        />
      ))}
    </div>
  )
}

// ── Helpers ─────────────────────────────────────────────────────

function pastel(rgb: string, alpha: number) {
  const [r, g, b] = rgb.split(',').map((v) => Number(v.trim()))
  const mix = (c: number) => Math.round(255 - (255 - c) * alpha)
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`
}

function hexA(hex: string, alpha: number) {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha.toFixed(3)})`
}

/** Monotone chain convex hull. Returns the input for one or two points. */
function convexHull(points: [number, number][]): [number, number][] {
  if (points.length < 3) return points
  const pts = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const cross = (o: number[], a: number[], b: number[]) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const lower: [number, number][] = []
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop()
    lower.push(p)
  }
  const upper: [number, number][] = []
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop()
    upper.push(p)
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1))
}
