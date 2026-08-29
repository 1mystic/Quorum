import { describe, test, expect, vi, beforeEach } from 'vitest'
import { askAssistant } from './ai'

// A well-formed POST /ai/chat response, matching AgentChatResponse.
function chatResponse(overrides = {}) {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      reply: 'Robotics & Automation looks like a good fit.',
      kind: 'clubs',
      items: [{ id: 1, name: 'Robotics & Automation', entity_kind: 'club' }],
      degraded: false,
      tools_used: ['recommend_clubs'],
      iterations: 2,
      budget_exhausted: false,
      ...overrides
    })
  }
}

function lastRequest() {
  const [url, options] = global.fetch.mock.calls[0]
  return { url, options, body: JSON.parse(options.body) }
}

describe('askAssistant', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  test('posts the question and the transcript to /ai/chat', async () => {
    global.fetch = vi.fn().mockResolvedValue(chatResponse())

    await askAssistant('I love building robots', [])

    const { url, body } = lastRequest()

    expect(url).toContain('/ai/chat')
    expect(body.interest_text).toBe('I love building robots')
    expect(body.messages).toEqual([])
  })

  test('replays earlier turns as alternating user and assistant messages', async () => {
    global.fetch = vi.fn().mockResolvedValue(chatResponse())

    const conversation = [
      { query: 'photography clubs?', message: 'Photography Circle runs photo walks.' }
    ]

    await askAssistant('any events?', conversation)

    expect(lastRequest().body.messages).toEqual([
      { role: 'user', content: 'photography clubs?' },
      { role: 'assistant', content: 'Photography Circle runs photo walks.' }
    ])
  })

  test('sends only the last 10 turns so long chats do not grow the prompt', async () => {
    global.fetch = vi.fn().mockResolvedValue(chatResponse())

    const conversation = []
    for (let index = 0; index < 15; index += 1) {
      conversation.push({ query: 'q' + index, message: 'a' + index })
    }

    await askAssistant('latest', conversation)

    const messages = lastRequest().body.messages

    // 10 turns, each contributing a user and an assistant message.
    expect(messages).toHaveLength(20)
    expect(messages[0].content).toBe('q5')
  })

  test('attaches the bearer token when the student is signed in', async () => {
    global.fetch = vi.fn().mockResolvedValue(chatResponse())
    localStorage.setItem('cc_token', 'test-token')

    await askAssistant('robots', [])

    expect(lastRequest().options.headers.Authorization).toBe('Bearer test-token')
  })

  test('maps the response onto what the finder view renders', async () => {
    global.fetch = vi.fn().mockResolvedValue(chatResponse())

    const result = await askAssistant('robots', [])

    expect(result.message).toBe('Robotics & Automation looks like a good fit.')
    expect(result.kind).toBe('clubs')
    expect(result.items).toHaveLength(1)
    expect(result.toolsUsed).toEqual(['recommend_clubs'])
    expect(result.degraded).toBe(false)
    expect(result.offline).toBe(false)
  })

  test('surfaces degraded and offline as separate flags', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      chatResponse({ degraded: true, offline: true })
    )

    const result = await askAssistant('robots', [])

    expect(result.degraded).toBe(true)
    expect(result.offline).toBe(true)
  })

  test('throws when the request fails so the view can mark the turn failed', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' })
    })

    await expect(askAssistant('robots', [])).rejects.toThrow('Not authenticated')
  })
})
