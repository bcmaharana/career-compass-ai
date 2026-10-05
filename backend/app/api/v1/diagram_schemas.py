"""Validated, serializable data for article and showcase diagrams."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

HexColor = str
_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class DiagramShapePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: Literal["rectangle", "ellipse", "triangle", "diamond"]
    x: float = Field(ge=0, le=900)
    y: float = Field(ge=0, le=500)
    width: float = Field(ge=40, le=500)
    height: float = Field(ge=40, le=400)
    rotation: float = Field(default=0, ge=-180, le=180)
    text: str = Field(default="", max_length=180)
    font_size: int = Field(default=16, ge=8, le=48)
    text_color: HexColor = Field(default="#0f172a", pattern=_COLOR_PATTERN)
    bold: bool = False
    italic: bool = False
    text_align: Literal["left", "center", "right"] = "center"
    text_vertical_align: Literal["top", "middle", "bottom"] = "middle"
    fill: HexColor = Field(default="#ffffff", pattern=_COLOR_PATTERN)
    stroke: HexColor = Field(default="#334155", pattern=_COLOR_PATTERN)
    stroke_width: float = Field(default=2, ge=1, le=10)


class DiagramConnectorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_id: UUID
    target_id: UUID
    color: HexColor = Field(default="#475569", pattern=_COLOR_PATTERN)
    stroke_width: float = Field(default=2, ge=1, le=10)
    arrow: bool = True
    label: str = Field(default="", max_length=120)


class DiagramDataPayload(BaseModel):
    """Versioned application-owned scene data; never raw SVG/HTML."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    shapes: list[DiagramShapePayload] = Field(default_factory=list, max_length=100)
    connectors: list[DiagramConnectorPayload] = Field(default_factory=list, max_length=150)

    @model_validator(mode="after")
    def validate_references(self) -> DiagramDataPayload:
        shape_ids = [shape.id for shape in self.shapes]
        connector_ids = [connector.id for connector in self.connectors]
        if len(set(shape_ids)) != len(shape_ids):
            raise ValueError("Diagram shape IDs must be unique.")
        if len(set(connector_ids)) != len(connector_ids):
            raise ValueError("Diagram connector IDs must be unique.")
        known = set(shape_ids)
        for connector in self.connectors:
            if connector.source_id == connector.target_id:
                raise ValueError("A diagram connector must connect two different shapes.")
            if connector.source_id not in known or connector.target_id not in known:
                raise ValueError("Diagram connectors must reference shapes in the same diagram.")
        return self
