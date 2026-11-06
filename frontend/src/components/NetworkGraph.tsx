import { AnimatePresence, motion } from 'motion/react'
import { Graph, X } from '@phosphor-icons/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { forceCollide, forceX, forceY } from 'd3-force-3d'
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from 'react-force-graph-2d'
import { shortDate } from '../lib/format'
import { EASE } from '../lib/motion'
import { useStore } from '../store'
import type { EdgeRelation, NetworkNode, NodeType } from '../types'
import { EmptyState } from './MemoryPanel'
import { Panel } from './Panel'

// ── Visual constants ────────────────────────────────────────────

const NODE_COLOR: Record<NodeType, string> = {
  alias: '#e5e5e5',
  upi: '#4ade80',
  phone: '#93c5fd',
  agency_claimed: '#737373',
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

const RING_TINTS = ['74, 222, 128', '147, 197, 253', '251, 191, 36', '196, 181, 253', '248, 113, 113']

const PULSE_MS = 2000
const FONT = "'Geist Variable', ui-sans-serif, system-ui, sans-serif"

type GNode = NodeObject<NetworkNode & { firstSeenAt?: number }>
type GLink = LinkObject<GNode, { relation: EdgeRelation; weight: number }>

const radius = (n: NetworkNode) => 4 + Math.sqrt(Math.max(1, n.count)) * 2.2

// ── Component ───────────────────────────────────────────────────

export function NetworkGraph() {
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

  // Track the panel size so the canvas always fills it.
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

    // Place new nodes next to an existing neighbour so they grow out of the graph.
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
    // Unpin everything that touches a new node so the layout can make room.
    if (fresh.length > 0) for (const n of next.values()) { n.fx = undefined; n.fy = undefined }

    cache.current = next
    return { nodes: [...next.values()], links }
  }, [network])

  // Keep redrawing while new nodes pulse.
  useEffect(() => {
    if (pulses.current.size === 0) return
    setPulsing(true)
    const t = window.setTimeout(() => {
      pulses.current.clear()
      setPulsing(false)
    }, PULSE_MS + 100)
    return () => window.clearTimeout(t)
  }, [graphData])

  // Keep the selected node in sync with fresh data.
  useEffect(() => {
    if (selected && !cache.current.has(String(selected.id))) setSelected(null)
  }, [graphData, selected])

  const graphReady = size.width > 0 && graphData.nodes.length > 0

  // Tune forces once: gentle charge, short links, and a weak pull to the centre
  // so separate rings sit close together instead of drifting off screen.
  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    const charge = fg.d3Force('charge') as unknown as { strength: (v: number) => { distanceMax: (v: number) => void } } | undefined
    charge?.strength(-180).distanceMax(220)
    const link = fg.d3Force('link') as unknown as { distance?: (d: number) => void } | undefined
    link?.distance?.(48)
    fg.d3Force('x', forceX<GNode>(0).strength(0.06) as never)
    fg.d3Force('y', forceY<GNode>(0).strength(0.1) as never)
    fg.d3Force('collide', forceCollide<GNode>((n) => radius(n) + (n.type === "alias" ? 30 : 20)) as never)
    fg.d3ReheatSimulation()
  }, [graphReady])

  // Freeze once settled so nothing drifts during the demo.
  const onEngineStop = useCallback(() => {
    for (const n of cache.current.values()) {
      n.fx = n.x
      n.fy = n.y
    }
    if (cache.current.size > 0) {
      fgRef.current?.zoomToFit(fitted.current ? 600 : 0, 56)
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
        const idx = Math.max(0, Number(/\d+/.exec(ringId)?.[0] ?? 1) - 1)
        const tint = RING_TINTS[idx % RING_TINTS.length]
        const hull = convexHull(nodes.map((n) => [n.x!, n.y!] as [number, number]))
        ctx.save()
        ctx.beginPath()
        hull.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)))
        ctx.closePath()
        ctx.lineJoin = 'round'
        ctx.lineCap = 'round'
        ctx.lineWidth = 44
        ctx.strokeStyle = `rgba(${tint}, 0.07)`
        ctx.fillStyle = `rgba(${tint}, 0.07)`
        ctx.stroke()
        ctx.fill()
        // Ring label above the hull.
        const top = hull.reduce((a, b) => (b[1] < a[1] ? b : a), hull[0])
        const cx = hull.reduce((s, p) => s + p[0], 0) / hull.length
        ctx.font = `600 ${11 / scale}px ${FONT}`
        ctx.fillStyle = `rgba(${tint}, 0.75)`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText(ringId.replace('_', ' ').toUpperCase(), cx, top[1] - 26)
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
          ctx.arc(x, y, r + p * 18, 0, Math.PI * 2)
          ctx.strokeStyle = hexA(color, (1 - p) * 0.7)
          ctx.lineWidth = 1.5 / scale
          ctx.stroke()
        }
      }
    }

    if (node.in_current) {
      ctx.beginPath()
      ctx.arc(x, y, r + 4, 0, Math.PI * 2)
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 1.6 / scale
      ctx.stroke()
    }

    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()

    if (node.type === 'alias' || node.type === 'upi' || node.in_current) {
      const px = node.type === 'alias' ? 14 : 12
      ctx.font = `${node.type === 'alias' ? 600 : 500} ${px / scale}px ${FONT}`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillStyle = node.type === 'alias' ? '#ffffff' : 'rgba(255,255,255,0.7)'
      ctx.fillText(node.label, x, y + r + 4 / scale)
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
      const w = ctx.measureText(text).width + 12 / scale
      const h = 20 / scale
      ctx.fillStyle = '#272727'
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

  const nodeCount = network?.nodes.length ?? 0
  const ringCount = new Set(network?.nodes.map((n) => n.ring_id).filter(Boolean)).size

  return (
    <Panel
      title="Scam network"
      meta={network ? `${nodeCount} identifiers · ${ringCount} rings` : null}
      bodyClassName="relative overflow-hidden rounded-xl bg-bg/40"
    >
      <div ref={wrapRef} className="absolute inset-0">
        {!network ? (
          <GraphSkeleton />
        ) : nodeCount === 0 ? (
          <EmptyState
            icon={<Graph size={28} />}
            title="No scammers yet"
            text="Aliases, UPI handles and phones appear here as she collects them."
          />
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
                ctx.arc(node.x ?? 0, node.y ?? 0, radius(node) + 4, 0, Math.PI * 2)
                ctx.fill()
              }}
              linkColor={(l) => (l === hoverLink ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.16)')}
              linkWidth={(l) => (l === hoverLink ? 2 : Math.min(3, 0.6 + l.weight * 0.4))}
              linkCanvasObjectMode={() => 'after'}
              linkCanvasObject={drawLinkLabel}
              linkHoverPrecision={6}
              onLinkHover={(l) => setHoverLink(l ?? null)}
              onNodeClick={(n) => setSelected(n)}
              onBackgroundClick={() => setSelected(null)}
              onRenderFramePre={drawHulls}
              onEngineStop={onEngineStop}
              cooldownTicks={140}
              warmupTicks={40}
              d3VelocityDecay={0.35}
              enableNodeDrag={false}
              autoPauseRedraw={!pulsing && !hoverLink}
              minZoom={0.5}
              maxZoom={6}
            />
          )
        )}
      </div>

      {network && nodeCount > 0 && <Legend />}

      <AnimatePresence>
        {selected && (
          <motion.div
            key={String(selected.id)}
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.3, ease: EASE }}
            className="absolute top-3 right-3 w-64 rounded-xl border border-line bg-panel/95 p-4 shadow-2xl shadow-black backdrop-blur-xl"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="inline-flex items-center gap-2 caption-3 uppercase tracking-wider text-ink-3">
                <span className="size-2 rounded-full" style={{ background: NODE_COLOR[selected.type] }} />
                {NODE_LABEL[selected.type]}
              </span>
              <button
                type="button"
                onClick={() => setSelected(null)}
                aria-label="Close"
                className="-m-1 rounded-full p-1 text-ink-3 transition-colors hover:bg-raised hover:text-ink"
              >
                <X size={14} />
              </button>
            </div>
            <p className={`title-2 mt-2 break-all ${selected.type === "upi" || selected.type === "phone" ? "font-mono" : ""}`}>{selected.label}</p>
            <dl className="mt-3 grid grid-cols-2 gap-2">
              <div>
                <dt className="caption-5 text-ink-3">Seen</dt>
                <dd className="body-5 tabular-nums">{selected.count} times</dd>
              </div>
              <div>
                <dt className="caption-5 text-ink-3">First seen</dt>
                <dd className="body-5">{shortDate(selected.first_seen)}</dd>
              </div>
              {selected.ring_id && (
                <div className="col-span-2">
                  <dt className="caption-5 text-ink-3">Ring</dt>
                  <dd className="body-5">{selected.ring_id.replace('_', ' ')}</dd>
                </div>
              )}
            </dl>
          </motion.div>
        )}
      </AnimatePresence>
    </Panel>
  )
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-3 rounded-full bg-panel/80 px-3 py-1 backdrop-blur">
      {(Object.keys(NODE_COLOR) as NodeType[]).map((t) => (
        <span key={t} className="inline-flex items-center gap-1 caption-4 text-ink-3">
          <span className="size-2 rounded-full" style={{ background: NODE_COLOR[t] }} />
          {NODE_LABEL[t]}
        </span>
      ))}
      <span className="inline-flex items-center gap-1 caption-4 text-ink-3">
        <span className="size-2 rounded-full border border-ink" />
        This chat
      </span>
    </div>
  )
}

function GraphSkeleton() {
  const dots = [
    [30, 40], [45, 30], [52, 55], [38, 62], [65, 42], [72, 60], [58, 25],
  ]
  return (
    <div className="absolute inset-0" aria-label="Loading network">
      {dots.map(([x, y], i) => (
        <span
          key={i}
          className="absolute size-3 animate-pulse rounded-full bg-raised"
          style={{ left: `${x}%`, top: `${y}%`, animationDelay: `${i * 120}ms` }}
        />
      ))}
    </div>
  )
}

// ── Helpers ─────────────────────────────────────────────────────

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
