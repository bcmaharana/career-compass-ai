/**
 * The "back to the Core Grid" glyph - a solid 4-square grid, not an
 * outlined one. No Lucide icon matches this (LayoutGrid is stroke-only),
 * and this exact shape needs to stay pixel-consistent with the identical
 * icon used for this same link in the sibling `simple`/`training` repos
 * (2026-09-05) - a hand-rolled SVG here rather than a library icon.
 */
export function CoreGridIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className} aria-hidden="true">
      <rect x="2" y="2" width="7" height="7" rx="1.4" />
      <rect x="11" y="2" width="7" height="7" rx="1.4" />
      <rect x="2" y="11" width="7" height="7" rx="1.4" />
      <rect x="11" y="11" width="7" height="7" rx="1.4" />
    </svg>
  );
}
