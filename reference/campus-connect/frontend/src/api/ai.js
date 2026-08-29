const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem('cc_token')

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || error.message || 'Request failed')
  }

  return response.json()
}

// The assistant answers one turn at a time and keeps no server-side session, so
// the client owns the transcript and replays it. Only the recent turns are worth
// sending - the backend trims to the last 10 anyway, and a long transcript costs
// tokens on every request.
const HISTORY_LIMIT = 10

function toApiMessages(conversation) {
  const messages = []

  for (const turn of conversation.slice(-HISTORY_LIMIT)) {
    messages.push({ role: 'user', content: turn.query })
    if (turn.message) {
      messages.push({ role: 'assistant', content: turn.message })
    }
  }

  return messages
}

/**
 * Ask the assistant one question.
 *
 * `degraded` means the model was unreachable and the deterministic recommender
 * answered instead; `offline` means the live club data was unreachable and the
 * answer is grounded in sample data. They are independent - the UI shows a
 * different notice for each.
 */
export async function askAssistant(question, conversation = []) {
  const data = await apiRequest('/ai/chat', {
    method: 'POST',
    body: JSON.stringify({
      messages: toApiMessages(conversation),
      interest_text: question
    })
  })

  return {
    message: data.reply || '',
    kind: data.kind || 'chat',
    items: data.items || [],
    degraded: Boolean(data.degraded),
    offline: Boolean(data.offline),
    toolsUsed: data.tools_used || []
  }
}

export { BASE_URL }
