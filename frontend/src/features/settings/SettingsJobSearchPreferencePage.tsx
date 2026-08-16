import {
  useJobSearchPreference,
  useUpdateJobSearchPreference,
} from "@/api/queries/opportunity-intelligence";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import { type FormEvent, useState } from "react";

type JobSearchPreferenceResponse = components["schemas"]["JobSearchPreferenceResponse"];

/**
 * Settings > Job Search Preference — the location + filter values
 * JobListingService (backend) uses as an override on top of the
 * profile-derived city/state whenever it calls Adzuna. Values here are
 * exactly what JobSearchPreferenceService validates
 * (VALID_MAX_DAYS_OLD/VALID_DISTANCE_MILES/VALID_EMPLOYMENT_TIME/
 * VALID_EMPLOYMENT_TYPE) — confirmed live against the real Adzuna API
 * before this feature was designed, not a guess. Adzuna has no native
 * remote/hybrid/on-site parameter and its own full_time/part_time and
 * contract/permanent facets are single-select (not multi-select), so
 * this page intentionally exposes only what the backend actually
 * supports rather than a broader filter set that would silently do
 * nothing.
 */
export function SettingsJobSearchPreferencePage() {
  const { data: preference, isLoading, isError, error } = useJobSearchPreference();

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Job Search Preference</CardTitle>
        <CardDescription>
          Set the location and filters used when searching for job listings on the Opportunity
          Intelligence page.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {isError && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(error)}
          </p>
        )}
        {preference && <JobSearchPreferenceForm preference={preference} />}
      </CardContent>
    </Card>
  );
}

interface SegmentedOption<T> {
  label: string;
  value: T;
}

/**
 * A row of equal-width toggle buttons, one active at a time — same
 * visual language as LoginPage.tsx's Personal/Enterprise and
 * Email/Phone toggles (bg-muted p-1 rounded-md wrapper, bg-card +
 * shadow-sm on the active option).
 */
function SegmentedControl<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-1 rounded-md bg-muted p-1">
        {options.map((option) => (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              "flex-1 whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium transition-colors",
              value === option.value
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const NO_PREFERENCE = "none";

const MAX_DAYS_OLD_OPTIONS: SegmentedOption<string>[] = [
  { label: "No preference", value: NO_PREFERENCE },
  { label: "Today", value: "1" },
  { label: "Last 3 days", value: "3" },
  { label: "Last 7 days", value: "7" },
];

const DISTANCE_MILES_OPTIONS: SegmentedOption<string>[] = [
  { label: "No preference", value: NO_PREFERENCE },
  { label: "Within 10 miles", value: "10" },
  { label: "Within 30 miles", value: "30" },
  { label: "Within 50 miles", value: "50" },
  { label: "Within 100 miles", value: "100" },
];

const EMPLOYMENT_TIME_OPTIONS: SegmentedOption<string>[] = [
  { label: "No preference", value: NO_PREFERENCE },
  { label: "Full time", value: "full_time" },
  { label: "Part time", value: "part_time" },
];

const EMPLOYMENT_TYPE_OPTIONS: SegmentedOption<string>[] = [
  { label: "No preference", value: NO_PREFERENCE },
  { label: "Contract", value: "contract" },
  { label: "Permanent", value: "permanent" },
];

/**
 * Its own component, mounted only once `preference` data exists, so
 * local form state seeds exactly once from real data — no useEffect
 * re-syncing from the query on every background refetch (see
 * SettingsAIModelPage.tsx / CLAUDE.md's frontend conventions).
 */
function JobSearchPreferenceForm({ preference }: { preference: JobSearchPreferenceResponse }) {
  const updatePreference = useUpdateJobSearchPreference();
  const [location, setLocation] = useState(preference.location ?? "");
  const [maxDaysOld, setMaxDaysOld] = useState(
    preference.max_days_old ? String(preference.max_days_old) : NO_PREFERENCE,
  );
  const [distanceMiles, setDistanceMiles] = useState(
    preference.distance_miles ? String(preference.distance_miles) : NO_PREFERENCE,
  );
  const [employmentTime, setEmploymentTime] = useState(preference.employment_time ?? NO_PREFERENCE);
  const [employmentType, setEmploymentType] = useState(preference.employment_type ?? NO_PREFERENCE);
  const [savedJustNow, setSavedJustNow] = useState(false);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSavedJustNow(false);
    updatePreference.mutate(
      {
        location: location.trim() ? location.trim() : null,
        max_days_old:
          maxDaysOld === NO_PREFERENCE ? null : (Number(maxDaysOld) as 1 | 3 | 7),
        distance_miles:
          distanceMiles === NO_PREFERENCE ? null : (Number(distanceMiles) as 10 | 30 | 50 | 100),
        employment_time:
          employmentTime === NO_PREFERENCE ? null : (employmentTime as "full_time" | "part_time"),
        employment_type:
          employmentType === NO_PREFERENCE ? null : (employmentType as "contract" | "permanent"),
      },
      { onSuccess: () => setSavedJustNow(true) },
    );
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="job-search-location">Location</Label>
        <Input
          id="job-search-location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="e.g. Seattle, WA"
        />
        <p className="text-xs text-muted-foreground">
          Overrides your Career Profile city/state for job searches. Leave blank to use your
          profile location.
        </p>
      </div>

      <SegmentedControl
        label="Posted date"
        options={MAX_DAYS_OLD_OPTIONS}
        value={maxDaysOld}
        onChange={setMaxDaysOld}
      />

      <SegmentedControl
        label="Distance"
        options={DISTANCE_MILES_OPTIONS}
        value={distanceMiles}
        onChange={setDistanceMiles}
      />

      <SegmentedControl
        label="Employment time"
        options={EMPLOYMENT_TIME_OPTIONS}
        value={employmentTime}
        onChange={setEmploymentTime}
      />

      <SegmentedControl
        label="Employment type"
        options={EMPLOYMENT_TYPE_OPTIONS}
        value={employmentType}
        onChange={setEmploymentType}
      />

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={updatePreference.isPending}>
          {updatePreference.isPending ? "Saving..." : "Save changes"}
        </Button>
        {savedJustNow && !updatePreference.isPending && (
          <span className="text-sm text-muted-foreground">Saved.</span>
        )}
      </div>

      {updatePreference.isError && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(updatePreference.error)}
        </p>
      )}
    </form>
  );
}
