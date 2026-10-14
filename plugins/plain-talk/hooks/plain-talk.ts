import type { Register } from 'claude-code'

import { narration, unticked } from './text'

export const register: Register = on => {
  // The drawing only: what the model wrote, and read, is unchanged.
  on('ui.render', { component: 'AssistantMessage', props: { text: /`/ } }, ($, e, next) =>
    e.component === 'AssistantMessage' ? next({ ...e, props: { ...e.props, text: unticked(e.props.text) } }) : next(e),
  )

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId !== undefined) return result
    const n = narration(await $.session.messages())
    $.ui.status(n > 0 ? `plain-talk: ${n} message(s) of narration between tool calls` : undefined)
    return result
  })
}
