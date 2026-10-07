import { RichTextDisplay as SharedRichTextDisplay } from "@bcmaharana/ui-kit";
import { linkifyPlainUrls } from "@/lib/linkify-plain-urls";

/** App wrapper ensuring bare URLs linkify even when running against an
 * older published ui-kit package. The shared component still handles
 * styling and explicit links. */
export function RichTextDisplay({ html, className }: { html: string; className?: string }) {
  return <SharedRichTextDisplay html={linkifyPlainUrls(html)} className={className} />;
}
