import type { ReactNode } from "react";

/** Splits on a literal `<br>`/`<br/>`/`<br />` tag first (LLMs commonly
 * emit these inside a table cell to force a line break within one
 * logical cell) before applying bold/italic — each segment between
 * breaks gets its own emphasis pass, joined by real `<br />` elements
 * rather than the literal tag text. Matches bold (** or __ delimited)
 * before italic (single * or _ delimited) at the same position within
 * a segment — JS regex alternation tries branches left-to-right at
 * each index, so ordering the double-marker forms first is what keeps
 * a bold span from being consumed by the single-marker italic branch
 * instead. */
function renderInline(text: string): ReactNode[] {
  const inlineRe = /\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*|_(.+?)_/g;
  const nodes: ReactNode[] = [];
  let key = 0;

  const segments = text.split(/<br\s*\/?>/i);
  segments.forEach((segment, segmentIndex) => {
    if (segmentIndex > 0) {
      nodes.push(<br key={`br-${key++}`} />);
    }
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    inlineRe.lastIndex = 0;
    while ((match = inlineRe.exec(segment)) !== null) {
      if (match.index > lastIndex) {
        nodes.push(segment.slice(lastIndex, match.index));
      }
      const bold = match[1] ?? match[2];
      const italic = match[3] ?? match[4];
      if (bold !== undefined) {
        nodes.push(<strong key={key++}>{bold}</strong>);
      } else if (italic !== undefined) {
        nodes.push(<em key={key++}>{italic}</em>);
      }
      lastIndex = inlineRe.lastIndex;
    }
    if (lastIndex < segment.length) {
      nodes.push(segment.slice(lastIndex));
    }
  });
  return nodes;
}

/** A table row is any line containing at least one `|` — confirmed as a
 * real table only once the very next line is a valid separator row (see
 * isTableSeparatorRow), so an unrelated line that happens to contain a
 * pipe for some other reason never gets misread as a table header on
 * its own. */
function isTableRowLike(line: string): boolean {
  return line.includes("|");
}

function splitTableRow(line: string): string[] {
  const withoutEdgePipes = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return withoutEdgePipes.split("|").map((cell) => cell.trim());
}

/** Every cell in a genuine markdown table separator row is just dashes
 * with optional leading/trailing colons (alignment markers) — e.g.
 * `|---|:--|--:|`. */
function isTableSeparatorRow(line: string): boolean {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-+:?$/.test(cell));
}

interface TextLine {
  text: string;
  heading: boolean;
}
type Block =
  | { kind: "bullet" | "para"; lines: TextLine[] }
  | { kind: "table"; header: string[]; rows: string[][] };

/**
 * Renders a small, LLM-output-shaped subset of Markdown as real React
 * elements — never `dangerouslySetInnerHTML`, so this is safe by
 * construction regardless of what the model's raw text contains (any
 * literal `<`/`>` in the source that isn't specifically the `<br>`
 * pattern handled by renderInline is just plain text passed to a React
 * child, which JSX always escapes on render).
 *
 * Added 2026-08-21 — AI chat replies (footer composer, AI Career Coach,
 * JD Tailoring) were rendered as a flat `whitespace-pre-wrap` text dump,
 * so a reply using markdown (as LLMs commonly do — "**Skills:**\n- SQL\n-
 * Python") showed the literal asterisks/dashes instead of real
 * formatting. Supports: `**bold**`/`__bold__`, `*italic*`/`_italic_`,
 * "- "/"* "/"+ " bullet lines, "1. " numbered lines (kept as literal
 * "1. text" inside a bullet — no ordered-list tag, just enough to not
 * lose the number), "#" through "######" headers (rendered bold, no
 * distinct heading size), blank-line-agnostic paragraphs (each
 * non-empty line is its own paragraph unless it's part of a bullet
 * run), and GitHub-flavored-Markdown pipe tables (added same day, after
 * a real reply used one — a header row, a `|---|---|` separator row,
 * then 0+ data rows, rendered as a real scrollable `<table>` rather
 * than showing literal pipes/dashes; cells commonly carry an embedded
 * `<br>` for a line break within the cell, handled by renderInline
 * above). Not a general-purpose Markdown parser — no links, nested
 * emphasis, or code blocks — just enough of what typical LLM chat
 * replies actually use.
 */
export function renderMarkdownMessage(text: string): ReactNode {
  const rawLines = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const blocks: Block[] = [];
  let i = 0;
  while (i < rawLines.length) {
    const line = rawLines[i]!;

    if (isTableRowLike(line) && i + 1 < rawLines.length && isTableSeparatorRow(rawLines[i + 1]!)) {
      const header = splitTableRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < rawLines.length && isTableRowLike(rawLines[i]!)) {
        rows.push(splitTableRow(rawLines[i]!));
        i += 1;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }

    const headerMatch = /^#{1,6}\s+(.*)$/.exec(line);
    const bulletMatch = /^[-*+]\s+(.*)$/.exec(line);
    const numberedMatch = /^(\d+\.\s+.*)$/.exec(line);

    let kind: "bullet" | "para";
    let lineText: string;
    let heading = false;
    if (headerMatch) {
      kind = "para";
      lineText = headerMatch[1] ?? "";
      heading = true;
    } else if (bulletMatch) {
      kind = "bullet";
      lineText = bulletMatch[1] ?? "";
    } else if (numberedMatch) {
      kind = "bullet";
      lineText = numberedMatch[1] ?? "";
    } else {
      kind = "para";
      lineText = line;
    }

    const last = blocks[blocks.length - 1];
    if (last && last.kind === kind) {
      last.lines.push({ text: lineText, heading });
    } else {
      blocks.push({ kind, lines: [{ text: lineText, heading }] });
    }
    i += 1;
  }

  return (
    <div className="flex flex-col gap-1.5">
      {blocks.map((block, blockIndex) => {
        if (block.kind === "table") {
          return (
            <div key={blockIndex} className="overflow-x-auto">
              <table className="min-w-full border-collapse text-left text-sm">
                <thead>
                  <tr>
                    {block.header.map((cell, cellIndex) => (
                      <th
                        key={cellIndex}
                        className="border-b border-border px-2 py-1 align-bottom font-semibold"
                      >
                        {renderInline(cell)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td
                          key={cellIndex}
                          className="border-b border-border/50 px-2 py-1 align-top"
                        >
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        if (block.kind === "bullet") {
          return (
            <ul key={blockIndex} className="ml-4 list-disc">
              {block.lines.map((line, lineIndex) => (
                <li key={lineIndex}>{renderInline(line.text)}</li>
              ))}
            </ul>
          );
        }

        return (
          <div key={blockIndex} className="flex flex-col gap-1.5">
            {block.lines.map((line, lineIndex) => (
              <p key={lineIndex}>
                {line.heading ? <strong>{renderInline(line.text)}</strong> : renderInline(line.text)}
              </p>
            ))}
          </div>
        );
      })}
    </div>
  );
}
