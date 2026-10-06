import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Arrow, Circle, Ellipse, Group, Layer, Line, Rect, Shape, Stage, Text, Transformer } from "react-konva";
import { createPortal } from "react-dom";
import type Konva from "konva";
import { RichTextEditor, RICH_TEXT_CONTENT_CLASSES } from "@bcmaharana/ui-kit";
import type { DiagramConnector, DiagramDocument, DiagramDocumentInput, DiagramLine, DiagramShape, DiagramShapeKind } from "./diagram-types";

const CANVAS_WIDTH = 1600;
const MAX_CANVAS_HEIGHT = 10000;
type LineTool = "line" | "start-arrow" | "end-arrow" | "both-arrows";
type SelectedItem = { kind: "shape" | "connector" | "line"; id: string } | null;
type EndpointSnap = { x: number; y: number; shapeId: string; anchorX: number; anchorY: number; distance: number };
type LinePreview = Pick<DiagramLine, "x1" | "y1" | "x2" | "y2" | "start_shape_id" | "start_anchor_x" | "start_anchor_y" | "end_shape_id" | "end_anchor_x" | "end_anchor_y">;

function copyDocument(document: DiagramDocument): DiagramDocument {
  return structuredClone(document);
}

function shapeEditorValue(shape: DiagramShape): string {
  if (shape.text_html) return shape.text_html;
  const escaped = shape.text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped.split("\n").map((line) => `<div>${line || "<br>"}</div>`).join("");
}

function sanitizeShapeHtml(html: string): string {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const allowedTags = new Set(["b", "strong", "i", "em", "u", "strike", "span", "div", "p", "br", "ul", "ol", "li", "blockquote", "a"]);
  const allowedStyles = new Set(["color", "margin", "background-color", "font-family", "font-size", "text-align", "list-style-type", "-webkit-text-fill-color"]);
  const blockedTags = new Set(["script", "style", "iframe", "object", "svg", "math"]);
  function cleanChildren(source: ParentNode): string {
    return Array.from(source.childNodes).map((node) => {
      if (node.nodeType === Node.TEXT_NODE) return (node.textContent ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (!(node instanceof HTMLElement)) return "";
      const tag = node.tagName.toLowerCase();
      if (blockedTags.has(tag)) return "";
      const children = cleanChildren(node);
      if (!allowedTags.has(tag)) return children;
      const safe = document.createElement(tag);
      for (const property of allowedStyles) {
        const value = node.style.getPropertyValue(property);
        if (value) safe.style.setProperty(property, value);
      }
      if (tag === "span" && (node.dataset.rainbow === "true" || ["sunset", "ocean"].includes(node.dataset.gradient ?? ""))) {
        if (node.dataset.rainbow === "true") safe.dataset.rainbow = "true";
        if (node.dataset.gradient) safe.dataset.gradient = node.dataset.gradient;
      }
      if (tag === "a") {
        const href = node.getAttribute("href") ?? "";
        if (/^(https?:|mailto:)/i.test(href)) {
          safe.setAttribute("href", href);
          safe.setAttribute("target", "_blank");
          safe.setAttribute("rel", "noreferrer noopener");
        }
      }
      safe.innerHTML = children;
      return safe.outerHTML;
    }).join("");
  }
  return cleanChildren(parsed.body);
}

function orderLineEndpoints<T extends LinePreview>(line: T): T {
  return line.x1 <= line.x2 ? line : {
    ...line,
    x1: line.x2, y1: line.y2, x2: line.x1, y2: line.y1,
    start_shape_id: line.end_shape_id, start_anchor_x: line.end_anchor_x, start_anchor_y: line.end_anchor_y,
    end_shape_id: line.start_shape_id, end_anchor_x: line.start_anchor_x, end_anchor_y: line.start_anchor_y,
  };
}

function shapeOutline(shape: DiagramShape): [number, number][] {
  if (shape.kind === "rectangle") return [[0, 0], [shape.width, 0], [shape.width, shape.height], [0, shape.height]];
  if (shape.kind === "ellipse" || shape.kind === "circle") {
    return Array.from({ length: 64 }, (_, index) => {
      const angle = (index * 2 * Math.PI) / 64;
      return [shape.width / 2 + Math.cos(angle) * shape.width / 2, shape.height / 2 + Math.sin(angle) * shape.height / 2];
    });
  }
  const sides = shape.kind === "triangle" ? 3 : shape.kind === "diamond" ? 4 : shape.kind === "pentagon" ? 5 : 6;
  return Array.from({ length: sides }, (_, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / sides;
    const radiusX = shape.kind === "diamond" ? shape.width / 2 : shape.width / 2 - 2;
    const radiusY = shape.kind === "diamond" ? shape.height / 2 : shape.height / 2 - 2;
    return [shape.width / 2 + Math.cos(angle) * radiusX, shape.height / 2 + Math.sin(angle) * radiusY];
  });
}

function shapeLocalToWorld(shape: DiagramShape, point: [number, number]): [number, number] {
  const [rx, ry] = rotatePoint(point[0] - shape.width / 2, point[1] - shape.height / 2, shape.rotation);
  return [shape.x + shape.width / 2 + rx, shape.y + shape.height / 2 + ry];
}

function pointOnShapeAnchor(shape: DiagramShape, anchorX: number, anchorY: number): [number, number] {
  const approximate = shapeLocalToWorld(shape, [shape.width / 2 + anchorX * shape.width / 2, shape.height / 2 + anchorY * shape.height / 2]);
  const snapped = closestShapeAnchor(shape, approximate[0], approximate[1]);
  return [snapped.x, snapped.y];
}

function closestShapeAnchor(shape: DiagramShape, x: number, y: number): EndpointSnap {
  const outline = shapeOutline(shape).map((point) => shapeLocalToWorld(shape, point));
  let closest: [number, number] = outline[0]!;
  let distanceSquared = Number.POSITIVE_INFINITY;
  for (let index = 0; index < outline.length; index++) {
    const a = outline[index]!;
    const b = outline[(index + 1) % outline.length]!;
    const dx = b[0] - a[0]; const dy = b[1] - a[1];
    const lengthSquared = dx * dx + dy * dy;
    const t = lengthSquared ? Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / lengthSquared)) : 0;
    const point: [number, number] = [a[0] + t * dx, a[1] + t * dy];
    const candidateDistance = (x - point[0]) ** 2 + (y - point[1]) ** 2;
    if (candidateDistance < distanceSquared) { closest = point; distanceSquared = candidateDistance; }
  }
  const [localX, localY] = rotatePoint(closest[0] - shape.x - shape.width / 2, closest[1] - shape.y - shape.height / 2, -shape.rotation);
  const anchorX = Math.max(-1, Math.min(1, localX / (shape.width / 2)));
  const anchorY = Math.max(-1, Math.min(1, localY / (shape.height / 2)));
  return { x: closest[0], y: closest[1], shapeId: shape.id, anchorX, anchorY, distance: Math.sqrt(distanceSquared) };
}

function syncAttachedLines(lines: DiagramLine[], shape: DiagramShape): DiagramLine[] {
  return lines.map((line) => {
    let next = line;
    if (line.start_shape_id === shape.id && line.start_anchor_x != null && line.start_anchor_y != null) {
      const [x1, y1] = pointOnShapeAnchor(shape, line.start_anchor_x, line.start_anchor_y);
      next = { ...next, x1, y1 };
    }
    if (line.end_shape_id === shape.id && line.end_anchor_x != null && line.end_anchor_y != null) {
      const [x2, y2] = pointOnShapeAnchor(shape, line.end_anchor_x, line.end_anchor_y);
      next = { ...next, x2, y2 };
    }
    return next;
  });
}

function normalizeDocument(document: DiagramDocumentInput): DiagramDocument {
  return {
    version: 1,
    shapes: structuredClone(document.shapes ?? []).map((shape) => ({
      ...shape,
      font_size: shape.font_size ?? 16,
      font_family: shape.font_family ?? "Arial, Helvetica, sans-serif",
      text_color: shape.text_color ?? "#0f172a",
      bold: shape.bold ?? false,
      italic: shape.italic ?? false,
      text_align: shape.text_align ?? "center",
      text_vertical_align: shape.text_vertical_align ?? "middle",
    })),
    connectors: structuredClone(document.connectors ?? []),
    lines: structuredClone(document.lines ?? []),
  };
}

function canvasHeight(document: DiagramDocument): number {
  const shapeBottom = Math.max(0, ...document.shapes.map((shape) => shape.y + shape.height));
  const lineBottom = Math.max(0, ...document.lines.map((line) => Math.max(line.y1, line.y2)));
  const bottom = Math.max(shapeBottom, lineBottom);
  return bottom === 0 ? 0 : Math.min(MAX_CANVAS_HEIGHT, Math.ceil(bottom + 20));
}

function linePoints(line: Pick<DiagramLine, "x1" | "y1" | "x2" | "y2">): number[] {
  if (Math.abs(line.y2 - line.y1) < 1) return [line.x1, line.y1, line.x2, line.y2];
  const elbowX = (line.x1 + line.x2) / 2;
  return [line.x1, line.y1, elbowX, line.y1, elbowX, line.y2, line.x2, line.y2];
}

function rectsIntersect(a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }): boolean {
  return a.x <= b.x + b.width && a.x + a.width >= b.x && a.y <= b.y + b.height && a.y + a.height >= b.y;
}

function polylineIntersectsRect(points: number[], rect: { x: number; y: number; width: number; height: number }): boolean {
  for (let index = 0; index + 3 < points.length; index += 2) {
    const x1 = points[index]!; const y1 = points[index + 1]!; const x2 = points[index + 2]!; const y2 = points[index + 3]!;
    const dx = x2 - x1; const dy = y2 - y1;
    let t0 = 0; let t1 = 1;
    const p = [-dx, dx, -dy, dy];
    const q = [x1 - rect.x, rect.x + rect.width - x1, y1 - rect.y, rect.y + rect.height - y1];
    let intersects = true;
    for (let edge = 0; edge < 4; edge++) {
      if (Math.abs(p[edge]!) < 0.0001) { if (q[edge]! < 0) intersects = false; }
      else {
        const ratio = q[edge]! / p[edge]!;
        if (p[edge]! < 0) t0 = Math.max(t0, ratio); else t1 = Math.min(t1, ratio);
      }
    }
    if (intersects && t0 <= t1) return true;
  }
  return false;
}

function makeShape(kind: DiagramShapeKind, index: number): DiagramShape {
  const sizes: Record<DiagramShapeKind, [number, number]> = {
    rectangle: [180, 88], ellipse: [150, 92], circle: [110, 110], triangle: [130, 112],
    diamond: [140, 110], pentagon: [130, 120], hexagon: [140, 112],
  };
  const [width, height] = sizes[kind];
  const column = index % 4;
  const row = Math.floor(index / 4);
  return {
    id: crypto.randomUUID(), kind, x: Math.max(0, 36 + column * 210), y: 36 + row * 160,
    width, height, rotation: 0, text: kind === "rectangle" ? "Text" : "",
    font_size: 16, text_color: "#0f172a", bold: false, italic: false, text_align: "center", text_vertical_align: "middle", fill: "#ffffff",
    stroke: "#334155", stroke_width: 2,
  };
}

function rotatePoint(x: number, y: number, degrees: number): [number, number] {
  const radians = (degrees * Math.PI) / 180;
  return [x * Math.cos(radians) - y * Math.sin(radians), x * Math.sin(radians) + y * Math.cos(radians)];
}

function raySegmentDistance(dx: number, dy: number, a: [number, number], b: [number, number]): number | null {
  const sx = b[0] - a[0];
  const sy = b[1] - a[1];
  const cross = dx * sy - dy * sx;
  if (Math.abs(cross) < 0.0001) return null;
  const t = (a[0] * sy - a[1] * sx) / cross;
  const u = (a[0] * dy - a[1] * dx) / cross;
  return t > 0 && u >= 0 && u <= 1 ? t : null;
}

/** Find the shape boundary in the direction of another shape, honoring rotation. */
function boundaryPoint(shape: DiagramShape, toward: DiagramShape): [number, number] {
  const cx = shape.x + shape.width / 2;
  const cy = shape.y + shape.height / 2;
  const tx = toward.x + toward.width / 2;
  const ty = toward.y + toward.height / 2;
  const [dx, dy] = rotatePoint(tx - cx, ty - cy, -shape.rotation);
  if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) return [cx, cy + shape.height / 2];
  const hw = shape.width / 2;
  const hh = shape.height / 2;
  let distance: number;
  if (shape.kind === "ellipse" || shape.kind === "circle") {
    distance = 1 / Math.sqrt((dx * dx) / (hw * hw) + (dy * dy) / (hh * hh));
  } else if (shape.kind === "diamond") {
    distance = 1 / (Math.abs(dx) / hw + Math.abs(dy) / hh);
  } else if (shape.kind !== "rectangle") {
    const vertices: [number, number][] = shape.kind === "triangle"
      ? [[0, -hh], [hw, hh], [-hw, hh]]
      : Array.from({ length: shape.kind === "pentagon" ? 5 : 6 }, (_, index) => {
            const angle = -Math.PI / 2 + (index * 2 * Math.PI) / (shape.kind === "pentagon" ? 5 : 6);
            return [Math.cos(angle) * hw, Math.sin(angle) * hh] as [number, number];
          });
    const intersections = vertices.map((point, index) => raySegmentDistance(dx, dy, point, vertices[(index + 1) % vertices.length]!)).filter((n): n is number => n !== null);
    distance = intersections.length ? Math.min(...intersections) : 0;
  } else {
    distance = Math.min(hw / Math.max(Math.abs(dx), 0.0001), hh / Math.max(Math.abs(dy), 0.0001));
  }
  const localX = dx * distance;
  const localY = dy * distance;
  const [worldX, worldY] = rotatePoint(localX, localY, shape.rotation);
  return [cx + worldX, cy + worldY];
}

function ShapeDrawing({ shape }: { shape: DiagramShape }) {
  const common = { fill: shape.fill, stroke: shape.stroke, strokeWidth: shape.stroke_width, lineJoin: "round" as const };
  if (shape.kind === "rectangle") return <Rect width={shape.width} height={shape.height} cornerRadius={5} {...common} />;
  if (shape.kind === "ellipse" || shape.kind === "circle") return <Ellipse x={shape.width / 2} y={shape.height / 2} radiusX={shape.width / 2} radiusY={shape.height / 2} {...common} />;
  return (
    <Shape
      width={shape.width}
      height={shape.height}
      {...common}
      sceneFunc={(context, canvasShape) => {
        context.beginPath();
        const outline = shapeOutline(shape);
        outline.forEach(([x, y], index) => {
          if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
        });
        context.closePath(); context.fillStrokeShape(canvasShape);
      }}
    />
  );
}

export function DiagramCanvas({
  value,
  onChange,
  readOnly = false,
}: {
  value: DiagramDocumentInput | null | undefined;
  onChange?: (document: DiagramDocument) => void;
  readOnly?: boolean;
}) {
  const initial = value ?? { version: 1 as const, shapes: [], connectors: [], lines: [] };
  const [document, setDocument] = useState<DiagramDocument>(() => normalizeDocument(initial));
  const incomingDocument = normalizeDocument(initial);
  const incomingSignature = JSON.stringify(incomingDocument);
  const [selected, setSelected] = useState<SelectedItem>(null);
  const [selectedShapeIds, setSelectedShapeIds] = useState<string[]>([]);
  const [selectedLineIds, setSelectedLineIds] = useState<string[]>([]);
  const [selectedConnectorIds, setSelectedConnectorIds] = useState<string[]>([]);
  const [marquee, setMarquee] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const [lineTool, setLineTool] = useState<LineTool | null>(null);
  const [linePreview, setLinePreview] = useState<LinePreview | null>(null);
  const [snapPreview, setSnapPreview] = useState<{ x: number; y: number } | null>(null);
  const [hasCopiedShape, setHasCopiedShape] = useState(false);
  const [viewportWidth, setViewportWidth] = useState(CANVAS_WIDTH);
  const [readOnlyZoom, setReadOnlyZoom] = useState(1);
  const [editingShapeId, setEditingShapeId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const [editorPosition, setEditorPosition] = useState({ left: 8, top: 8 });
  const canvasRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const editorPanelRef = useRef<HTMLDivElement>(null);
  const cancelTextEditRef = useRef(false);
  const transformerRef = useRef<Konva.Transformer>(null);
  const shapeRefs = useRef(new Map<string, Konva.Group>());
  const documentRef = useRef(document);
  const dragBeforeRef = useRef<DiagramDocument | null>(null);
  const undoRef = useRef<DiagramDocument[]>([]);
  const redoRef = useRef<DiagramDocument[]>([]);
  const lastIncomingSignatureRef = useRef(incomingSignature);
  const copiedItemsRef = useRef<{ shapes: DiagramShape[]; lines: DiagramLine[]; connectors: DiagramConnector[] }>({ shapes: [], lines: [], connectors: [] });
  const pasteCountRef = useRef(0);

  // The editor calls onChange as it changes, while the preview may stay
  // mounted as the server response replaces its initially empty value.
  // Reconcile incoming data so the first save appears without reopening
  // the block. Ignore equal values to preserve selection and undo state.
  useEffect(() => {
    if (lastIncomingSignatureRef.current === incomingSignature) return;
    lastIncomingSignatureRef.current = incomingSignature;
    if (JSON.stringify(documentRef.current) === JSON.stringify(incomingDocument)) return;
    documentRef.current = incomingDocument;
    setDocument(incomingDocument);
    setSelected(null);
    setSelectedShapeIds([]);
    setSelectedLineIds([]);
    setSelectedConnectorIds([]);
    undoRef.current = [];
    redoRef.current = [];
  }, [incomingDocument, incomingSignature]);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setViewportWidth(Math.max(1, entry.contentRect.width));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const transformer = transformerRef.current;
    if (!transformer) return;
    const targets = selectedShapeIds.map((id) => shapeRefs.current.get(id)).filter((node): node is Konva.Group => Boolean(node));
    transformer.nodes(targets);
    transformer.getLayer()?.batchDraw();
  }, [selected, selectedShapeIds, document.shapes]);

  useLayoutEffect(() => {
    if (!editingShapeId) return;
    const positionEditor = () => {
      const canvas = canvasRef.current;
      const panel = editorPanelRef.current;
      const shape = documentRef.current.shapes.find((item) => item.id === editingShapeId);
      if (!canvas || !panel || !shape) return;
      const canvasRect = canvas.getBoundingClientRect();
      const scale = canvasRect.width / CANVAS_WIDTH;
      const panelWidth = panel.offsetWidth;
      const panelHeight = panel.offsetHeight;
      const left = Math.max(8, Math.min(window.innerWidth - panelWidth - 8, canvasRect.left + (shape.x + shape.width / 2) * scale - panelWidth / 2));
      const shapeTop = canvasRect.top + shape.y * scale;
      const below = shapeTop + (shape.height + 12) * scale;
      const top = below + panelHeight <= window.innerHeight - 8
        ? below
        : Math.max(8, shapeTop - panelHeight - 8);
      setEditorPosition({ left, top });
    };
    positionEditor();
    window.addEventListener("resize", positionEditor);
    window.addEventListener("scroll", positionEditor, true);
    return () => {
      window.removeEventListener("resize", positionEditor);
      window.removeEventListener("scroll", positionEditor, true);
    };
  }, [editingShapeId, viewportWidth, document.shapes]);

  function setLive(next: DiagramDocument, notify = true) {
    documentRef.current = next;
    setDocument(next);
    if (notify) onChange?.(next);
  }

  function commit(next: DiagramDocument) {
    undoRef.current.push(copyDocument(documentRef.current));
    if (undoRef.current.length > 60) undoRef.current.shift();
    redoRef.current = [];
    setLive(next);
  }

  function addShape(kind: DiagramShapeKind) {
    const shape = makeShape(kind, documentRef.current.shapes.length);
    commit({ ...documentRef.current, shapes: [...documentRef.current.shapes, shape] });
    setSelected({ kind: "shape", id: shape.id });
    setSelectedShapeIds([shape.id]);
    setSelectedLineIds([]);
    setSelectedConnectorIds([]);
    setLineTool(null);
  }

  function copySelectedShape() {
    if (!selected) return;
    const shapeIds = new Set(selectedShapeIds);
    const lineIds = new Set(selectedLineIds);
    const connectorIds = new Set(selectedConnectorIds);
    if (selected.kind === "shape") shapeIds.add(selected.id);
    if (selected.kind === "line") lineIds.add(selected.id);
    if (selected.kind === "connector") connectorIds.add(selected.id);
    const items = documentRef.current;
    copiedItemsRef.current = structuredClone({
      shapes: items.shapes.filter((item) => shapeIds.has(item.id)),
      lines: items.lines.filter((item) => lineIds.has(item.id)),
      connectors: items.connectors.filter((item) => connectorIds.has(item.id)),
    });
    pasteCountRef.current = 0;
    setHasCopiedShape(Boolean(copiedItemsRef.current.shapes.length || copiedItemsRef.current.lines.length || copiedItemsRef.current.connectors.length));
  }

  function pasteShape() {
    const sources = copiedItemsRef.current;
    if (!sources.shapes.length && !sources.lines.length && !sources.connectors.length) return;
    pasteCountRef.current += 1;
    const offset = 24 * pasteCountRef.current;
    const xs = [...sources.shapes.flatMap((shape) => [shape.x, shape.x + shape.width]), ...sources.lines.flatMap((line) => [line.x1, line.x2])];
    const ys = [...sources.shapes.flatMap((shape) => [shape.y, shape.y + shape.height]), ...sources.lines.flatMap((line) => [line.y1, line.y2])];
    const minX = Math.min(0, ...xs); const maxX = Math.max(0, ...xs);
    const minY = Math.min(0, ...ys); const maxY = Math.max(0, ...ys);
    const dx = maxX + offset <= CANVAS_WIDTH ? offset : -minX;
    const dy = maxY + offset <= MAX_CANVAS_HEIGHT ? offset : -minY;
    const pastedShapes = sources.shapes.map((shape) => ({
      ...structuredClone(shape), id: crypto.randomUUID(), x: shape.x + dx, y: shape.y + dy,
    }));
    const idMap = new Map(sources.shapes.map((shape, index) => [shape.id, pastedShapes[index]!.id]));
    const pastedLines = sources.lines.map((line) => {
      const startCopied = Boolean(line.start_shape_id && idMap.has(line.start_shape_id));
      const endCopied = Boolean(line.end_shape_id && idMap.has(line.end_shape_id));
      return { ...structuredClone(line), id: crypto.randomUUID(), x1: line.x1 + dx, y1: line.y1 + dy, x2: line.x2 + dx, y2: line.y2 + dy,
        start_shape_id: startCopied ? idMap.get(line.start_shape_id!) : null, end_shape_id: endCopied ? idMap.get(line.end_shape_id!) : null,
        ...(!startCopied ? { start_anchor_x: null, start_anchor_y: null } : {}), ...(!endCopied ? { end_anchor_x: null, end_anchor_y: null } : {}),
      };
    });
    const pastedConnectors = sources.connectors.map((connector) => ({ ...structuredClone(connector), id: crypto.randomUUID(), source_id: idMap.get(connector.source_id) ?? connector.source_id, target_id: idMap.get(connector.target_id) ?? connector.target_id }));
    commit({ ...documentRef.current, shapes: [...documentRef.current.shapes, ...pastedShapes], lines: [...documentRef.current.lines, ...pastedLines], connectors: [...documentRef.current.connectors, ...pastedConnectors] });
    const shapeIds = pastedShapes.map((item) => item.id); const lineIds = pastedLines.map((item) => item.id); const connectorIds = pastedConnectors.map((item) => item.id);
    setSelectedShapeIds(shapeIds); setSelectedLineIds(lineIds); setSelectedConnectorIds(connectorIds);
    const primary: SelectedItem = shapeIds.length ? { kind: "shape", id: shapeIds.at(-1)! } : lineIds.length ? { kind: "line", id: lineIds.at(-1)! } : connectorIds.length ? { kind: "connector", id: connectorIds.at(-1)! } : null;
    setSelected(primary);
  }

  function nearestSnapPoint(x: number, y: number): EndpointSnap | null {
    let nearest: EndpointSnap | null = null;
    for (const shape of documentRef.current.shapes) {
      const candidate = closestShapeAnchor(shape, x, y);
      if ((!nearest || candidate.distance < nearest.distance) && candidate.distance <= 28) nearest = candidate;
    }
    return nearest;
  }

  function endpointPatch(which: "start" | "end", x: number, y: number): Partial<DiagramLine> {
    const snap = nearestSnapPoint(x, y);
    return which === "start"
      ? { x1: snap?.x ?? x, y1: snap?.y ?? y, start_shape_id: snap?.shapeId ?? null, start_anchor_x: snap?.anchorX ?? null, start_anchor_y: snap?.anchorY ?? null }
      : { x2: snap?.x ?? x, y2: snap?.y ?? y, end_shape_id: snap?.shapeId ?? null, end_anchor_x: snap?.anchorX ?? null, end_anchor_y: snap?.anchorY ?? null };
  }

  function beginLineDraw(position: { x: number; y: number }) {
    if (!lineTool) return;
    const x = Math.max(0, Math.min(CANVAS_WIDTH, position.x));
    const y = Math.max(0, Math.min(MAX_CANVAS_HEIGHT, position.y));
    const snap = nearestSnapPoint(x, y);
    const start = snap ? { x1: snap.x, y1: snap.y, start_shape_id: snap.shapeId, start_anchor_x: snap.anchorX, start_anchor_y: snap.anchorY } : { x1: x, y1: y, start_shape_id: null, start_anchor_x: null, start_anchor_y: null };
    setLinePreview({ ...start, x2: start.x1, y2: start.y1, end_shape_id: null, end_anchor_x: null, end_anchor_y: null });
    setSnapPreview(snap ? { x: snap.x, y: snap.y } : null);
  }

  function finishLineDraw() {
    const preview = linePreview;
    if (!lineTool || !preview) return;
    setLinePreview(null);
    setSnapPreview(null);
    if (Math.hypot(preview.x2 - preview.x1, preview.y2 - preview.y1) < 8) return;
    const line: DiagramLine = {
      id: crypto.randomUUID(), ...orderLineEndpoints(preview), color: "#475569", stroke_width: 2,
      arrow_start: lineTool === "start-arrow" || lineTool === "both-arrows",
      arrow_end: lineTool === "end-arrow" || lineTool === "both-arrows",
    };
    commit({ ...documentRef.current, lines: [...documentRef.current.lines, line] });
    setSelected({ kind: "line", id: line.id });
    setSelectedShapeIds([]);
    setSelectedLineIds([line.id]); setSelectedConnectorIds([]);
    setLineTool(null);
  }

  function updateLinePreview(event: { target: Konva.Node }) {
    if (!lineTool || readOnly) return;
    const position = event.target.getStage()?.getPointerPosition();
    if (!position) return;
    const x = Math.max(0, Math.min(CANVAS_WIDTH, position.x / stageScale));
    const y = Math.max(0, Math.min(MAX_CANVAS_HEIGHT, position.y / stageScale));
    const end = endpointPatch("end", x, y);
    setLinePreview((current) => current ? { ...current, ...end } : current);
    const snap = nearestSnapPoint(x, y);
    setSnapPreview(snap ? { x: snap.x, y: snap.y } : null);
  }

  function editShapeText(shape: DiagramShape) {
    if (readOnly || lineTool) return;
    cancelTextEditRef.current = false;
    setEditingText(shapeEditorValue(shape));
    setEditingShapeId(shape.id);
  }

  function finishShapeText() {
    const id = editingShapeId;
    if (id && !cancelTextEditRef.current) {
      const text = new DOMParser().parseFromString(editingText, "text/html").body.textContent?.replace(/\s+/g, " ").trim() ?? "";
      updateShape(id, { text, text_html: editingText });
    }
    cancelTextEditRef.current = false;
    setEditingShapeId(null);
  }

  function updateShape(id: string, patch: Partial<DiagramShape>) {
    const shapes = documentRef.current.shapes.map((shape) => shape.id === id ? { ...shape, ...patch } : shape);
    const updatedShape = shapes.find((shape) => shape.id === id);
    const lines = updatedShape ? syncAttachedLines(documentRef.current.lines, updatedShape) : documentRef.current.lines;
    const next = { ...documentRef.current, shapes, lines };
    commit(next);
  }

  function updateConnector(id: string, patch: Partial<DiagramConnector>) {
    const next = { ...documentRef.current, connectors: documentRef.current.connectors.map((edge) => edge.id === id ? { ...edge, ...patch } : edge) };
    commit(next);
  }

  function updateLine(id: string, patch: Partial<DiagramLine>) {
    const next = { ...documentRef.current, lines: documentRef.current.lines.map((line) => line.id === id ? { ...line, ...patch } : line) };
    commit(next);
  }

  function removeSelected() {
    if (!selected) return;
    const removedIds = new Set(selectedShapeIds);
    const removedLineIds = new Set(selectedLineIds);
    const removedConnectorIds = new Set(selectedConnectorIds);
    if (selected.kind === "shape") removedIds.add(selected.id);
    if (selected.kind === "line") removedLineIds.add(selected.id);
    if (selected.kind === "connector") removedConnectorIds.add(selected.id);
    if (removedIds.size) {
      const lines = documentRef.current.lines.map((line) => ({
        ...line,
        ...(line.start_shape_id && removedIds.has(line.start_shape_id) ? { start_shape_id: null, start_anchor_x: null, start_anchor_y: null } : {}),
        ...(line.end_shape_id && removedIds.has(line.end_shape_id) ? { end_shape_id: null, end_anchor_x: null, end_anchor_y: null } : {}),
      }));
      commit({
        ...documentRef.current,
        shapes: documentRef.current.shapes.filter((shape) => !removedIds.has(shape.id)),
        connectors: documentRef.current.connectors.filter((edge) => !removedConnectorIds.has(edge.id) && !removedIds.has(edge.source_id) && !removedIds.has(edge.target_id)),
        lines: lines.filter((line) => !removedLineIds.has(line.id)),
      });
    } else {
      commit({ ...documentRef.current, lines: documentRef.current.lines.filter((line) => !removedLineIds.has(line.id)), connectors: documentRef.current.connectors.filter((edge) => !removedConnectorIds.has(edge.id)) });
    }
    setSelected(null);
    setSelectedShapeIds([]); setSelectedLineIds([]); setSelectedConnectorIds([]);
  }

  function moveSelectedLayer(direction: "forward" | "backward") {
    if (selected?.kind !== "shape") return;
    const shapes = [...documentRef.current.shapes];
    const index = shapes.findIndex((shape) => shape.id === selected.id);
    const target = direction === "forward" ? index + 1 : index - 1;
    if (index < 0 || target < 0 || target >= shapes.length) return;
    [shapes[index], shapes[target]] = [shapes[target]!, shapes[index]!];
    commit({ ...documentRef.current, shapes });
  }

  function undo() {
    const previous = undoRef.current.pop();
    if (!previous) return;
    redoRef.current.push(copyDocument(documentRef.current));
    setLive(previous);
  }

  function redo() {
    const next = redoRef.current.pop();
    if (!next) return;
    undoRef.current.push(copyDocument(documentRef.current));
    setLive(next);
  }

  useEffect(() => {
    if (readOnly) return;
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable=true]")) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "c" && selected) {
        event.preventDefault(); copySelectedShape();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "v" && hasCopiedShape) {
        event.preventDefault(); pasteShape();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault(); event.shiftKey ? redo() : undo();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
        event.preventDefault(); redo();
      } else if ((event.key === "Delete" || event.key === "Backspace") && selected) {
        event.preventDefault(); removeSelected();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // Document and clipboard data are read through refs; selected is the
    // only state captured by the listener and is included below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readOnly, selected, selectedShapeIds, selectedLineIds, selectedConnectorIds, hasCopiedShape]);

  function onShapeClick(id: string, additive = false) {
    if (!additive) {
      setSelectedShapeIds([id]);
      setSelectedLineIds([]); setSelectedConnectorIds([]);
      setSelected({ kind: "shape", id });
      return;
    }
    const nextIds = selectedShapeIds.includes(id)
      ? selectedShapeIds.filter((selectedId) => selectedId !== id)
      : [...selectedShapeIds, id];
    setSelectedShapeIds(nextIds);
    const primaryId = nextIds.includes(id) ? id : nextIds.at(-1);
    setSelected(primaryId ? { kind: "shape", id: primaryId } : selectedLineIds.length ? { kind: "line", id: selectedLineIds.at(-1)! } : selectedConnectorIds.length ? { kind: "connector", id: selectedConnectorIds.at(-1)! } : null);
  }

  function onLineClick(id: string, additive = false) {
    if (!additive) { setSelected({ kind: "line", id }); setSelectedShapeIds([]); setSelectedLineIds([id]); setSelectedConnectorIds([]); return; }
    const next = selectedLineIds.includes(id) ? selectedLineIds.filter((item) => item !== id) : [...selectedLineIds, id];
    setSelectedLineIds(next);
    setSelected(next.includes(id) ? { kind: "line", id } : selectedConnectorIds.length ? { kind: "connector", id: selectedConnectorIds.at(-1)! } : selectedShapeIds.length ? { kind: "shape", id: selectedShapeIds.at(-1)! } : next.length ? { kind: "line", id: next.at(-1)! } : null);
  }

  function onConnectorClick(id: string, additive = false) {
    if (!additive) { setSelected({ kind: "connector", id }); setSelectedShapeIds([]); setSelectedLineIds([]); setSelectedConnectorIds([id]); return; }
    const next = selectedConnectorIds.includes(id) ? selectedConnectorIds.filter((item) => item !== id) : [...selectedConnectorIds, id];
    setSelectedConnectorIds(next);
    setSelected(next.includes(id) ? { kind: "connector", id } : selectedLineIds.length ? { kind: "line", id: selectedLineIds.at(-1)! } : selectedShapeIds.length ? { kind: "shape", id: selectedShapeIds.at(-1)! } : next.length ? { kind: "connector", id: next.at(-1)! } : null);
  }

  function startMarquee(event: { target: Konva.Node }) {
    if (readOnly || lineTool || event.target !== event.target.getStage()) return;
    const point = event.target.getStage()?.getPointerPosition();
    if (!point) return;
    const x = point.x / stageScale; const y = point.y / stageScale;
    setMarquee({ x1: x, y1: y, x2: x, y2: y });
  }

  function updateMarquee(event: { target: Konva.Node }) {
    if (!marquee) return;
    const point = event.target.getStage()?.getPointerPosition();
    if (point) setMarquee((current) => current ? { ...current, x2: point.x / stageScale, y2: point.y / stageScale } : current);
  }

  function finishMarquee() {
    if (!marquee) return;
    const area = { x: Math.min(marquee.x1, marquee.x2), y: Math.min(marquee.y1, marquee.y2), width: Math.abs(marquee.x2 - marquee.x1), height: Math.abs(marquee.y2 - marquee.y1) };
    setMarquee(null);
    if (area.width < 3 && area.height < 3) { setSelected(null); setSelectedShapeIds([]); setSelectedLineIds([]); setSelectedConnectorIds([]); return; }
    const shapes = documentRef.current.shapes.filter((shape) => {
      const points = shapeOutline(shape).map((point) => shapeLocalToWorld(shape, point));
      const xs = points.map(([x]) => x); const ys = points.map(([, y]) => y);
      return rectsIntersect({ x: Math.min(...xs), y: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) }, area);
    });
    const lines = documentRef.current.lines.filter((line) => polylineIntersectsRect(linePoints(line), area));
    const shapesById = new Map(documentRef.current.shapes.map((shape) => [shape.id, shape]));
    const connectors = documentRef.current.connectors.filter((edge) => {
      const source = shapesById.get(edge.source_id); const target = shapesById.get(edge.target_id);
      if (!source || !target) return false;
      const [sx, sy] = boundaryPoint(source, target); const [tx, ty] = boundaryPoint(target, source);
      return polylineIntersectsRect([sx, sy, tx, ty], area);
    });
    const shapeIds = shapes.map((item) => item.id); const lineIds = lines.map((item) => item.id); const connectorIds = connectors.map((item) => item.id);
    setSelectedShapeIds(shapeIds); setSelectedLineIds(lineIds); setSelectedConnectorIds(connectorIds);
    setSelected(shapeIds.length ? { kind: "shape", id: shapeIds.at(-1)! } : lineIds.length ? { kind: "line", id: lineIds.at(-1)! } : connectorIds.length ? { kind: "connector", id: connectorIds.at(-1)! } : null);
  }

  const selectedShape = selected?.kind === "shape" ? document.shapes.find((shape) => shape.id === selected.id) : undefined;
  const editingShape = editingShapeId ? document.shapes.find((shape) => shape.id === editingShapeId) : undefined;
  const selectedConnector = selected?.kind === "connector" ? document.connectors.find((edge) => edge.id === selected.id) : undefined;
  const selectedLine = selected?.kind === "line" ? document.lines.find((line) => line.id === selected.id) : undefined;
  const targetById = new Map(document.shapes.map((shape) => [shape.id, shape]));
  const sceneWidth = viewportWidth * (readOnly ? readOnlyZoom : 1);
  const stageScale = sceneWidth / CANVAS_WIDTH;
  const contentHeight = canvasHeight(document);

  return (
    <div className="flex flex-col gap-2">
      {!readOnly && (
        <>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-muted-foreground">Add shape:</span>
            {(["rectangle", "ellipse", "circle", "triangle", "diamond", "pentagon", "hexagon"] as const).map((kind) => (
              <button key={kind} type="button" onClick={() => addShape(kind)} className="rounded border border-border px-2 py-1 text-xs capitalize hover:bg-muted">
                {kind === "ellipse" ? "Oval" : kind}
              </button>
            ))}
            {([
              ["line", "Line"], ["start-arrow", "Left arrow"], ["end-arrow", "Right arrow"], ["both-arrows", "Both arrows"],
            ] as const).map(([tool, label]) => (
              <button key={tool} type="button" onClick={() => { setLineTool((current) => current === tool ? null : tool); setSelected(null); setSelectedShapeIds([]); setSelectedLineIds([]); setSelectedConnectorIds([]); }} aria-pressed={lineTool === tool} className={`rounded border px-2 py-1 text-xs ${lineTool === tool ? "border-accent bg-accent/10 text-accent" : "border-border hover:bg-muted"}`}>
                {label}
              </button>
            ))}
            <button type="button" onClick={copySelectedShape} disabled={!selected} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Copy{selected && selectedShapeIds.length + selectedLineIds.length + selectedConnectorIds.length > 1 ? ` (${selectedShapeIds.length + selectedLineIds.length + selectedConnectorIds.length})` : ""}</button>
            <button type="button" onClick={pasteShape} disabled={!hasCopiedShape} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Paste</button>
            <button type="button" onClick={undo} disabled={!undoRef.current.length} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Undo</button>
            <button type="button" onClick={redo} disabled={!redoRef.current.length} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Redo</button>
            {selected && <button type="button" onClick={removeSelected} className="ml-auto rounded border border-border px-2 py-1 text-xs text-destructive">Delete selected</button>}
            {selectedShape && <>
              <button type="button" onClick={() => moveSelectedLayer("backward")} disabled={document.shapes[0]?.id === selectedShape.id} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Send backward</button>
              <button type="button" onClick={() => moveSelectedLayer("forward")} disabled={document.shapes.at(-1)?.id === selectedShape.id} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Bring forward</button>
            </>}
          </div>
          {lineTool && <p className="text-xs text-muted-foreground">Drag on the canvas to draw a line. Endpoints snap to nearby shape outlines; drag an endpoint away to detach it.</p>}
          {selectedShape && (
            <div className="flex flex-wrap items-center gap-2 rounded border border-border bg-muted/40 p-2">
              <button type="button" onClick={() => editShapeText(selectedShape)} className="rounded border border-border px-2 py-1 text-xs hover:bg-muted">Edit text</button>
              <label className="flex items-center gap-1 text-xs">Text color <input aria-label="Shape text color" type="color" value={selectedShape.text_color} onChange={(event) => updateShape(selectedShape.id, { text_color: event.target.value })} /></label>
              <label className="flex items-center gap-1 text-xs">Font <select aria-label="Shape font family" value={selectedShape.font_family ?? "Arial, Helvetica, sans-serif"} onChange={(event) => updateShape(selectedShape.id, { font_family: event.target.value })} className="h-7 max-w-36 rounded border border-border bg-background px-1"><option value="Arial, Helvetica, sans-serif">Arial</option><option value="Georgia, serif">Georgia</option><option value="'Times New Roman', Times, serif">Times New Roman</option><option value="Verdana, Geneva, sans-serif">Verdana</option><option value="'Courier New', Courier, monospace">Courier New</option><option value="'Trebuchet MS', sans-serif">Trebuchet MS</option><option value="Impact, sans-serif">Impact</option></select></label>
              <label className="flex items-center gap-1 text-xs">Size <input aria-label="Shape font size" type="number" min={8} max={48} value={selectedShape.font_size} onChange={(event) => updateShape(selectedShape.id, { font_size: Math.max(8, Math.min(48, Number(event.target.value) || 8)) })} className="h-7 w-14 rounded border border-border bg-background px-1" /></label>
              <button type="button" aria-label="Bold shape text" aria-pressed={selectedShape.bold} onClick={() => updateShape(selectedShape.id, { bold: !selectedShape.bold })} className={`rounded border px-2 py-1 text-xs font-bold ${selectedShape.bold ? "border-accent bg-accent/10" : "border-border hover:bg-muted"}`}>B</button>
              <button type="button" aria-label="Italic shape text" aria-pressed={selectedShape.italic} onClick={() => updateShape(selectedShape.id, { italic: !selectedShape.italic })} className={`rounded border px-2 py-1 text-xs italic ${selectedShape.italic ? "border-accent bg-accent/10" : "border-border hover:bg-muted"}`}>I</button>
              <label className="flex items-center gap-1 text-xs">Align <select aria-label="Shape text alignment" value={selectedShape.text_align} onChange={(event) => updateShape(selectedShape.id, { text_align: event.target.value as DiagramShape["text_align"] })} className="h-7 rounded border border-border bg-background px-1"><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></select></label>
              <label className="flex items-center gap-1 text-xs">Vertical <select aria-label="Shape text vertical alignment" value={selectedShape.text_vertical_align} onChange={(event) => updateShape(selectedShape.id, { text_vertical_align: event.target.value as DiagramShape["text_vertical_align"] })} className="h-7 rounded border border-border bg-background px-1"><option value="top">Top</option><option value="middle">Middle</option><option value="bottom">Bottom</option></select></label>
              <label className="flex items-center gap-1 text-xs">Fill <input aria-label="Shape fill color" type="color" value={selectedShape.fill} onChange={(event) => updateShape(selectedShape.id, { fill: event.target.value })} /></label>
              <label className="flex items-center gap-1 text-xs">Outline <input aria-label="Shape outline color" type="color" value={selectedShape.stroke} onChange={(event) => updateShape(selectedShape.id, { stroke: event.target.value })} /></label>
              <label className="flex items-center gap-1 text-xs">Width <input aria-label="Outline width" type="number" min={1} max={10} value={selectedShape.stroke_width} onChange={(event) => updateShape(selectedShape.id, { stroke_width: Math.max(1, Math.min(10, Number(event.target.value) || 1)) })} className="h-7 w-14 rounded border border-border bg-background px-1" /></label>
              <label className="flex items-center gap-1 text-xs">Rotation <input aria-label="Shape rotation" type="number" min={-180} max={180} value={selectedShape.rotation} onChange={(event) => updateShape(selectedShape.id, { rotation: Math.max(-180, Math.min(180, Number(event.target.value) || 0)) })} className="h-7 w-16 rounded border border-border bg-background px-1" /></label>
            </div>
          )}
          {selectedShapeIds.length + selectedLineIds.length + selectedConnectorIds.length > 1 && <p className="text-xs text-muted-foreground">{selectedShapeIds.length + selectedLineIds.length + selectedConnectorIds.length} objects selected. Formatting controls apply to the active object; Copy/Paste and Delete apply to the selection.</p>}
          {selectedConnector && (
            <div className="flex flex-wrap items-center gap-2 rounded border border-border bg-muted/40 p-2">
              <label className="flex items-center gap-1 text-xs">Label <input aria-label="Connector label" className="h-7 w-36 rounded border border-border bg-background px-1" value={selectedConnector.label} onChange={(event) => updateConnector(selectedConnector.id, { label: event.target.value })} maxLength={120} /></label>
              <label className="flex items-center gap-1 text-xs">Line <input aria-label="Connector line color" type="color" value={selectedConnector.color} onChange={(event) => updateConnector(selectedConnector.id, { color: event.target.value })} /></label>
              <label className="flex items-center gap-1 text-xs">Width <input aria-label="Connector width" type="number" min={1} max={10} value={selectedConnector.stroke_width} onChange={(event) => updateConnector(selectedConnector.id, { stroke_width: Math.max(1, Math.min(10, Number(event.target.value) || 1)) })} className="h-7 w-14 rounded border border-border bg-background px-1" /></label>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={selectedConnector.arrow} onChange={(event) => updateConnector(selectedConnector.id, { arrow: event.target.checked })} /> Arrowhead</label>
            </div>
          )}
          {selectedLine && (
            <div className="flex flex-wrap items-center gap-2 rounded border border-border bg-muted/40 p-2">
              <label className="flex items-center gap-1 text-xs">Line <input aria-label="Line color" type="color" value={selectedLine.color} onChange={(event) => updateLine(selectedLine.id, { color: event.target.value })} /></label>
              <label className="flex items-center gap-1 text-xs">Width <input aria-label="Line width" type="number" min={1} max={10} value={selectedLine.stroke_width} onChange={(event) => updateLine(selectedLine.id, { stroke_width: Math.max(1, Math.min(10, Number(event.target.value) || 1)) })} className="h-7 w-14 rounded border border-border bg-background px-1" /></label>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={selectedLine.arrow_start} onChange={(event) => updateLine(selectedLine.id, { arrow_start: event.target.checked })} /> Left arrow</label>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={selectedLine.arrow_end} onChange={(event) => updateLine(selectedLine.id, { arrow_end: event.target.checked })} /> Right arrow</label>
            </div>
          )}
        </>
      )}
      <div ref={viewportRef} className={readOnly ? "w-full overflow-x-auto" : "w-full"}>
      {readOnly && contentHeight > 0 && <div className="mb-1 flex items-center justify-end gap-2" aria-label="Diagram zoom controls">
        <span className="text-xs text-muted-foreground">Zoom {Math.round(readOnlyZoom * 100)}%</span>
        <button type="button" aria-label="Zoom out diagram" title="Zoom out" onClick={() => setReadOnlyZoom((zoom) => Math.max(0.5, Math.round((zoom - 0.25) * 100) / 100))} disabled={readOnlyZoom <= 0.5} className="h-7 w-7 rounded border border-border text-sm disabled:opacity-40">−</button>
        <button type="button" onClick={() => setReadOnlyZoom(1)} className="h-7 rounded border border-border px-2 text-xs">Fit</button>
        <button type="button" aria-label="Zoom in diagram" title="Zoom in" onClick={() => setReadOnlyZoom((zoom) => Math.min(2, Math.round((zoom + 0.25) * 100) / 100))} disabled={readOnlyZoom >= 2} className="h-7 w-7 rounded border border-border text-sm disabled:opacity-40">+</button>
      </div>}
      {contentHeight > 0 || lineTool ? <div
        role="group"
        aria-label={readOnly ? `Diagram with ${document.shapes.length} shapes, ${document.lines.length} lines, and ${document.connectors.length} attached connections` : "Diagram editor canvas"}
        ref={canvasRef}
        className={`relative w-full overflow-hidden rounded-md bg-white ${readOnly ? "" : "border border-border"}`}
        style={{ width: `${(readOnly ? readOnlyZoom : 1) * 100}%`, aspectRatio: `${CANVAS_WIDTH} / ${Math.max(contentHeight, lineTool ? 120 : 1)}` }}
      >
        <Stage
          width={sceneWidth} height={sceneWidth * Math.max(contentHeight, lineTool ? 120 : 1) / CANVAS_WIDTH}
          scaleX={stageScale} scaleY={stageScale}
          style={{ width: "100%", height: "100%" }} listening={!readOnly}
          onMouseDown={(event) => {
            if (lineTool) {
              event.evt.preventDefault();
              const position = event.target.getStage()?.getPointerPosition();
              if (position) beginLineDraw({ x: position.x / stageScale, y: position.y / stageScale });
            } else if (event.target === event.target.getStage()) startMarquee(event);
          }}
          onMouseMove={(event) => { updateLinePreview(event); updateMarquee(event); }}
          onMouseUp={() => { finishLineDraw(); finishMarquee(); }}
          onTouchStart={(event) => {
            if (!lineTool) return;
            event.evt.preventDefault();
            const position = event.target.getStage()?.getPointerPosition();
            if (position) beginLineDraw({ x: position.x / stageScale, y: position.y / stageScale });
          }}
          onTouchMove={updateLinePreview}
          onTouchEnd={finishLineDraw}
        >
          <Layer>
            {!readOnly && Array.from({ length: Math.ceil(CANVAS_WIDTH / 50) + 1 }, (_, index) => <Line key={`v${index}`} points={[index * 50, 0, index * 50, contentHeight]} stroke="#e2e8f0" strokeWidth={0.5} listening={false} />)}
            {!readOnly && Array.from({ length: Math.ceil(contentHeight / 50) + 1 }, (_, index) => <Line key={`h${index}`} points={[0, index * 50, CANVAS_WIDTH, index * 50]} stroke="#e2e8f0" strokeWidth={0.5} listening={false} />)}
            {document.connectors.map((connector) => {
              const source = targetById.get(connector.source_id); const target = targetById.get(connector.target_id);
              if (!source || !target) return null;
              const [sx, sy] = boundaryPoint(source, target); const [tx, ty] = boundaryPoint(target, source);
              const selectedEdge = selectedConnectorIds.includes(connector.id);
              const midpointX = (sx + tx) / 2; const midpointY = (sy + ty) / 2;
              return (
                <Group key={connector.id} onClick={(event) => !readOnly && onConnectorClick(connector.id, (event.evt as MouseEvent).shiftKey)} onTap={(event) => !readOnly && onConnectorClick(connector.id, (event.evt as MouseEvent).shiftKey)}>
                  <Line points={[sx, sy, tx, ty]} stroke="transparent" strokeWidth={22} hitStrokeWidth={22} listening={!readOnly} />
                  <Arrow points={[sx, sy, tx, ty]} stroke={connector.color} fill={connector.color} strokeWidth={connector.stroke_width} pointerLength={10} pointerWidth={10} pointerAtEnding={connector.arrow} hitStrokeWidth={16} />
                  {selectedEdge && <Line points={[sx, sy, tx, ty]} stroke="#2563eb" opacity={0.45} strokeWidth={4} listening={false} />}
                  {connector.label && <Text x={midpointX - 70} y={midpointY - 18} width={140} text={connector.label} align="center" fontSize={14} fill="#334155" listening={false} />}
                </Group>
              );
            })}
            {document.shapes.map((shape) => (
              <Group
                key={shape.id} ref={(node) => { if (node) shapeRefs.current.set(shape.id, node); else shapeRefs.current.delete(shape.id); }}
                x={shape.x + shape.width / 2} y={shape.y + shape.height / 2}
                offsetX={shape.width / 2} offsetY={shape.height / 2} rotation={shape.rotation}
                draggable={!readOnly && !lineTool}
                onClick={(event) => !readOnly && onShapeClick(shape.id, (event.evt as MouseEvent).shiftKey)} onTap={(event) => !readOnly && onShapeClick(shape.id, (event.evt as MouseEvent).shiftKey)}
                onDblClick={() => editShapeText(shape)} onDblTap={() => editShapeText(shape)}
                onDragStart={() => { dragBeforeRef.current = copyDocument(documentRef.current); }}
                onDragMove={(event) => {
                  const before = dragBeforeRef.current ?? documentRef.current;
                  const movingIds = new Set(selectedShapeIds.includes(shape.id) ? selectedShapeIds : [shape.id]);
                  const movingShapes = before.shapes.filter((item) => movingIds.has(item.id));
                  const minX = Math.min(...movingShapes.map((item) => item.x));
                  const maxX = Math.max(...movingShapes.map((item) => item.x + item.width));
                  const minY = Math.min(...movingShapes.map((item) => item.y));
                  const maxY = Math.max(...movingShapes.map((item) => item.y + item.height));
                  const original = before.shapes.find((item) => item.id === shape.id) ?? shape;
                  const desiredX = event.target.x() - (original.x + original.width / 2);
                  const desiredY = event.target.y() - (original.y + original.height / 2);
                  const dx = Math.max(-minX, Math.min(CANVAS_WIDTH - maxX, desiredX));
                  const dy = Math.max(-minY, Math.min(MAX_CANVAS_HEIGHT - maxY, desiredY));
                  const positions = new Map(movingShapes.map((item) => [item.id, { ...item, x: item.x + dx, y: item.y + dy }]));
                  const shapes = documentRef.current.shapes.map((item) => positions.get(item.id) ?? item);
                  const lines = shapes.reduce((current, item) => positions.has(item.id) ? syncAttachedLines(current, item) : current, documentRef.current.lines);
                  for (const moved of movingShapes) {
                    shapeRefs.current.get(moved.id)?.position({ x: moved.x + dx + moved.width / 2, y: moved.y + dy + moved.height / 2 });
                  }
                  event.target.position({ x: original.x + dx + original.width / 2, y: original.y + dy + original.height / 2 });
                  const next = { ...documentRef.current, shapes, lines };
                  setLive(next, false);
                }}
                onDragEnd={() => { if (dragBeforeRef.current) { undoRef.current.push(dragBeforeRef.current); redoRef.current = []; dragBeforeRef.current = null; onChange?.(documentRef.current); } }}
                onTransformEnd={(event) => {
                  const node = event.target; const width = Math.max(40, Math.min(500, shape.width * node.scaleX())); const height = Math.max(40, Math.min(400, shape.height * node.scaleY()));
                  const nextShape = { ...shape, x: node.x() - width / 2, y: node.y() - height / 2, width, height, rotation: node.rotation() };
                  node.scaleX(1); node.scaleY(1); updateShape(shape.id, nextShape);
                }}
              >
                <ShapeDrawing shape={shape} />
                {!shape.text_html && <Text x={10} y={10} width={shape.width - 20} height={shape.height - 20} text={shape.text} align={shape.text_align} verticalAlign={shape.text_vertical_align} fontSize={shape.font_size} fontFamily={shape.font_family} fontStyle={`${shape.bold ? "bold" : ""}${shape.italic ? " italic" : ""}`.trim() || "normal"} lineHeight={1.2} fill={shape.text_color} wrap="word" listening={false} />}
              </Group>
            ))}
            {document.lines.map((line) => {
              const selectLine = (event: { evt: Event }) => { if (!readOnly) onLineClick(line.id, event.evt instanceof MouseEvent && event.evt.shiftKey); };
              const finishMove = (event: { target: Konva.Node }) => {
                const dx = Math.max(-Math.min(line.x1, line.x2), Math.min(CANVAS_WIDTH - Math.max(line.x1, line.x2), event.target.x()));
                const dy = Math.max(-Math.min(line.y1, line.y2), Math.min(MAX_CANVAS_HEIGHT - Math.max(line.y1, line.y2), event.target.y()));
                if (dx || dy) updateLine(line.id, {
                  ...endpointPatch("start", line.x1 + dx, line.y1 + dy),
                  ...endpointPatch("end", line.x2 + dx, line.y2 + dy),
                });
                event.target.position({ x: 0, y: 0 });
              };
              const handleEndpointMove = (which: "start" | "end", event: { target: Konva.Node }) => {
                const x = Math.max(0, Math.min(CANVAS_WIDTH, event.target.x()));
                const y = Math.max(0, Math.min(MAX_CANVAS_HEIGHT, event.target.y()));
                updateLine(line.id, endpointPatch(which, x, y));
                setSnapPreview(null);
              };
              const previewEndpointSnap = (event: { target: Konva.Node }) => {
                const snap = nearestSnapPoint(event.target.x(), event.target.y());
                if (snap) event.target.position({ x: snap.x, y: snap.y });
                setSnapPreview(snap ? { x: snap.x, y: snap.y } : null);
              };
              const commonProps = {
                points: linePoints(line), stroke: line.color,
                strokeWidth: line.stroke_width, hitStrokeWidth: 16, listening: !readOnly,
                draggable: !readOnly && !lineTool, onClick: selectLine, onTap: selectLine,
                onDragEnd: finishMove,
              };
              const isSelected = selectedLineIds.includes(line.id);
              return <Group key={line.id}>
                <Line points={linePoints(line)} stroke="transparent" strokeWidth={24} hitStrokeWidth={24} listening={!readOnly} draggable={!readOnly && !lineTool} onClick={selectLine} onTap={selectLine} onDragEnd={finishMove} />
                {line.arrow_start || line.arrow_end
                  ? <Arrow {...commonProps} fill={line.color} pointerLength={10} pointerWidth={10} pointerAtBeginning={line.arrow_start} pointerAtEnding={line.arrow_end} />
                  : <Line {...commonProps} />}
                {isSelected && !readOnly && <>
                  <Circle x={line.x1} y={line.y1} radius={6} fill="#ffffff" stroke={line.color} strokeWidth={2} draggable={!lineTool} onDragMove={previewEndpointSnap} onDragEnd={(event) => handleEndpointMove("start", event)} />
                  <Circle x={line.x2} y={line.y2} radius={6} fill="#ffffff" stroke={line.color} strokeWidth={2} draggable={!lineTool} onDragMove={previewEndpointSnap} onDragEnd={(event) => handleEndpointMove("end", event)} />
                </>}
              </Group>;
            })}
            {linePreview && lineTool && (() => {
              const orderedPreview = orderLineEndpoints(linePreview);
              const points = linePoints(orderedPreview);
              const arrows = lineTool !== "line";
              return arrows
                ? <Arrow points={points} stroke="#475569" fill="#475569" strokeWidth={2} pointerLength={10} pointerWidth={10} pointerAtBeginning={lineTool === "start-arrow" || lineTool === "both-arrows"} pointerAtEnding={lineTool === "end-arrow" || lineTool === "both-arrows"} listening={false} />
                : <Line points={points} stroke="#475569" strokeWidth={2} listening={false} />;
            })()}
            {!readOnly && snapPreview && <Circle x={snapPreview.x} y={snapPreview.y} radius={8} fill="#ffffff" stroke="#2563eb" strokeWidth={3} listening={false} />}
            {!readOnly && marquee && <Rect x={Math.min(marquee.x1, marquee.x2)} y={Math.min(marquee.y1, marquee.y2)} width={Math.abs(marquee.x2 - marquee.x1)} height={Math.abs(marquee.y2 - marquee.y1)} fill="rgba(37,99,235,0.10)" stroke="#2563eb" strokeWidth={1} dash={[5, 4]} listening={false} />}
            {!readOnly && <Transformer ref={transformerRef} rotateEnabled flipEnabled={false} keepRatio={selectedShape?.kind === "circle"} boundBoxFunc={(oldBox, newBox) => newBox.width < 40 || newBox.height < 40 ? oldBox : newBox} />}
          </Layer>
        </Stage>
        {document.shapes.filter((shape) => shape.text_html).map((shape) => {
          const scale = stageScale;
          return <div key={`rich-${shape.id}`} aria-label={shape.text || "Shape text"} className="pointer-events-none absolute flex overflow-hidden p-1 text-sm" style={{ left: (shape.x + shape.width / 2) * scale, top: (shape.y + shape.height / 2) * scale, width: Math.max(24, (shape.width - 20) * scale), height: Math.max(24, (shape.height - 20) * scale), transform: `translate(-50%, -50%) rotate(${shape.rotation}deg)`, alignItems: shape.text_vertical_align === "top" ? "flex-start" : shape.text_vertical_align === "bottom" ? "flex-end" : "center", justifyContent: shape.text_align === "left" ? "flex-start" : shape.text_align === "right" ? "flex-end" : "center", color: shape.text_color, fontFamily: shape.font_family, fontSize: `${shape.font_size * scale}px`, fontWeight: shape.bold ? "bold" : undefined, fontStyle: shape.italic ? "italic" : undefined, textAlign: shape.text_align, lineHeight: 1.2 }}><div className={`max-w-full ${RICH_TEXT_CONTENT_CLASSES}`} dangerouslySetInnerHTML={{ __html: sanitizeShapeHtml(shape.text_html!) }} /></div>;
        })}
      </div> : !readOnly && <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">Add a shape to start a diagram. The canvas will grow with your drawing.</div>}
      </div>
      {editingShape && createPortal(<div ref={editorPanelRef} role="dialog" aria-label="Edit shape text" className="fixed z-[10000] w-[min(760px,calc(100vw-16px))] rounded-md border border-accent bg-white p-2 shadow-2xl" style={editorPosition}>
        <RichTextEditor key={editingShape.id} defaultValue={editingText} onChange={setEditingText} placeholder="Type inside this shape…" autoFocus />
        <div className="mt-2 flex justify-end gap-2"><button type="button" className="rounded border px-3 py-1 text-sm" onClick={() => { cancelTextEditRef.current = true; setEditingShapeId(null); }}>Cancel</button><button type="button" className="rounded bg-accent px-3 py-1 text-sm text-white" onClick={finishShapeText}>Save text</button></div>
      </div>, globalThis.document.body)}
      <ul className="sr-only" aria-label="Diagram contents">
        {document.shapes.map((shape) => <li key={shape.id}>{shape.kind}: {shape.text || "no text"}</li>)}
        {document.connectors.map((edge) => {
          const source = targetById.get(edge.source_id)?.text || "shape";
          const target = targetById.get(edge.target_id)?.text || "shape";
          return <li key={edge.id}>{source} connects to {target}{edge.label ? `: ${edge.label}` : ""}</li>;
        })}
        {document.lines.map((line) => <li key={line.id}>Line from ({Math.round(line.x1)}, {Math.round(line.y1)}) to ({Math.round(line.x2)}, {Math.round(line.y2)})</li>)}
      </ul>
      {!readOnly && <p className="text-[11px] text-muted-foreground">Drag on empty canvas space to select objects in an area; Shift-click to add or remove individual objects. Copy/Paste duplicates the selection and preserves its layout. Use Ctrl/⌘+Z to undo.</p>}
    </div>
  );
}
