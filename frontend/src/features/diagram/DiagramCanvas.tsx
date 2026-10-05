import { useEffect, useRef, useState } from "react";
import { Arrow, Ellipse, Group, Layer, Line, Rect, Shape, Stage, Text, Transformer } from "react-konva";
import type Konva from "konva";
import type { DiagramConnector, DiagramDocument, DiagramDocumentInput, DiagramShape, DiagramShapeKind } from "./diagram-types";

const CANVAS_WIDTH = 900;
const CANVAS_HEIGHT = 500;
type SelectedItem = { kind: "shape" | "connector"; id: string } | null;

function copyDocument(document: DiagramDocument): DiagramDocument {
  return structuredClone(document);
}

function normalizeDocument(document: DiagramDocumentInput): DiagramDocument {
  return {
    version: 1,
    shapes: structuredClone(document.shapes ?? []).map((shape) => ({
      ...shape,
      font_size: shape.font_size ?? 16,
      text_color: shape.text_color ?? "#0f172a",
      bold: shape.bold ?? false,
      italic: shape.italic ?? false,
      text_align: shape.text_align ?? "center",
      text_vertical_align: shape.text_vertical_align ?? "middle",
    })),
    connectors: structuredClone(document.connectors ?? []),
  };
}

function makeShape(kind: DiagramShapeKind, index: number): DiagramShape {
  const sizes: Record<DiagramShapeKind, [number, number]> = {
    rectangle: [180, 88], ellipse: [150, 92], triangle: [130, 112], diamond: [140, 110],
  };
  const [width, height] = sizes[kind];
  const offset = Math.min(index, 5) * 18;
  return {
    id: crypto.randomUUID(), kind, x: Math.max(0, (CANVAS_WIDTH - width) / 2 + offset), y: Math.max(0, (CANVAS_HEIGHT - height) / 2 + offset),
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
  if (shape.kind === "ellipse") {
    distance = 1 / Math.sqrt((dx * dx) / (hw * hw) + (dy * dy) / (hh * hh));
  } else if (shape.kind === "diamond") {
    distance = 1 / (Math.abs(dx) / hw + Math.abs(dy) / hh);
  } else if (shape.kind === "triangle") {
    const vertices: [number, number][] = [[0, -hh], [hw, hh], [-hw, hh]];
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
  if (shape.kind === "ellipse") return <Ellipse x={shape.width / 2} y={shape.height / 2} radiusX={shape.width / 2} radiusY={shape.height / 2} {...common} />;
  return (
    <Shape
      width={shape.width}
      height={shape.height}
      {...common}
      sceneFunc={(context, canvasShape) => {
        context.beginPath();
        if (shape.kind === "triangle") {
          context.moveTo(shape.width / 2, 2); context.lineTo(shape.width - 2, shape.height - 2); context.lineTo(2, shape.height - 2);
        } else {
          context.moveTo(shape.width / 2, 2); context.lineTo(shape.width - 2, shape.height / 2);
          context.lineTo(shape.width / 2, shape.height - 2); context.lineTo(2, shape.height / 2);
        }
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
  const initial = value ?? { version: 1 as const, shapes: [], connectors: [] };
  const [document, setDocument] = useState<DiagramDocument>(() => normalizeDocument(initial));
  const incomingDocument = normalizeDocument(initial);
  const incomingSignature = JSON.stringify(incomingDocument);
  const [selected, setSelected] = useState<SelectedItem>(null);
  const [connectMode, setConnectMode] = useState(false);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [viewportWidth, setViewportWidth] = useState(CANVAS_WIDTH);
  const [editingShapeId, setEditingShapeId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  const canvasRef = useRef<HTMLDivElement>(null);
  const textEditorRef = useRef<HTMLTextAreaElement>(null);
  const cancelTextEditRef = useRef(false);
  const transformerRef = useRef<Konva.Transformer>(null);
  const shapeRefs = useRef(new Map<string, Konva.Group>());
  const documentRef = useRef(document);
  const dragBeforeRef = useRef<DiagramDocument | null>(null);
  const undoRef = useRef<DiagramDocument[]>([]);
  const redoRef = useRef<DiagramDocument[]>([]);
  const lastIncomingSignatureRef = useRef(incomingSignature);

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
    undoRef.current = [];
    redoRef.current = [];
  }, [incomingDocument, incomingSignature]);

  useEffect(() => {
    const element = canvasRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setViewportWidth(Math.max(1, Math.min(CANVAS_WIDTH, entry.contentRect.width)));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (editingShapeId) textEditorRef.current?.focus();
  }, [editingShapeId]);

  useEffect(() => {
    const transformer = transformerRef.current;
    if (!transformer) return;
    const target = selected?.kind === "shape" ? shapeRefs.current.get(selected.id) : undefined;
    transformer.nodes(target ? [target] : []);
    transformer.getLayer()?.batchDraw();
  }, [selected, document.shapes]);

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
    setConnectMode(false); setConnectFrom(null);
  }

  function editShapeText(shape: DiagramShape) {
    if (readOnly || connectMode) return;
    setEditingText(shape.text);
    setEditingShapeId(shape.id);
  }

  function finishShapeText() {
    const id = editingShapeId;
    if (id && !cancelTextEditRef.current) updateShape(id, { text: editingText });
    cancelTextEditRef.current = false;
    setEditingShapeId(null);
  }

  function updateShape(id: string, patch: Partial<DiagramShape>) {
    const next = { ...documentRef.current, shapes: documentRef.current.shapes.map((shape) => shape.id === id ? { ...shape, ...patch } : shape) };
    commit(next);
  }

  function updateConnector(id: string, patch: Partial<DiagramConnector>) {
    const next = { ...documentRef.current, connectors: documentRef.current.connectors.map((edge) => edge.id === id ? { ...edge, ...patch } : edge) };
    commit(next);
  }

  function removeSelected() {
    if (!selected) return;
    if (selected.kind === "shape") {
      commit({
        ...documentRef.current,
        shapes: documentRef.current.shapes.filter((shape) => shape.id !== selected.id),
        connectors: documentRef.current.connectors.filter((edge) => edge.source_id !== selected.id && edge.target_id !== selected.id),
      });
    } else {
      commit({ ...documentRef.current, connectors: documentRef.current.connectors.filter((edge) => edge.id !== selected.id) });
    }
    setSelected(null);
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
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault(); event.shiftKey ? redo() : undo();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
        event.preventDefault(); redo();
      } else if ((event.key === "Delete" || event.key === "Backspace") && selected) {
        event.preventDefault(); removeSelected();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // The handlers read the latest document through refs; `selected` is
    // the only state captured by the listener and is included below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readOnly, selected]);

  function onShapeClick(id: string) {
    if (connectMode) {
      if (!connectFrom) { setConnectFrom(id); return; }
      if (connectFrom === id) { setConnectFrom(null); return; }
      commit({
        ...documentRef.current,
        connectors: [...documentRef.current.connectors, {
          id: crypto.randomUUID(), source_id: connectFrom, target_id: id,
          color: "#475569", stroke_width: 2, arrow: true, label: "",
        }],
      });
      setConnectFrom(null); setConnectMode(false); setSelected(null); return;
    }
    setSelected({ kind: "shape", id });
  }

  const selectedShape = selected?.kind === "shape" ? document.shapes.find((shape) => shape.id === selected.id) : undefined;
  const selectedConnector = selected?.kind === "connector" ? document.connectors.find((edge) => edge.id === selected.id) : undefined;
  const targetById = new Map(document.shapes.map((shape) => [shape.id, shape]));

  return (
    <div className="flex flex-col gap-2">
      {!readOnly && (
        <>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-muted-foreground">Add shape:</span>
            {(["rectangle", "ellipse", "triangle", "diamond"] as const).map((kind) => (
              <button key={kind} type="button" onClick={() => addShape(kind)} className="rounded border border-border px-2 py-1 text-xs capitalize hover:bg-muted">
                {kind === "ellipse" ? "Oval" : kind}
              </button>
            ))}
            <button type="button" onClick={() => { setConnectMode((mode) => !mode); setConnectFrom(null); setSelected(null); }} className={`rounded border px-2 py-1 text-xs ${connectMode ? "border-accent bg-accent/10 text-accent" : "border-border hover:bg-muted"}`}>
              {connectMode ? (connectFrom ? "Choose target…" : "Choose source…") : "Connect shapes"}
            </button>
            <button type="button" onClick={undo} disabled={!undoRef.current.length} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Undo</button>
            <button type="button" onClick={redo} disabled={!redoRef.current.length} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Redo</button>
            {selected && <button type="button" onClick={removeSelected} className="ml-auto rounded border border-border px-2 py-1 text-xs text-destructive">Delete selected</button>}
            {selectedShape && <>
              <button type="button" onClick={() => moveSelectedLayer("backward")} disabled={document.shapes[0]?.id === selectedShape.id} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Send backward</button>
              <button type="button" onClick={() => moveSelectedLayer("forward")} disabled={document.shapes.at(-1)?.id === selectedShape.id} className="rounded border border-border px-2 py-1 text-xs disabled:opacity-40">Bring forward</button>
            </>}
          </div>
          {connectMode && <p className="text-xs text-muted-foreground">Click a source shape, then a target shape. The arrow stays attached when either shape moves.</p>}
          {selectedShape && (
            <div className="flex flex-wrap items-center gap-2 rounded border border-border bg-muted/40 p-2">
              <button type="button" onClick={() => editShapeText(selectedShape)} className="rounded border border-border px-2 py-1 text-xs hover:bg-muted">Edit text</button>
              <label className="flex items-center gap-1 text-xs">Text color <input aria-label="Shape text color" type="color" value={selectedShape.text_color} onChange={(event) => updateShape(selectedShape.id, { text_color: event.target.value })} /></label>
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
          {selectedConnector && (
            <div className="flex flex-wrap items-center gap-2 rounded border border-border bg-muted/40 p-2">
              <label className="flex items-center gap-1 text-xs">Label <input aria-label="Connector label" className="h-7 w-36 rounded border border-border bg-background px-1" value={selectedConnector.label} onChange={(event) => updateConnector(selectedConnector.id, { label: event.target.value })} maxLength={120} /></label>
              <label className="flex items-center gap-1 text-xs">Line <input aria-label="Connector line color" type="color" value={selectedConnector.color} onChange={(event) => updateConnector(selectedConnector.id, { color: event.target.value })} /></label>
              <label className="flex items-center gap-1 text-xs">Width <input aria-label="Connector width" type="number" min={1} max={10} value={selectedConnector.stroke_width} onChange={(event) => updateConnector(selectedConnector.id, { stroke_width: Math.max(1, Math.min(10, Number(event.target.value) || 1)) })} className="h-7 w-14 rounded border border-border bg-background px-1" /></label>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={selectedConnector.arrow} onChange={(event) => updateConnector(selectedConnector.id, { arrow: event.target.checked })} /> Arrowhead</label>
            </div>
          )}
        </>
      )}
      <div
        role="group"
        aria-label={readOnly ? `Diagram with ${document.shapes.length} shapes and ${document.connectors.length} connections` : "Diagram editor canvas"}
        ref={canvasRef}
        className="relative w-full overflow-hidden rounded-md border border-border bg-white"
        style={{ aspectRatio: `${CANVAS_WIDTH} / ${CANVAS_HEIGHT}` }}
      >
        <Stage
          width={viewportWidth} height={viewportWidth * CANVAS_HEIGHT / CANVAS_WIDTH}
          scaleX={viewportWidth / CANVAS_WIDTH} scaleY={viewportWidth / CANVAS_WIDTH}
          style={{ width: "100%", height: "100%" }} listening={!readOnly}
          onMouseDown={(event) => { if (event.target === event.target.getStage() && !connectMode) setSelected(null); }}
        >
          <Layer>
            {!readOnly && Array.from({ length: 19 }, (_, index) => <Line key={`v${index}`} points={[index * 50, 0, index * 50, CANVAS_HEIGHT]} stroke="#e2e8f0" strokeWidth={0.5} listening={false} />)}
            {!readOnly && Array.from({ length: 11 }, (_, index) => <Line key={`h${index}`} points={[0, index * 50, CANVAS_WIDTH, index * 50]} stroke="#e2e8f0" strokeWidth={0.5} listening={false} />)}
            {document.connectors.map((connector) => {
              const source = targetById.get(connector.source_id); const target = targetById.get(connector.target_id);
              if (!source || !target) return null;
              const [sx, sy] = boundaryPoint(source, target); const [tx, ty] = boundaryPoint(target, source);
              const selectedEdge = selected?.kind === "connector" && selected.id === connector.id;
              const midpointX = (sx + tx) / 2; const midpointY = (sy + ty) / 2;
              return (
                <Group key={connector.id} onClick={() => !readOnly && setSelected({ kind: "connector", id: connector.id })} onTap={() => !readOnly && setSelected({ kind: "connector", id: connector.id })}>
                  <Arrow points={[sx, sy, tx, ty]} stroke={connector.color} fill={connector.color} strokeWidth={connector.stroke_width} pointerLength={10} pointerWidth={10} pointerAtEnding={connector.arrow} hitStrokeWidth={16} />
                  {selectedEdge && <Line points={[sx, sy, tx, ty]} stroke="transparent" strokeWidth={16} />}
                  {connector.label && <Text x={midpointX - 70} y={midpointY - 18} width={140} text={connector.label} align="center" fontSize={14} fill="#334155" listening={false} />}
                </Group>
              );
            })}
            {document.shapes.map((shape) => (
              <Group
                key={shape.id} ref={(node) => { if (node) shapeRefs.current.set(shape.id, node); else shapeRefs.current.delete(shape.id); }}
                x={shape.x + shape.width / 2} y={shape.y + shape.height / 2}
                offsetX={shape.width / 2} offsetY={shape.height / 2} rotation={shape.rotation}
                draggable={!readOnly && !connectMode}
                onClick={() => !readOnly && onShapeClick(shape.id)} onTap={() => !readOnly && onShapeClick(shape.id)}
                onDblClick={() => editShapeText(shape)} onDblTap={() => editShapeText(shape)}
                onDragStart={() => { dragBeforeRef.current = copyDocument(documentRef.current); }}
                onDragMove={(event) => {
                  const next = { ...documentRef.current, shapes: documentRef.current.shapes.map((item) => item.id === shape.id ? { ...item, x: event.target.x() - item.width / 2, y: event.target.y() - item.height / 2 } : item) };
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
            <Text x={10} y={10} width={shape.width - 20} height={shape.height - 20} text={shape.text} align={shape.text_align} verticalAlign={shape.text_vertical_align} fontSize={shape.font_size} fontStyle={`${shape.bold ? "bold" : ""}${shape.italic ? " italic" : ""}`.trim() || "normal"} lineHeight={1.2} fill={shape.text_color} wrap="word" listening={false} />
              </Group>
            ))}
            {!readOnly && <Transformer ref={transformerRef} rotateEnabled flipEnabled={false} keepRatio={false} boundBoxFunc={(oldBox, newBox) => newBox.width < 40 || newBox.height < 40 ? oldBox : newBox} />}
          </Layer>
        </Stage>
        {editingShapeId && (() => {
          const shape = document.shapes.find((item) => item.id === editingShapeId);
          if (!shape) return null;
          const scale = viewportWidth / CANVAS_WIDTH;
          return <textarea
            ref={textEditorRef}
            aria-label="Edit shape text"
            value={editingText}
            maxLength={180}
            onChange={(event) => setEditingText(event.target.value)}
            onBlur={finishShapeText}
            onKeyDown={(event) => {
              if (event.key === "Escape") { cancelTextEditRef.current = true; textEditorRef.current?.blur(); }
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) textEditorRef.current?.blur();
            }}
            className="absolute z-10 resize-none overflow-auto border border-accent bg-white/95 p-1 text-center text-sm text-slate-900 outline-none"
            style={{ left: (shape.x + shape.width / 2) * scale, top: (shape.y + shape.height / 2) * scale, width: Math.max(40, (shape.width - 20) * scale), height: Math.max(32, (shape.height - 20) * scale), transform: `translate(-50%, -50%) rotate(${shape.rotation}deg)`, color: shape.text_color, fontSize: `${shape.font_size * scale}px`, fontWeight: shape.bold ? "bold" : "normal", fontStyle: shape.italic ? "italic" : "normal", textAlign: shape.text_align }}
          />;
        })()}
      </div>
      <ul className="sr-only" aria-label="Diagram contents">
        {document.shapes.map((shape) => <li key={shape.id}>{shape.kind}: {shape.text || "no text"}</li>)}
        {document.connectors.map((edge) => {
          const source = targetById.get(edge.source_id)?.text || "shape";
          const target = targetById.get(edge.target_id)?.text || "shape";
          return <li key={edge.id}>{source} connects to {target}{edge.label ? `: ${edge.label}` : ""}</li>;
        })}
      </ul>
      {!readOnly && <p className="text-[11px] text-muted-foreground">Drag shapes to move; select one to resize, style, or rotate it. Use Ctrl/⌘+Z to undo.</p>}
    </div>
  );
}
