"""Chat API routes (UI enhancement brief Part 1.2).

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service — a caller
only ever sends messages into / continues their own conversations, so
no extra RBAC permission is required beyond a valid identity, matching
the career-profile router's convention.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_chat_service, get_current_identity
from app.api.v1.chat.schemas import (
    ChatMessageResponse,
    DeleteChatMessageResponse,
    LatestConversationResponse,
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
        section_key=request.section_key,
        content=request.content,
    )
    return _turn_response(turn)


@router.get("/chat/conversations/latest", response_model=LatestConversationResponse)
async def get_latest_conversation(
    section_key: str = Query(..., min_length=1, max_length=100),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ChatService = Depends(get_chat_service),
) -> LatestConversationResponse:
    conversation_id = await service.get_latest_conversation_id(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), section_key=section_key
    )
    return LatestConversationResponse(conversation_id=conversation_id)


@router.get(
    "/chat/conversations/{conversation_id}/messages", response_model=list[ChatMessageResponse]
)
async def list_chat_messages(
    conversation_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ChatService = Depends(get_chat_service),
) -> list[ChatMessageResponse]:
    """Real, fetchable history (2026-08-21) — lets the AI Career Coach
    conversation be redisplayed in full whenever it's shown, matching
    JD Tailoring's own GET messages endpoint."""
    messages = await service.list_messages(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        conversation_id=conversation_id,
    )
    return [
        ChatMessageResponse(
            id=m.id, role=m.role.value, content=m.content, created_at=m.created_at
        )
        for m in messages
    ]


@router.delete(
    "/chat/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_chat_conversation(
    conversation_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ChatService = Depends(get_chat_service),
) -> None:
    """Removes the whole conversation — the next message this user sends
    starts a genuinely new one. Matching JD Tailoring's session delete."""
    await service.delete_conversation(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        conversation_id=conversation_id,
    )


@router.delete(
    "/chat/conversations/{conversation_id}/messages",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_chat_messages(
    conversation_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ChatService = Depends(get_chat_service),
) -> None:
    """Clears just the conversation — the conversation row itself (and
    its id) stays, so the next message keeps using it. Matching JD
    Tailoring's "Clear conversation" action."""
    await service.clear_messages(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        conversation_id=conversation_id,
    )


@router.delete("/chat/conversations/{conversation_id}/messages/{message_id}")
async def delete_chat_message(
    conversation_id: UUID,
    message_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ChatService = Depends(get_chat_service),
) -> DeleteChatMessageResponse:
    """Removes a whole question+answer turn — the message targeted plus
    its paired counterpart, if one sits immediately adjacent to it.
    Matching JD Tailoring's per-message delete exactly."""
    deleted_ids = await service.delete_message(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        conversation_id=conversation_id,
        message_id=message_id,
    )
    return DeleteChatMessageResponse(deleted_message_ids=deleted_ids)
