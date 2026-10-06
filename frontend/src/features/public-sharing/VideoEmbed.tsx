import { ExternalLink } from "lucide-react";

function videoEmbedUrl(value: string): string | null {
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    return null;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  url.protocol = "https:";

  const host = url.hostname.toLowerCase().replace(/^www\./, "");
  const isYouTube = ["youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "youtube-nocookie.com"].includes(host);
  if (isYouTube) {
    const parts = url.pathname.split("/").filter(Boolean);
    let id = "";
    if (host === "youtu.be") id = parts[0] ?? "";
    else if (url.pathname === "/watch") id = url.searchParams.get("v") ?? "";
    else if (["embed", "shorts", "live", "v"].includes(parts[0] ?? "")) id = parts[1] ?? "";
    if (!/^[\w-]{6,}$/.test(id)) return null;

    const embed = new URL(`https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}`);
    const start = url.searchParams.get("start") ?? url.searchParams.get("t");
    if (start) {
      const seconds = /^\d+$/.test(start) ? Number(start) : start.match(/(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?/);
      const startSeconds = typeof seconds === "number"
        ? seconds
        : seconds && seconds[0]
          ? Number(seconds[1] ?? 0) * 3600 + Number(seconds[2] ?? 0) * 60 + Number(seconds[3] ?? 0)
          : 0;
      if (startSeconds > 0) embed.searchParams.set("start", String(startSeconds));
    }
    return embed.toString();
  }

  if (host === "vimeo.com" || host === "player.vimeo.com") {
    const parts = url.pathname.split("/").filter(Boolean);
    const id = (host === "player.vimeo.com" ? (parts[0] === "video" ? parts[1] : "") : parts.at(-1)) ?? "";
    if (!/^\d+$/.test(id)) return null;
    const embed = new URL(`https://player.vimeo.com/video/${id}`);
    const privacyHash = url.searchParams.get("h");
    if (privacyHash) embed.searchParams.set("h", privacyHash);
    return embed.toString();
  }

  // Keep supporting other providers when users paste their provider's
  // ready-to-embed HTTPS URL. Plain page links for unknown providers
  // should use an External Link block instead.
  return url.toString();
}

export function VideoEmbed({ url, title }: { url: string; title: string }) {
  const src = videoEmbedUrl(url);
  let safeLink: string | null = null;
  try {
    const parsed = new URL(url.trim());
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      parsed.protocol = "https:";
      safeLink = parsed.toString();
    }
  } catch {
    // Invalid or unsafe URLs are rendered as plain text below.
  }
  if (!src) {
    if (!safeLink) return <p className="text-sm text-muted-foreground">This video link is invalid.</p>;
    return (
      <a href={safeLink} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-accent underline underline-offset-2">
        <ExternalLink className="h-3.5 w-3.5" /> Open video
      </a>
    );
  }
  return (
    <div className="aspect-video w-full overflow-hidden rounded-md border border-border">
      <iframe
        src={src}
        title={title}
        className="h-full w-full"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
        referrerPolicy="strict-origin-when-cross-origin"
      />
    </div>
  );
}
