"""Chat API routes (UI enhancement brief Part 1.2).

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service — a caller
only ever sends messages into / continues their own conversations, so
no extra RBAC permission is required beyond a valid identity, matching
the career-profile router's convention.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_chat_service, get_current_identity
from app.api.v1.chat.schemas import (
    ChatMessageResponse,
    SendChatMessageRequest,
    SendChatMessageResponse,
)
from app.application.chat.chat_service import ChatService, ChatTurn
from app.core.identity_provider_interface import IdentityClaims

router = APIRouter(tags=["chat"])


def _turn_response(turn: ChatTurn) -> SendChatMessageResponse:
    return SendChatMessageResponse(
        conversation_id=turn.conversation_id,
        user_message=ChatMessageResponse(
            id=turn.user_message.id,
            role=turn.user_message.role.value,
            content=turn.user_message.content,
            created_at=turn.user_message.created_at,
        ),
        assistant_message=ChatMessageResponse(
            id=turn.assistant_message.id,
            role=turn.assistant_message.role.value,
            content=turn.assistant_message.content,
            created_at=turn.assistant_message.created_at,
        ),
    )


@router.post(
    "/chat/messages", response_model=SendChatMessageResponse, status_code=status.HTTP_201_CREATED
)
async def send_chat_message(
    request: SendChatMessageRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ChatService = Depends(get_chat_service),
) -> SendChatMessageResponse:
    turn = await service.send_message(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        conversation_id=request.conversation_id,
        content=request.content,
    )
    return _turn_response(turn)
