import { useGenerateResume } from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { formatDisplayDateTime } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { FileDown } from "lucide-react";
import { useState } from "react";

type CareerProfileResponse = components["schemas"]["CareerProfileResponse"];
type ResumeFormat = "docx" | "pdf";

/**
 * Generate-and-download + "here's the one already on this profile"
 * link, both driven by the same POST /career-profile/resume-export —
 * generating always downloads immediately (opens the fresh presigned
 * URL in a new tab) and persists to the profile in the same call, so
 * there's no separate "now save it" step. Regenerating a format
 * replaces the previous file for that format, same as the profile
 * photo — this bar always shows only the current one, never a history.
 */
export function ResumeDownloadBar({
  profile,
  scope,
}: {
  profile: CareerProfileResponse;
  scope: string | null;
}) {
  const generateResume = useGenerateResume(scope);
  const [pendingFormat, setPendingFormat] = useState<ResumeFormat | null>(null);

  function handleDownload(format: ResumeFormat) {
    setPendingFormat(format);
    generateResume.mutate(
      { format },
      {
        onSuccess: (data) => {
          const url = format === "docx" ? data.resume_docx_url : data.resume_pdf_url;
          if (url) window.open(url, "_blank", "noopener,noreferrer");
        },
        onSettled: () => setPendingFormat(null),
      },
    );
  }

  const hasExisting = Boolean(profile.resume_docx_url || profile.resume_pdf_url);
  const generatedAt = formatDisplayDateTime(profile.resume_generated_at);

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
      <div className="flex items-center gap-2">
        <FileDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="text-muted-foreground">Download resume:</span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleDownload("docx")}
          disabled={generateResume.isPending}
        >
          {pendingFormat === "docx" && generateResume.isPending ? "Generating..." : "Word (.docx)"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleDownload("pdf")}
          disabled={generateResume.isPending}
        >
          {pendingFormat === "pdf" && generateResume.isPending ? "Generating..." : "PDF"}
        </Button>
      </div>

      {hasExisting && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Saved to this profile:</span>
          {profile.resume_docx_url && (
            <a
              href={profile.resume_docx_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-accent underline underline-offset-2 hover:text-accent/80"
            >
              View Word
            </a>
          )}
          {profile.resume_pdf_url && (
            <a
              href={profile.resume_pdf_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-accent underline underline-offset-2 hover:text-accent/80"
            >
              View PDF
            </a>
          )}
          {generatedAt && <span>· generated {generatedAt}</span>}
        </div>
      )}

      {generateResume.isError && (
        <p role="alert" className="w-full text-xs text-destructive">
          {getErrorMessage(generateResume.error)}
        </p>
      )}
    </div>
  );
}
