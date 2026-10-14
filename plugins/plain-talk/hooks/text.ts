import type { SessionMessage } from 'claude-code'

const FENCE = /(```[\s\S]*?```|~~~[\s\S]*?~~~)/

// Inline code drawn as plain words; fenced blocks are left as they are.
export function unticked(text: string): string {
  return text
    .split(FENCE)
    .map((part, i) => (i % 2 === 1 ? part : part.replace(/`([^`\n]+)`/g, '$1')))
    .join('')
}

// Text the model wrote this turn before it called another tool: narration.
export function narration(rows: readonly SessionMessage[]): number {
  let start = -1
  rows.forEach((r, i) => {
    if (r.role === 'user' && r.text.trim() !== '' && !(r.toolResults?.length)) start = i
  })
  const turn = rows.slice(start + 1)
  let lastTool = -1
  turn.forEach((r, i) => {
    if (r.toolUses.length > 0) lastTool = i
  })
  return turn.filter((r, i) => r.role === 'assistant' && r.text.trim() !== '' && i < lastTool).length
}
