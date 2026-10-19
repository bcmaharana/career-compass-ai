from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.adapters.db.repositories.interview_prep import (
    _article_column_from_json,
    _article_column_to_json,
)
from app.adapters.db.repositories.showcase_page import _column_from_json, _column_to_json
from app.api.v1.interview_prep.router import (
    _article_column_from_payload,
    _article_column_payload,
)
from app.api.v1.interview_prep.schemas import ArticleColumnPayload
from app.api.v1.public_sharing.schemas import PublicArticleColumn, PublicShowcaseColumn
from app.api.v1.showcase_page.router import _column_from_payload, _column_payload
from app.api.v1.showcase_page.schemas import ShowcaseColumnPayload
from app.domain.content_blocks.entities import ContentColumn

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "schema",
    [
        ArticleColumnPayload,
        ShowcaseColumnPayload,
        PublicArticleColumn,
        PublicShowcaseColumn,
    ],
)
def test_column_appearance_defaults_and_custom_values(schema: type[BaseModel]) -> None:
    base = {"id": str(uuid4()), "type": "rich_text", "label": "Text"}

    default_column = schema.model_validate(base)
    assert default_column.show_background is True
    assert default_column.background_color is None

    customized_column = schema.model_validate(
        {**base, "show_background": False, "background_color": "#3b82f6"}
    )
    assert customized_column.show_background is False
    assert customized_column.background_color == "#3b82f6"


def test_article_column_appearance_round_trips_and_legacy_columns_default_on() -> None:
    column = ContentColumn(
        id=uuid4(),
        type="rich_text",
        label="Article",
        show_background=False,
        background_color="#f3f4f6",
    )

    serialized = _article_column_to_json(column)
    restored = _article_column_from_json(serialized)
    assert restored.show_background is False
    assert restored.background_color == "#f3f4f6"

    legacy = _article_column_from_json(
        {"id": str(uuid4()), "type": "rich_text", "label": "Legacy"}
    )
    assert legacy.show_background is True
    assert legacy.background_color is None


def test_showcase_column_appearance_round_trips_and_legacy_columns_default_on() -> None:
    column = ContentColumn(
        id=uuid4(),
        type="rich_text",
        label="Showcase",
        show_background=False,
        background_color="#f3f4f6",
    )

    serialized = _column_to_json(column)
    restored = _column_from_json(serialized)
    assert restored.show_background is False
    assert restored.background_color == "#f3f4f6"

    legacy = _column_from_json({"id": str(uuid4()), "type": "rich_text", "label": "Legacy"})
    assert legacy.show_background is True
    assert legacy.background_color is None


def test_article_api_payload_preserves_background_settings() -> None:
    payload = ArticleColumnPayload.model_validate(
        {
            "id": str(uuid4()),
            "type": "rich_text",
            "label": "Article",
            "show_background": False,
            "background_color": "#f3f4f6",
        }
    )

    restored = _article_column_payload(_article_column_from_payload(payload), {})
    assert restored.show_background is False
    assert restored.background_color == "#f3f4f6"


def test_showcase_api_payload_preserves_background_settings() -> None:
    payload = ShowcaseColumnPayload.model_validate(
        {
            "id": str(uuid4()),
            "type": "rich_text",
            "label": "Showcase",
            "show_background": False,
            "background_color": "#f3f4f6",
        }
    )

    restored = _column_payload(_column_from_payload(payload))
    assert restored.show_background is False
    assert restored.background_color == "#f3f4f6"
