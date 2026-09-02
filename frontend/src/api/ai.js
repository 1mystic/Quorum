// Real POST /api/t/{slug}/ai/chat (app/api/ai.py, app/agent/loop.py). One
// turn of the bounded tool-calling agent: it narrates real Evidence and
// group/event recommendations, it never computes or recomputes a statistic
// itself (docs/RULES.md rule 5). MEMBER-scoped, same as every other
// tenant-scoped call - no admin widening here, see the router's own comment.
//
// Response shape is app/schemas/ai.py's AgentChatResponse: `degraded` means
// the model was unreachable and a deterministic recommender answered
// instead; `offline` means the database was unreachable/unseeded and the
// answer is grounded in sample data. Both are independent, real states the
// UI must show, never smooth over - same posture as `insufficient_data`
// elsewhere in the app.

import { api, tenantPath } from './client'

export function chat(slug, { messages, interestText = '' } = {}) {
  return api.post(tenantPath(slug, '/ai/chat'), {
    messages,
    interest_text: interestText
  })
}
