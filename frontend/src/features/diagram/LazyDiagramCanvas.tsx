import { lazy, Suspense } from "react";
import type { DiagramDocument, DiagramDocumentInput } from "./diagram-types";

const DiagramCanvasImpl = lazy(() => import("./DiagramCanvas").then((module) => ({ default: module.DiagramCanvas })));

export function DiagramCanvas({
  value,
  onChange,
  readOnly,
}: {
  value: DiagramDocumentInput | null | undefined;
  onChange?: (document: DiagramDocument) => void;
  readOnly?: boolean;
}) {
  return (
    <Suspense fallback={<div className="flex min-h-40 items-center justify-center rounded-md border border-border bg-muted/30 text-sm text-muted-foreground">Loading diagram…</div>}>
      <DiagramCanvasImpl value={value} onChange={onChange} readOnly={readOnly} />
    </Suspense>
  );
}
