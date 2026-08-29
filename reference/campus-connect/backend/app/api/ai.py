"""
The AI assistant endpoint.

One route: POST /ai/chat, running the bounded tool-calling loop in
app/agent/loop.py. Follows the exact same shape as every other router in this
package - Security(get_user_info, scopes=[...]) for auth, Depends(get_*_service)
for data access - so the AI module is not a special case integration-wise, it
is one more router calling the same services everything else calls.
"""
from fastapi import APIRouter, Depends, Security

from app.agent.demo_data import resolve_services
from app.agent.loop import run_agent_turn
from app.core.di import (
    get_announcement_service,
    get_club_service,
    get_event_service,
    get_student_service,
    get_user_info,
)
from app.schemas import AgentChatRequest, AgentChatResponse
from app.services import AnnouncementService, ClubService, EventService, StudentService

ai_router = APIRouter(prefix="/ai", tags=["AI"])


@ai_router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    data: AgentChatRequest,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    club_service: ClubService = Depends(get_club_service),
    event_service: EventService = Depends(get_event_service),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
    student_service: StudentService = Depends(get_student_service),
) -> AgentChatResponse:
    """
    One turn of the bounded agent loop.

    Never raises on a model or service failure. There are two independent
    degradation axes and the response reports both:

      offline=true    the database was unreachable or unseeded, so the answer
                      is grounded in the sample campus in agent/demo_data.py
      degraded=true   the model was unreachable, so the answer came from the
                      deterministic recommender instead of the agent loop

    Either can happen without the other, which is why they are separate fields
    rather than one "something went wrong" flag.
    """
    services, offline = await resolve_services(
        payload, club_service, event_service, announcement_service, student_service
    )
    history = [{"role": m.role, "content": m.content} for m in data.messages]

    result = await run_agent_turn(
        messages=history,
        payload=payload,
        services=services,
        interest_text=data.interest_text,
        offline=offline,
    )

    return AgentChatResponse(
        reply=result.reply,
        kind=result.kind,
        items=result.items,
        degraded=result.degraded,
        offline=offline,
        tools_used=result.tools_used,
        iterations=result.budget.iterations if result.budget else 0,
        budget_exhausted=bool(result.budget and result.budget.exhausted_reason),
    )
