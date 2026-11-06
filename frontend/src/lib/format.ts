export function clockTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/** conv_0007 → 7 */
export function chatNumber(conversationId: string | null | undefined): string | null {
  if (!conversationId) return null
  const m = /(\d+)$/.exec(conversationId)
  return m ? String(Number(m[1])) : conversationId
}

export function shortDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
