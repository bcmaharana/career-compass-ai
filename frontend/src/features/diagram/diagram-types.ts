export type DiagramShapeKind = "rectangle" | "ellipse" | "circle" | "triangle" | "diamond" | "pentagon" | "hexagon";

export interface DiagramShape {
  id: string;
  kind: DiagramShapeKind;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  text: string;
  font_size: number;
  text_color: string;
  bold: boolean;
  italic: boolean;
  text_align: "left" | "center" | "right";
  text_vertical_align: "top" | "middle" | "bottom";
  fill: string;
  stroke: string;
  stroke_width: number;
}

export interface DiagramConnector {
  id: string;
  source_id: string;
  target_id: string;
  color: string;
  stroke_width: number;
  arrow: boolean;
  label: string;
}

export interface DiagramLine {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  stroke_width: number;
  arrow_start: boolean;
  arrow_end: boolean;
  start_shape_id?: string | null;
  start_anchor_x?: number | null;
  start_anchor_y?: number | null;
  end_shape_id?: string | null;
  end_anchor_x?: number | null;
  end_anchor_y?: number | null;
}

export interface DiagramDocument {
  version: 1;
  shapes: DiagramShape[];
  connectors: DiagramConnector[];
  lines: DiagramLine[];
}

export type DiagramDocumentInput = {
  version: 1;
  shapes?: DiagramShape[];
  connectors?: DiagramConnector[];
  lines?: DiagramLine[];
};

export const EMPTY_DIAGRAM: DiagramDocument = { version: 1, shapes: [], connectors: [], lines: [] };
