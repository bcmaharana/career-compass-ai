import { useTargetRoles } from "@/api/queries/career-profile";
import {
  useExtractJd,
  useStartCustomSession,
  useStartSessionFromListing,
} from "@/api/queries/jd-tailoring";
import { useTrackedProviderIds } from "@/api/queries/job-application-tracking";
import { useCareerPath, useJobListings } from "@/api/queries/opportunity-intelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InlineLink } from "@/components/ui/inline-link";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatDisplayDateTime } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { resolveValidTargetRoleId, useTargetRoleScopeStore } from "@/stores/target-role-scope-store";
import { ArrowRight, ExternalLink, MapPin } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Phase 6 — Opportunity Intelligence, extended in Phase 8.2 (JD
 * Tailoring + Job Application Tracking) with a radio-select per
 * listing row, a "Get JD"/"Evaluate" flow that starts a JD Tailoring
 * session (see app/application/jd_tailoring/), an "Already tracking"
 * badge backed by useTrackedProviderIds, and an "Add Your Own JD"
 * dialog independent of whatever row is selected. Starting a session
 * from either entry point shows an inline confirmation with a direct
 * link into that session's conversation on the JD Tailoring page
 * (/jd-tailoring?session=<id>) — deliberately not an automatic
 * navigation away, since the user may want to keep evaluating more
 * listings on this page first.
 */
export function OpportunityIntelligencePage() {
  const { data: targetRoles, isLoading: rolesLoading } = useTargetRoles();
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const setActiveTargetRoleId = useTargetRoleScopeStore((s) => s.setActiveTargetRoleId);

  // Defaults to whichever role is currently active app-wide (see
  // target-role-scope-store.ts), falling back to the person's first
  // target role if that scope is Master or points at a role that no
  // longer exists — this page has no Master mode of its own (job
  // listings/career path are always role-specific), so it needs *some*
  // role selected. Only reads the shared scope, doesn't write it —
  // otherwise simply landing here (with nothing stored anywhere yet)
  // would silently make this page's own auto-picked first role the new
  // app-wide default, even though the person never actually chose it —
  // see handleRoleChange below for the one place that's a real choice.
  useEffect(() => {
    if (!selectedRoleId && targetRoles && targetRoles.length > 0) {
      const preferred = resolveValidTargetRoleId(
        useTargetRoleScopeStore.getState().activeTargetRoleId,
        targetRoles,
      );
      setSelectedRoleId(preferred ?? targetRoles[0]!.id);
    }
  }, [targetRoles, selectedRoleId]);

  function handleRoleChange(value: string) {
    const roleId = value || null;
    setSelectedRoleId(roleId);
    setActiveTargetRoleId(roleId);
  }

  const {
    data: jobListings,
    isLoading: jobsLoading,
    error: jobsError,
  } = useJobListings(selectedRoleId);
  const { data: careerPath, isLoading: pathLoading } = useCareerPath(selectedRoleId);
  const { data: trackedProviderIds } = useTrackedProviderIds();

  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [jdText, setJdText] = useState("");
  const [startedSession, setStartedSession] = useState<{
    id: string;
    title: string;
    company: string;
  } | null>(null);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const startFromListing = useStartSessionFromListing();

  // A stale provider_id/JD text from a different role's listing set
  // would silently point at the wrong job once the role changes.
  useEffect(() => {
    setSelectedProviderId(null);
    setJdText("");
    setStartedSession(null);
  }, [selectedRoleId]);

  const selectedListing =
    jobListings?.listings.find((listing) => listing.provider_id === selectedProviderId) ?? null;

  function selectRow(providerId: string) {
    if (providerId === selectedProviderId) return;
    setSelectedProviderId(providerId);
    setJdText("");
    setStartedSession(null);
  }

  function handleGetJd() {
    if (selectedListing) setJdText(selectedListing.description);
  }

  function handleEvaluate() {
    if (!selectedRoleId || !selectedListing || !jdText.trim()) return;
    startFromListing.mutate(
      {
        target_role_id: selectedRoleId,
        provider_id: selectedListing.provider_id,
        title: selectedListing.title,
        company: selectedListing.company ?? "Unknown company",
        redirect_url: selectedListing.redirect_url,
        jd_text: jdText,
      },
      {
        onSuccess: (data) => {
          setStartedSession({
            id: data.session.id,
            title: selectedListing.title,
            company: selectedListing.company ?? "Unknown company",
          });
          setJdText("");
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {!rolesLoading && (!targetRoles || targetRoles.length === 0) && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Add a target role on your <InlineLink to="/profile">Career Profile</InlineLink> to
              see matching job listings and a career path.
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
              onChange={(e) => handleRoleChange(e.target.value)}
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
        <div className="grid gap-4 lg:grid-cols-[1fr_380px] lg:items-start">
          <Card className="lg:min-w-0">
            <CardHeader>
              <CardTitle>Job Listings</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-xs text-muted-foreground">
                Results below are based on your{" "}
                <InlineLink to="/settings/job-search-preference">Job Search Preference</InlineLink>{" "}
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
                  {jobListings.listings.length > 0 && (
                    <div className="flex flex-col gap-2">
                      {jobListings.listings.map((listing) => (
                        <div
                          key={listing.provider_id}
                          onClick={() => selectRow(listing.provider_id)}
                          className="flex cursor-pointer items-start gap-3 rounded-md border border-border px-4 py-2 hover:bg-muted"
                        >
                          <input
                            type="radio"
                            name="job-listing-select"
                            className="mt-1.5 h-3.5 w-3.5 shrink-0 accent-accent"
                            checked={selectedProviderId === listing.provider_id}
                            onChange={() => selectRow(listing.provider_id)}
                            onClick={(event) => event.stopPropagation()}
                            aria-label={`Select ${listing.title} at ${listing.company ?? "this company"}`}
                          />
                          <div className="flex flex-1 flex-col gap-1">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-medium">{listing.title}</p>
                              <a
                                href={listing.redirect_url}
                                target="_blank"
                                rel="noreferrer"
                                onClick={() => selectRow(listing.provider_id)}
                                className="flex shrink-0 items-center gap-1 text-xs text-accent hover:underline"
                              >
                                View posting <ExternalLink className="h-3 w-3" />
                              </a>
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {listing.company}
                              {listing.location ? ` — ${listing.location}` : ""}
                            </p>
                            <div className="flex flex-wrap items-center gap-2">
                              {listing.category && (
                                <Badge variant="accent">{listing.category}</Badge>
                              )}
                              {listing.salary_min && listing.salary_max && (
                                <Badge variant="default">
                                  ${Math.round(listing.salary_min).toLocaleString()} - $
                                  {Math.round(listing.salary_max).toLocaleString()}
                                </Badge>
                              )}
                              {trackedProviderIds?.includes(listing.provider_id) && (
                                <Badge variant="accent">Already tracking</Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Floating alongside the listings (not fully covering them —
              a fixed-width right column, not an overlay) so "Get JD" stays
              reachable while scrolling a long listings list, rather than
              requiring a scroll back down to a JD box that used to live
              at the bottom of the same card — direct 2026-08-20 request. */}
          <Card className="lg:sticky lg:top-0">
            <CardHeader>
              <CardTitle>Job Description</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <Label htmlFor="jd-text">Job description</Label>
              <Textarea
                id="jd-text"
                rows={6}
                placeholder='Select a listing and click "Get JD", or paste a job description here.'
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
              />
              {selectedListing && (
                <p className="text-xs text-muted-foreground">
                  "Get JD" pulls in the listing's own summary text, which is often shortened —
                  paste the full posting here if you've read it on the listing's site.
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!selectedListing}
                  onClick={handleGetJd}
                >
                  Get JD
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={!selectedListing || !jdText.trim() || startFromListing.isPending}
                  onClick={handleEvaluate}
                >
                  {startFromListing.isPending ? "Starting..." : "Evaluate / Get Recommendation"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsAddDialogOpen(true)}
                >
                  Add Your Own JD
                </Button>
              </div>
              {startFromListing.isError && (
                <p role="alert" className="text-sm text-destructive">
                  {getErrorMessage(startFromListing.error)}
                </p>
              )}
              {startedSession && (
                <p className="text-sm text-accent">
                  Started a JD Tailoring session for "{startedSession.title}" at{" "}
                  {startedSession.company} — it's now tracked as a Job Application.{" "}
                  <InlineLink to={`/jd-tailoring?session=${startedSession.id}`}>
                    Go to the conversation
                  </InlineLink>
                </p>
              )}
            </CardContent>
          </Card>
        </div>
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

      <AddYourOwnJdDialog
        open={isAddDialogOpen}
        onClose={() => setIsAddDialogOpen(false)}
        targetRoleId={selectedRoleId}
      />
    </div>
  );
}

interface AddYourOwnJdDialogProps {
  open: boolean;
  onClose: () => void;
  targetRoleId: string | null;
}

/**
 * Always independent of whatever listing row is radio-selected on the
 * page behind it, even if one is — no provider_id exists for a pasted
 * JD, so there's nothing to dedupe/link against. Scoped to whichever
 * target role the page currently has selected (Opportunity
 * Intelligence has no Master-profile job search, so there's always a
 * real role in context here).
 */
function AddYourOwnJdDialog({ open, onClose, targetRoleId }: AddYourOwnJdDialogProps) {
  const [jdText, setJdText] = useState("");
  const [hasExtracted, setHasExtracted] = useState(false);
  const [company, setCompany] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [startedSessionId, setStartedSessionId] = useState<string | null>(null);
  const extractJd = useExtractJd();
  const startCustom = useStartCustomSession();

  function reset() {
    setJdText("");
    setHasExtracted(false);
    setCompany("");
    setRoleTitle("");
    setStartedSessionId(null);
    extractJd.reset();
    startCustom.reset();
  }

  function handleClose() {
    reset();
    onClose();
  }

  function handleExtract() {
    extractJd.mutate(
      { jd_text: jdText },
      {
        onSuccess: (data) => {
          setCompany(data.company ?? "");
          setRoleTitle(data.role_title ?? "");
          setHasExtracted(true);
        },
      },
    );
  }

  function handleStart() {
    if (!company.trim() || !roleTitle.trim()) return;
    startCustom.mutate(
      { target_role_id: targetRoleId, jd_text: jdText, company, role_title: roleTitle },
      { onSuccess: (data) => setStartedSessionId(data.session.id) },
    );
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title="Add Your Own JD"
      description="Paste a job description you found outside Opportunity Intelligence."
    >
      {startedSessionId ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-accent">
            Session started for "{roleTitle}" at {company} — it's now tracked as a Job
            Application.{" "}
            <InlineLink to={`/jd-tailoring?session=${startedSessionId}`} onClick={handleClose}>
              Go to the conversation
            </InlineLink>
          </p>
          <div className="flex justify-end">
            <Button type="button" onClick={handleClose}>
              Stay here
            </Button>
          </div>
        </div>
      ) : !hasExtracted ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="custom-jd-text">Job description</Label>
            <Textarea
              id="custom-jd-text"
              rows={10}
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste the full job description here..."
            />
          </div>
          {extractJd.isError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(extractJd.error)}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!jdText.trim() || extractJd.isPending}
              onClick={handleExtract}
            >
              {extractJd.isPending ? "Extracting..." : "Extract"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-muted-foreground">
            Confirm or fill in whatever the AI couldn't find in the JD text.
          </p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="custom-jd-company">Company</Label>
            <Input
              id="custom-jd-company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="custom-jd-role-title">Role title</Label>
            <Input
              id="custom-jd-role-title"
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
            />
          </div>
          {startCustom.isError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(startCustom.error)}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setHasExtracted(false)}>
              Back
            </Button>
            <Button
              type="button"
              disabled={!company.trim() || !roleTitle.trim() || startCustom.isPending}
              onClick={handleStart}
            >
              {startCustom.isPending ? "Starting..." : "Start"}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
