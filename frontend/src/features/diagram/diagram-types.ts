export type DiagramShapeKind = "rectangle" | "ellipse" | "triangle" | "diamond";

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

export interface DiagramDocument {
  version: 1;
  shapes: DiagramShape[];
  connectors: DiagramConnector[];
}

export type DiagramDocumentInput = {
  version: 1;
  shapes?: DiagramShape[];
  connectors?: DiagramConnector[];
};

export const EMPTY_DIAGRAM: DiagramDocument = { version: 1, shapes: [], connectors: [] };
