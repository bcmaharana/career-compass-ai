import { ApiError } from "@/api/client";
import { usePublicProfileSkill } from "@/api/queries/profile-skills";
import { Card, CardContent } from "@/components/ui/card";
import { ExpandableImage } from "@/features/public-sharing/ExpandableImage";
import { PublicPageHeader } from "@/features/public-sharing/PublicPageHeader";
import { useNoIndex } from "@/hooks/useNoIndex";
import { formatDisplayDate } from "@/lib/date-format";
import { ExternalLink } from "lucide-react";
import { useParams } from "react-router-dom";

export function PublicProfileSkillPage() {
  useNoIndex();
  const { shareKey } = useParams<{ shareKey: string }>();
  const { data: skill, isLoading, isError, error } = usePublicProfileSkill(shareKey);

  return (
    <div className="min-h-screen bg-[hsl(218,25%,93%)]">
      <PublicPageHeader>
        {skill && (
          <span className="font-display text-lg font-semibold text-primary-foreground">
            Below skill is issued to {skill.owner_display_name}
          </span>
        )}
      </PublicPageHeader>
      <main className="mx-auto w-full max-w-4xl px-3 py-6 sm:px-6 md:py-10">
        {isLoading && <p className="text-sm text-muted-foreground">Loading skill...</p>}
        {isError && (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-sm text-muted-foreground">
                {error instanceof ApiError && error.status === 404
                  ? "This skill doesn't exist or is no longer public."
                  : "Something went wrong loading this skill."}
              </p>
            </CardContent>
          </Card>
        )}
        {skill && (
          <article className="flex flex-col gap-4">
            <Card>
              <CardContent className="flex flex-col gap-3 py-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Skill
                </p>
                <h1 className="font-display text-2xl font-semibold">{skill.name}</h1>
                {skill.issuing_organization.trim().toLowerCase() !==
                  "not specified in resume" && (
                  <p className="text-base text-muted-foreground">
                    {skill.issuing_organization}
                  </p>
                )}
                <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                  {skill.issue_date && (
                    <span>Issued {formatDisplayDate(skill.issue_date)}</span>
                  )}
                  {skill.expiration_date && (
                    <span>Expires {formatDisplayDate(skill.expiration_date)}</span>
                  )}
                  {skill.credential_id && <span>Credential ID: {skill.credential_id}</span>}
                </div>
                {skill.credential_url && (
                  <a
                    className="inline-flex items-center gap-1 self-start text-sm text-primary underline"
                    href={skill.credential_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Verify credential <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </CardContent>
            </Card>

            {(skill.badge_image_url || skill.badge_url) && (
              <Card>
                <CardContent className="flex flex-col items-center gap-3 py-5">
                  <p className="self-start text-sm font-medium">Badge</p>
                  {skill.badge_image_url ? (
                    <ExpandableImage
                      src={skill.badge_image_url}
                      alt={`${skill.name} badge`}
                      className="max-h-56 max-w-full cursor-zoom-in object-contain"
                    />
                  ) : skill.badge_url ? (
                    <a
                      href={skill.badge_url}
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

            {skill.skill_file_url && (
              <Card>
                <CardContent className="py-5">
                  {skill.skill_file_content_type?.startsWith("image/") ? (
                    <ExpandableImage
                      src={skill.skill_file_url}
                      alt={`${skill.name} skill file`}
                      className="mx-auto max-h-[75vh] max-w-full cursor-zoom-in rounded-md object-contain"
                    />
                  ) : (
                    <iframe
                      title={`${skill.name} skill document`}
                      src={skill.skill_file_url}
                      className="h-[75vh] w-full rounded-md border border-border"
                    />
                  )}
                  {skill.skill_file_name && (
                    <p className="mt-2 text-center text-xs text-muted-foreground">
                      {skill.skill_file_name}
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
