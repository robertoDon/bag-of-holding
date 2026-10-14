import { describe, expect, test } from 'claude-code/testing'

import { narration, unticked } from '../hooks/text'

const row = (role: 'user' | 'assistant', text: string, tools = 0, results = 0) =>
  ({ role, text, toolUses: Array(tools).fill({}), ...(results ? { toolResults: Array(results).fill({}) } : {}) }) as any

describe('plain-talk', () => {
  test('inline code loses its backticks, fenced code keeps them', () => {
    expect(unticked('run `ls` now\n```\n`kept`\n```\nand `x`')).toBe('run ls now\n```\n`kept`\n```\nand x')
  })

  test('text before a later tool call counts as narration, the closing text does not', () => {
    const rows = [
      row('user', 'old prompt'),
      row('assistant', 'old narration', 1),
      row('user', 'new prompt'),
      row('assistant', 'Let me look.', 1),
      row('user', '', 0, 1),
      row('assistant', '', 1),
      row('user', '', 0, 1),
      row('assistant', 'Done.'),
    ]
    expect(narration(rows)).toBe(1)
  })

  test('the drawn reply has no backticks', async ($, on) => {
    let seen = ''
    on('ui.render', ($: any, e: any) => {
      seen = e.props.text
      return $.ui.resolve(e).Text({ children: seen })
    })
    await $.ui.render({
      component: 'AssistantMessage', surface: 'terminal', requestId: 'm1',
      props: { text: 'open `config.ini`', isFirstOfReply: true },
    } as any)
    expect(seen).toBe('open config.ini')
  })
})
