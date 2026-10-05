from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.diagram_schemas import DiagramDataPayload
from app.api.v1.interview_prep.schemas import ArticleColumnPayload

pytestmark = pytest.mark.unit


def test_diagram_accepts_shapes_and_attached_arrow() -> None:
    source_id, target_id = uuid4(), uuid4()
    diagram = DiagramDataPayload.model_validate(
        {
            "version": 1,
            "shapes": [
                {
                    "id": str(source_id),
                    "kind": "rectangle",
                    "x": 40,
                    "y": 60,
                    "width": 180,
                    "height": 80,
                },
                {
                    "id": str(target_id),
                    "kind": "diamond",
                    "x": 400,
                    "y": 60,
                    "width": 150,
                    "height": 100,
                },
            ],
            "connectors": [
                {"id": str(uuid4()), "source_id": str(source_id), "target_id": str(target_id)}
            ],
        }
    )

    assert len(diagram.shapes) == 2
    assert diagram.connectors[0].arrow is True


def test_diagram_rejects_connector_to_missing_shape() -> None:
    with pytest.raises(ValidationError, match="reference shapes"):
        DiagramDataPayload.model_validate(
            {
                "shapes": [
                    {
                        "id": str(uuid4()),
                        "kind": "ellipse",
                        "x": 50,
                        "y": 50,
                        "width": 100,
                        "height": 80,
                    }
                ],
                "connectors": [
                    {"id": str(uuid4()), "source_id": str(uuid4()), "target_id": str(uuid4())}
                ],
            }
        )


def test_diagram_rejects_non_hex_colors_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DiagramDataPayload.model_validate(
            {
                "shapes": [
                    {
                        "id": str(uuid4()),
                        "kind": "rectangle",
                        "x": 10,
                        "y": 20,
                        "width": 100,
                        "height": 80,
                        "fill": "url(https://example.test)",
                    }
                ]
            }
        )
    with pytest.raises(ValidationError):
        DiagramDataPayload.model_validate({"shapes": [], "connectors": [], "raw_svg": "<script/>"})


def test_article_diagram_column_requires_structured_diagram_data() -> None:
    common = {"id": str(uuid4()), "label": "Diagram", "type": "diagram"}
    with pytest.raises(ValidationError, match="require diagram_data"):
        ArticleColumnPayload.model_validate(common)

    column = ArticleColumnPayload.model_validate(
        {**common, "diagram_data": {"version": 1, "shapes": [], "connectors": []}}
    )
    assert column.diagram_data is not None


def test_non_diagram_article_column_rejects_diagram_payload() -> None:
    with pytest.raises(ValidationError, match="other block types"):
        ArticleColumnPayload.model_validate(
            {
                "id": str(uuid4()),
                "label": "Text",
                "type": "rich_text",
                "html": "<p>ok</p>",
                "diagram_data": {"version": 1, "shapes": [], "connectors": []},
            }
        )
