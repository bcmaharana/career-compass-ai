import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

export function ExpandableImage({
  src,
  alt,
  className,
}: {
  src: string;
  alt: string;
  className: string;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    if (!isExpanded) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setIsExpanded(false);
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isExpanded]);

  return (
    <>
      <button
        type="button"
        aria-label={`Expand image: ${alt}`}
        onClick={() => setIsExpanded(true)}
        className="block w-full cursor-zoom-in border-0 bg-transparent p-0 text-left"
      >
        <img src={src} alt={alt} className={className} />
      </button>
      {isExpanded &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label={alt || "Expanded image"}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
            onClick={() => setIsExpanded(false)}
          >
            <button
              type="button"
              aria-label="Close full screen image"
              onClick={() => setIsExpanded(false)}
              className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-2xl text-white transition hover:bg-white/20"
            >
              &times;
            </button>
            <img
              src={src}
              alt={alt}
              className="max-h-full max-w-full cursor-zoom-out rounded-lg object-contain"
            />
          </div>,
          document.body,
        )}
    </>
  );
}
