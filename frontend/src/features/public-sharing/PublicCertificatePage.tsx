import { ApiError } from "@/api/client";
import { usePublicCertificate } from "@/api/queries/certificates";
import { Card, CardContent } from "@/components/ui/card";
import { ExpandableImage } from "@/features/public-sharing/ExpandableImage";
import { PublicPageHeader } from "@/features/public-sharing/PublicPageHeader";
import { useNoIndex } from "@/hooks/useNoIndex";
import { formatDisplayDate } from "@/lib/date-format";
import { ExternalLink } from "lucide-react";
import { useParams } from "react-router-dom";

export function PublicCertificatePage() {
  useNoIndex();
  const { shareKey } = useParams<{ shareKey: string }>();
  const { data: certificate, isLoading, isError, error } = usePublicCertificate(shareKey);

  return (
    <div className="min-h-screen bg-[hsl(218,25%,93%)]">
      <PublicPageHeader>
        {certificate && (
          <span className="font-display text-lg font-semibold text-primary-foreground">
            Below certificate is issued to {certificate.owner_display_name}
          </span>
        )}
      </PublicPageHeader>
      <main className="mx-auto w-full max-w-4xl px-3 py-6 sm:px-6 md:py-10">
        {isLoading && <p className="text-sm text-muted-foreground">Loading certificate...</p>}
        {isError && (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-sm text-muted-foreground">
                {error instanceof ApiError && error.status === 404
                  ? "This certificate doesn't exist or is no longer public."
                  : "Something went wrong loading this certificate."}
              </p>
            </CardContent>
          </Card>
        )}
        {certificate && (
          <article className="flex flex-col gap-4">
            <Card>
              <CardContent className="flex flex-col gap-3 py-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Certificate
                </p>
                <h1 className="font-display text-2xl font-semibold">{certificate.name}</h1>
                {certificate.issuing_organization.trim().toLowerCase() !==
                  "not specified in resume" && (
                  <p className="text-base text-muted-foreground">
                    {certificate.issuing_organization}
                  </p>
                )}
                <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                  {certificate.issue_date && (
                    <span>Issued {formatDisplayDate(certificate.issue_date)}</span>
                  )}
                  {certificate.expiration_date && (
                    <span>Expires {formatDisplayDate(certificate.expiration_date)}</span>
                  )}
                  {certificate.credential_id && <span>Credential ID: {certificate.credential_id}</span>}
                </div>
                {certificate.credential_url && (
                  <a
                    className="inline-flex items-center gap-1 self-start text-sm text-primary underline"
                    href={certificate.credential_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Verify credential <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </CardContent>
            </Card>

            {(certificate.badge_image_url || certificate.badge_url) && (
              <Card>
                <CardContent className="flex flex-col items-center gap-3 py-5">
                  <p className="self-start text-sm font-medium">Badge</p>
                  {certificate.badge_image_url ? (
                    <ExpandableImage
                      src={certificate.badge_image_url}
                      alt={`${certificate.name} badge`}
                      className="max-h-56 max-w-full cursor-zoom-in object-contain"
                    />
                  ) : certificate.badge_url ? (
                    <a
                      href={certificate.badge_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-sm text-primary underline"
                    >
                      View badge <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : null}
                </CardContent>
              </Card>
            )}

            {certificate.certificate_file_url && (
              <Card>
                <CardContent className="py-5">
                  {certificate.certificate_file_content_type?.startsWith("image/") ? (
                    <ExpandableImage
                      src={certificate.certificate_file_url}
                      alt={`${certificate.name} certificate`}
                      className="mx-auto max-h-[75vh] max-w-full cursor-zoom-in rounded-md object-contain"
                    />
                  ) : (
                    <iframe
                      title={`${certificate.name} certificate document`}
                      src={certificate.certificate_file_url}
                      className="h-[75vh] w-full rounded-md border border-border"
                    />
                  )}
                  {certificate.certificate_file_name && (
                    <p className="mt-2 text-center text-xs text-muted-foreground">
                      {certificate.certificate_file_name}
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
          </article>
        )}
      </main>
    </div>
  );
}
