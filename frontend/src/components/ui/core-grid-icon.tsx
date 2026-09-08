/**
 * The "back to the Core Grid" glyph - a solid 4-square grid, not an
 * outlined one. No Lucide icon matches this (LayoutGrid is stroke-only),
 * and this exact shape needs to stay pixel-consistent with the identical
 * icon used for this same link in the sibling `simple`/`training` repos
 * (2026-09-05) - a hand-rolled SVG here rather than a library icon.
 *
 * Fixed per-square colors (2026-09-08), not currentColor: matches the
 * platform's own favicon.svg/Brand.tsx exactly (same 4 colors, same
 * corners) - this glyph is meant to read as "the actual Core Grid icon,"
 * not a monochrome placeholder that happens to be the same shape. `color`
 * on the wrapping link (see DesktopShell.tsx's usage) no longer affects
 * this icon at all as a result - only its hover background does.
 */
export function CoreGridIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
      <rect x="2" y="2" width="7" height="7" rx="1.4" fill="#a855f7" />
      <rect x="11" y="2" width="7" height="7" rx="1.4" fill="#3b82f6" />
      <rect x="2" y="11" width="7" height="7" rx="1.4" fill="#22c55e" />
      <rect x="11" y="11" width="7" height="7" rx="1.4" fill="#fdba74" />
    </svg>
  );
}
