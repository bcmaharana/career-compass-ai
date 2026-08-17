"""Interview Preparation API routes.

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service data, no
extra RBAC permission required beyond get_current_identity — same as
every career-profile route.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, status

from app.api.dependencies import (
    get_current_identity,
    get_interview_answer_service,
    get_interview_prep_summary_service,
    get_interview_question_service,
    get_interview_topic_service,
)
from app.api.v1.career_profile.schemas import MoveRequest
from app.api.v1.interview_prep.schemas import (
    AddFollowUpQuestionRequest,
    InterviewPrepMoveRequest,
    InterviewPrepScopeSummaryResponse,
    InterviewQuestionRequest,
    InterviewQuestionResponse,
    InterviewQuestionUpdateRequest,
    InterviewTopicRequest,
    InterviewTopicResponse,
    InterviewTopicUpdateRequest,
    ReferenceLinkPayload,
    UpdateFollowUpQuestionRequest,
)
from app.application.interview_prep.interview_answer_service import InterviewAnswerService
from app.application.interview_prep.interview_prep_summary_service import (
    InterviewPrepSummaryService,
)
from app.application.interview_prep.interview_question_service import InterviewQuestionService
from app.application.interview_prep.interview_topic_service import InterviewTopicService
from app.core.identity_provider_interface import IdentityClaims
from app.domain.interview_prep.entities import InterviewQuestion, InterviewTopic, ReferenceLink

router = APIRouter(tags=["interview-prep"])


async def _topic_response(
    service: InterviewTopicService, topic: InterviewTopic
) -> InterviewTopicResponse:
    image_url = await service.get_presigned_image_url(topic)
    return InterviewTopicResponse(
        id=topic.id,
        name=topic.name,
        section=topic.section,
        discussion=topic.discussion,
        image_url=image_url,
        reference_links=[
            ReferenceLinkPayload(url=link.url, label=link.label) for link in topic.reference_links
        ],
        scope_target_role_ids=topic.scope_target_role_ids,
        created_at=topic.created_at,
    )


def _question_response(question: InterviewQuestion) -> InterviewQuestionResponse:
    return InterviewQuestionResponse(
        id=question.id,
        topic_id=question.topic_id,
        question=question.question,
        category=question.category,
        manual_answer=question.manual_answer,
        ai_answer=question.ai_answer,
        ai_answer_status=question.ai_answer_status,
        ai_answer_error=question.ai_answer_error,
        ai_answer_generated_at=question.ai_answer_generated_at,
        reference_links=[
            ReferenceLinkPayload(url=link.url, label=link.label) for link in question.reference_links
        ],
        scope_target_role_ids=question.scope_target_role_ids,
        parent_question_id=question.parent_question_id,
        follow_ups=[_question_response(f) for f in question.follow_ups],
        created_at=question.created_at,
    )


@router.get("/interview-prep/topics", response_model=list[InterviewTopicResponse])
async def list_interview_topics(
    target_role_id: UUID | None = None,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewTopicService = Depends(get_interview_topic_service),
) -> list[InterviewTopicResponse]:
    topics = await service.list_for_scope(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [await _topic_response(service, t) for t in topics]


@router.post(
    "/interview-prep/topics", response_model=InterviewTopicResponse, status_code=status.HTTP_201_CREATED
)
async def add_interview_topic(
    request: InterviewTopicRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewTopicService = Depends(get_interview_topic_service),
) -> InterviewTopicResponse:
    topic = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        name=request.name,
        section=request.section,
        discussion=request.discussion,
        scope_target_role_ids=request.scope_target_role_ids,
    )
    return await _topic_response(service, topic)


@router.patch("/interview-prep/topics/{topic_id}", response_model=InterviewTopicResponse)
async def update_interview_topic(
    topic_id: UUID,
    request: InterviewTopicUpdateRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewTopicService = Depends(get_interview_topic_service),
) -> InterviewTopicResponse:
    topic = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        topic_id=topic_id,
        name=request.name,
        section=request.section,
        discussion=request.discussion,
        reference_links=[ReferenceLink(url=link.url, label=link.label) for link in request.reference_links],
        scope_target_role_ids=request.scope_target_role_ids,
    )
    return await _topic_response(service, topic)


@router.delete("/interview-prep/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview_topic(
    topic_id: UUID,
    target_role_id: UUID | None = None,
    delete_everywhere: bool = False,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewTopicService = Depends(get_interview_topic_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        topic_id=topic_id,
        target_role_id=target_role_id,
        delete_everywhere=delete_everywhere,
    )


@router.post("/interview-prep/topics/{topic_id}/move", response_model=list[InterviewTopicResponse])
async def move_interview_topic(
    topic_id: UUID,
    request: InterviewPrepMoveRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewTopicService = Depends(get_interview_topic_service),
) -> list[InterviewTopicResponse]:
    tenant_id = UUID(identity.tenant_id)
    user_id = UUID(identity.user_id)
    await service.move(
        tenant_id=tenant_id,
        user_id=user_id,
        topic_id=topic_id,
        target_role_id=request.target_role_id,
        direction=request.direction,
    )
    topics = await service.list_for_scope(
        tenant_id=tenant_id, user_id=user_id, target_role_id=request.target_role_id
    )
    return [await _topic_response(service, t) for t in topics]


@router.post("/interview-prep/topics/{topic_id}/image", response_model=InterviewTopicResponse)
async def upload_interview_topic_image(
    topic_id: UUID,
    file: UploadFile,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewTopicService = Depends(get_interview_topic_service),
) -> InterviewTopicResponse:
    content = await file.read()
    topic = await service.upload_image(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        topic_id=topic_id,
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )
    return await _topic_response(service, topic)


@router.delete("/interview-prep/topics/{topic_id}/image", response_model=InterviewTopicResponse)
async def delete_interview_topic_image(
    topic_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewTopicService = Depends(get_interview_topic_service),
) -> InterviewTopicResponse:
    topic = await service.delete_image(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), topic_id=topic_id
    )
    return await _topic_response(service, topic)


@router.get("/interview-prep/questions", response_model=list[InterviewQuestionResponse])
async def list_interview_questions(
    target_role_id: UUID | None = None,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> list[InterviewQuestionResponse]:
    questions = await service.list_for_scope(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_question_response(q) for q in questions]


@router.post(
    "/interview-prep/questions",
    response_model=InterviewQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_interview_question(
    request: InterviewQuestionRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> InterviewQuestionResponse:
    question = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        topic_id=request.topic_id,
        question=request.question,
        category=request.category,
        scope_target_role_ids=request.scope_target_role_ids,
    )
    return _question_response(question)


@router.patch("/interview-prep/questions/{question_id}", response_model=InterviewQuestionResponse)
async def update_interview_question(
    question_id: UUID,
    request: InterviewQuestionUpdateRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> InterviewQuestionResponse:
    question = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        question_id=question_id,
        topic_id=request.topic_id,
        question=request.question,
        category=request.category,
        manual_answer=request.manual_answer,
        reference_links=[ReferenceLink(url=link.url, label=link.label) for link in request.reference_links],
        scope_target_role_ids=request.scope_target_role_ids,
    )
    return _question_response(question)


@router.delete("/interview-prep/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview_question(
    question_id: UUID,
    target_role_id: UUID | None = None,
    delete_everywhere: bool = False,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        question_id=question_id,
        target_role_id=target_role_id,
        delete_everywhere=delete_everywhere,
    )


@router.post(
    "/interview-prep/questions/{question_id}/move", response_model=list[InterviewQuestionResponse]
)
async def move_interview_question(
    question_id: UUID,
    request: InterviewPrepMoveRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> list[InterviewQuestionResponse]:
    tenant_id = UUID(identity.tenant_id)
    user_id = UUID(identity.user_id)
    await service.move(
        tenant_id=tenant_id,
        user_id=user_id,
        question_id=question_id,
        target_role_id=request.target_role_id,
        direction=request.direction,
    )
    questions = await service.list_for_scope(
        tenant_id=tenant_id, user_id=user_id, target_role_id=request.target_role_id
    )
    return [_question_response(q) for q in questions]


@router.post(
    "/interview-prep/questions/{question_id}/generate-answer",
    response_model=InterviewQuestionResponse,
)
async def generate_interview_answer(
    question_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewAnswerService = Depends(get_interview_answer_service),
) -> InterviewQuestionResponse:
    question = await service.generate_answer(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), question_id=question_id
    )
    return _question_response(question)


@router.post(
    "/interview-prep/questions/{question_id}/follow-ups",
    response_model=InterviewQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_follow_up_question(
    question_id: UUID,
    request: AddFollowUpQuestionRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> InterviewQuestionResponse:
    follow_up = await service.add_follow_up(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        parent_question_id=question_id,
        question=request.question,
    )
    return _question_response(follow_up)


@router.patch(
    "/interview-prep/follow-up-questions/{follow_up_id}", response_model=InterviewQuestionResponse
)
async def update_follow_up_question(
    follow_up_id: UUID,
    request: UpdateFollowUpQuestionRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> InterviewQuestionResponse:
    follow_up = await service.update_follow_up(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        follow_up_id=follow_up_id,
        question=request.question,
        manual_answer=request.manual_answer,
        reference_links=[ReferenceLink(url=link.url, label=link.label) for link in request.reference_links],
    )
    return _question_response(follow_up)


@router.delete(
    "/interview-prep/follow-up-questions/{follow_up_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_follow_up_question(
    follow_up_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> None:
    await service.delete_follow_up(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), follow_up_id=follow_up_id
    )


@router.post(
    "/interview-prep/follow-up-questions/{follow_up_id}/move",
    response_model=list[InterviewQuestionResponse],
)
async def move_follow_up_question(
    follow_up_id: UUID,
    request: MoveRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewQuestionService = Depends(get_interview_question_service),
) -> list[InterviewQuestionResponse]:
    siblings = await service.move_follow_up(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        follow_up_id=follow_up_id,
        direction=request.direction,
    )
    return [_question_response(f) for f in siblings]


@router.get("/interview-prep/summary", response_model=list[InterviewPrepScopeSummaryResponse])
async def get_interview_prep_summary(
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewPrepSummaryService = Depends(get_interview_prep_summary_service),
) -> list[InterviewPrepScopeSummaryResponse]:
    summaries = await service.get_summary(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [
        InterviewPrepScopeSummaryResponse(
            target_role_id=s.target_role_id,
            role_name=s.role_name,
            topic_count=s.topic_count,
            question_count=s.question_count,
        )
        for s in summaries
    ]
