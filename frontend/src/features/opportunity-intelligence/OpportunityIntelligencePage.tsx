import { useTargetRoles } from "@/api/queries/career-profile";
import { useCareerPath, useJobListings } from "@/api/queries/opportunity-intelligence";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { formatDisplayDateTime } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { ArrowRight, MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

/**
 * Phase 6 — Opportunity Intelligence. A target-role picker drives both
 * sections below: real job listings (Adzuna, cached server-side against
 * a 24h TTL — see JobListingService) and a career-path view (CIKG's
 * role_progresses_to graph — see CareerPathService). Single-file page,
 * matching ResumeIntelligencePage.tsx's precedent for a feature this
 * size.
 */
export function OpportunityIntelligencePage() {
  const { data: targetRoles, isLoading: rolesLoading } = useTargetRoles();
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedRoleId && targetRoles && targetRoles.length > 0) {
      setSelectedRoleId(targetRoles[0]!.id);
    }
  }, [targetRoles, selectedRoleId]);

  const {
    data: jobListings,
    isLoading: jobsLoading,
    error: jobsError,
  } = useJobListings(selectedRoleId);
  const { data: careerPath, isLoading: pathLoading } = useCareerPath(selectedRoleId);

  return (
    <div className="flex flex-col gap-6">
      {!rolesLoading && (!targetRoles || targetRoles.length === 0) && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Add a target role on your Career Profile to see matching job listings and a career
              path.
            </p>
          </CardContent>
        </Card>
      )}

      {targetRoles && targetRoles.length > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-1.5 pt-6">
            <Label htmlFor="opportunity-target-role">Target role</Label>
            <Select
              id="opportunity-target-role"
              className="w-72"
              value={selectedRoleId ?? ""}
              onChange={(e) => setSelectedRoleId(e.target.value || null)}
            >
              {targetRoles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.role_name}
                </option>
              ))}
            </Select>
          </CardContent>
        </Card>
      )}

      {selectedRoleId && (
        <Card>
          <CardHeader>
            <CardTitle>Job Listings</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-xs text-muted-foreground">
              Results below are based on your{" "}
              <Link to="/settings/job-search-preference" className="text-accent hover:underline">
                Job Search Preference
              </Link>{" "}
              settings.
            </p>
            {jobsLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
            {jobsError && (
              <p role="alert" className="text-sm text-destructive">
                {getErrorMessage(jobsError)}
              </p>
            )}
            {jobListings && (
              <>
                <p className="text-xs text-muted-foreground">
                  Last updated {formatDisplayDateTime(jobListings.fetched_at)}
                </p>
                {jobListings.listings.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No listings found for this role right now — check back later.
                  </p>
                )}
                {jobListings.listings.map((listing) => (
                  <a
                    key={listing.provider_id}
                    href={listing.redirect_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex flex-col gap-1 rounded-md border border-border p-4 transition-colors hover:bg-muted/50"
                  >
                    <p className="text-sm font-medium md:text-base">{listing.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {listing.company}
                      {listing.location ? ` — ${listing.location}` : ""}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      {listing.category && <Badge variant="accent">{listing.category}</Badge>}
                      {listing.salary_min && listing.salary_max && (
                        <Badge variant="default">
                          ${Math.round(listing.salary_min).toLocaleString()} - $
                          {Math.round(listing.salary_max).toLocaleString()}
                        </Badge>
                      )}
                    </div>
                  </a>
                ))}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {selectedRoleId && (
        <Card>
          <CardHeader>
            <CardTitle>Career Path</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {pathLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
            {careerPath && !careerPath.resolved && (
              <p className="text-sm text-muted-foreground">
                No path data yet for this role — the CIKG catalog doesn't have a match for it
                yet.
              </p>
            )}
            {careerPath?.resolved && careerPath.matched_role && (
              <div className="flex flex-col gap-4">
                <p className="text-xs text-muted-foreground">
                  Matched to <span className="font-medium">{careerPath.matched_role.title}</span>{" "}
                  {careerPath.match_type === "search_fallback" ? "(closest match)" : ""}
                </p>
                {careerPath.upstream.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">
                      Roles that lead here
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      {[...careerPath.upstream].reverse().map((role, i, arr) => (
                        <div key={role.id} className="flex items-center gap-2">
                          <Badge variant="default">{role.title}</Badge>
                          {i < arr.length - 1 && (
                            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-accent" />
                  <Badge variant="accent">{careerPath.matched_role.title}</Badge>
                  <span className="text-xs text-muted-foreground">(your target role)</span>
                </div>
                {careerPath.downstream.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">
                      Where this can lead
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      {careerPath.downstream.map((role, i, arr) => (
                        <div key={role.id} className="flex items-center gap-2">
                          <Badge variant="default">{role.title}</Badge>
                          {i < arr.length - 1 && (
                            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {careerPath.upstream.length === 0 && careerPath.downstream.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No progression data linked to this role yet.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
