"""LLM service abstraction — the single entry point application
services call to invoke the AI Platform. See service.py (LLMService,
LLMServiceInterface) and provider_interface.py (LLMProviderInterface,
LLMRequest, LLMResponse).
"""

from app.ai_platform.llm_service.provider_interface import (
    LLMProviderInterface,
    LLMRequest,
    LLMResponse,
)
from app.ai_platform.llm_service.service import LLMService, LLMServiceInterface

__all__ = [
    "LLMProviderInterface",
    "LLMRequest",
    "LLMResponse",
    "LLMService",
    "LLMServiceInterface",
]
