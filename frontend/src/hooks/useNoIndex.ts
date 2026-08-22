import { useEffect } from "react";

/**
 * Adds `<meta name="robots" content="noindex">` for the lifetime of the
 * mounted component — used by the anonymous public-sharing pages
 * (PublicShowcasePage/PublicArticlePage), which are reachable content
 * but not meant to be search-indexed. Removed on unmount rather than
 * left permanently, since this is a client-side-routed SPA and the tag
 * would otherwise linger onto whatever page the visitor navigates to
 * next.
 */
export function useNoIndex() {
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    document.head.appendChild(meta);
    return () => {
      document.head.removeChild(meta);
    };
  }, []);
}
