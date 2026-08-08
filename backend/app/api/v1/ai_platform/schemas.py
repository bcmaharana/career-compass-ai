"""Request/response schemas for the AI Platform model-preference API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

# Friendly labels for known model_name values — falls back to the raw
# string for anything not listed, so a newly-seeded model never renders
# blank while this map is caught up.
_DISPLAY_NAMES: dict[str, str] = {
    "claude-opus-5": "Claude Opus 5",
    "claude-sonnet-5": "Claude Sonnet 5",
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "qwen2.5:7b": "Qwen 2.5 7B (Local)",
    "qwen2.5:3b": "Qwen 2.5 3B (Local)",
    "qwen2.5-coder:7b": "Qwen 2.5 Coder 7B (Local)",
    "qwen2.5-coder:3b": "Qwen 2.5 Coder 3B (Local)",
    "llama-3.3-70b-versatile": "Llama 3.3 70B (Groq)",
    "llama-3.1-8b-instant": "Llama 3.1 8B (Groq)",
    "qwen/qwen3.6-27b": "Qwen 3.6 27B (Groq, preview)",
}


def display_name(model_name: str) -> str:
    return _DISPLAY_NAMES.get(model_name, model_name)


class ModelOptionResponse(BaseModel):
    id: UUID
    provider: str
    model_name: str
    display_name: str
    is_default: bool


class ModelSelectionResponse(BaseModel):
    available: list[ModelOptionResponse]
    selected_id: UUID


class SetModelPreferenceRequest(BaseModel):
    #: None clears the user's override, reverting to the platform default.
    model_version_id: UUID | None = None
