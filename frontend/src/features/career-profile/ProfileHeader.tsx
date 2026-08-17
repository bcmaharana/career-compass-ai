import {
  useCareerProfile,
  useUpdateCareerProfile,
  useUploadProfilePhoto,
} from "@/api/queries/career-profile";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import { getErrorMessage } from "@/lib/errors";
import { UserCircle } from "lucide-react";
import { type ChangeEvent, useEffect, useRef, useState } from "react";

/**
 * Editable photo/headline for the current user's career profile — the
 * page-level sticky strip (UI enhancement brief Part 2.4): stays pinned
 * at the top of the scrollable center panel, just below the global
 * fixed Header, while everything else on the page (starting with
 * ExecutiveSummarySection.tsx) scrolls normally beneath it. This only
 * works because it's a direct sibling of every other section in
 * CareerProfilePage.tsx's grid, not nested inside a taller shared
 * card — `position: sticky` stays pinned only within the height of its
 * own containing block, so nesting it inside a card tall enough to
 * contain Executive Summary too would make it stop sticking the moment
 * that card scrolled past, defeating the point.
 *
 * The profile itself is created lazily by the backend on first GET (see
 * app/application/career_profile/career_profile_service.py), so this
 * component never needs to handle a "no profile yet" state.
 *
 * Executive Summary and Core Competencies used to live in this card too
 * — both moved out to their own sections (ExecutiveSummarySection.tsx,
 * CoreCompetenciesSection.tsx) once they needed to scroll normally while
 * this stayed pinned. Each shares the same `useCareerProfile` cache and
 * `useUpdateCareerProfile` mutation but manages its own edit state
 * independently, the same pattern all three now follow.
 *
 * Local edit-form state (headline) is deliberately NOT kept in sync with
 * `profile` via a reactive useEffect — it's initialized once, explicitly,
 * when the Edit button is clicked (see openEdit below). A reactive
 * `useEffect(() => {...}, [profile])` looked harmless but had a real,
 * hard-to-spot bug: ANY background refresh of the profile query — e.g.
 * the photo upload's own cache update — would re-fire that effect and
 * silently overwrite whatever the user had typed but not yet saved, with
 * whatever the server still had. The form would still *show* the unsaved
 * edit (React hadn't re-rendered from the clobber yet), but clicking Save
 * would submit the just-overwritten (old) value — making it look like
 * saves were "not persisting" when the actual save was submitting stale
 * data it never should have held in the first place.
 *
 * Photo is Master-only regardless of which profile is currently in view
 * (one professional photo, not one per target role — resume merge never
 * touches it either) — always fetched via the unscoped `useCareerProfile(null)`
 * call. Headline, though, IS part of the current scope (a Target Role
 * Profile's own headline, independent of Master's), so it's read/saved
 * through a second, scope-aware `useCareerProfile(scope)` call. When
 * viewing Master these are the same cached query; viewing a Target Role
 * Profile, they're genuinely two different profiles' data in one card.
 */
export function ProfileHeader() {
  const scope = useProfileScope();
  const { data: masterProfile } = useCareerProfile(null);
  const { data: profile, isLoading } = useCareerProfile(scope);
  const updateProfile = useUpdateCareerProfile(scope);
  const uploadPhoto = useUploadProfilePhoto();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [headline, setHeadline] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [photoLoadFailed, setPhotoLoadFailed] = useState(false);

  // Give a freshly-uploaded (or freshly-loaded) photo URL a clean
  // chance to load — without this, one failed load attempt (e.g. a
  // transient issue right after upload) would leave the fallback icon
  // showing forever, even after the URL changes to something that
  // would load fine.
  useEffect(() => {
    setPhotoLoadFailed(false);
  }, [masterProfile?.photo_url]);

  function openEdit() {
    setHeadline(profile?.headline ?? "");
    setIsEditing(true);
  }

  async function handleSave() {
    try {
      // summary/core_competencies/section_order are omitted here, not
      // sent as null/empty — the backend only overwrites a field when
      // it's explicitly provided (see CareerProfileService.update), so
      // leaving them out preserves whatever ExecutiveSummarySection /
      // CoreCompetenciesSection / a reorder action last saved instead
      // of wiping it out.
      await updateProfile.mutateAsync({ headline: headline || null });
      setIsEditing(false);
    } catch {
      // Error is surfaced via updateProfile.isError/error below —
      // edit mode deliberately stays open so nothing typed is lost.
    }
  }

  function handlePhotoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setPhotoError(null);
    uploadPhoto.mutate(file, {
      onError: (error) => setPhotoError(getErrorMessage(error)),
    });
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading profile...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    // The sticky element is this whole wrapper — background-colored
    // padding-top (matching main's own background, AppShell.tsx) plus
    // the Card, as one solid opaque unit pinned at top-0. That's
    // deliberate: CareerProfilePage's -mt-8 cancels the page
    // container's own py-8 so this wrapper's resting position is
    // already flush with main's scroll box (zero travel before it
    // catches), and folding the gap *into* the sticky unit itself
    // (rather than leaving it as space above a sticky Card) means
    // there's no un-covered band for cards scrolling past underneath
    // to show through — it's one continuous painted box the whole way
    // down, not two independently-positioned pieces that could ever
    // drift apart mid-scroll.
    <div className="sticky top-0 z-10 min-w-0 bg-[hsl(var(--center-bg))] pt-3">
      <Card>
        <CardContent className="flex flex-col gap-4 pt-6">
        <div className="flex min-w-0 items-start justify-between gap-4">
          <div className="flex min-w-0 flex-1 items-center gap-4">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="group relative h-16 w-16 shrink-0 overflow-hidden rounded-full border border-border bg-muted md:h-28 md:w-28"
              aria-label="Change profile photo"
            >
              {masterProfile?.photo_url && !photoLoadFailed ? (
                <img
                  src={masterProfile.photo_url}
                  alt=""
                  className="h-full w-full object-cover"
                  onError={() => setPhotoLoadFailed(true)}
                />
              ) : (
                <UserCircle className="h-full w-full text-muted-foreground" strokeWidth={1} />
              )}
              <span className="absolute inset-0 flex items-center justify-center bg-black/40 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                {uploadPhoto.isPending ? "Uploading..." : "Change"}
              </span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={handlePhotoChange}
            />
            <div className="min-w-0 flex-1">
              {isEditing ? (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="headline">Headline / About</Label>
                  <RichTextEditor
                    id="headline"
                    defaultValue={headline}
                    onChange={setHeadline}
                    placeholder="e.g. Senior Product Manager"
                    autoFocus
                  />
                </div>
              ) : profile?.headline ? (
                <RichTextDisplay html={profile.headline} className="text-sm font-medium md:text-base" />
              ) : (
                <p className="text-sm font-medium text-muted-foreground md:text-base">
                  No headline yet
                </p>
              )}
              {photoError && <p className="text-xs text-destructive">{photoError}</p>}
              {photoLoadFailed && !photoError && (
                <p className="text-xs text-destructive">
                  Uploaded, but the photo couldn't be loaded — check that the storage service is
                  reachable.
                </p>
              )}
            </div>
          </div>
          {isEditing ? (
            <div className="flex shrink-0 gap-2">
              <Button size="sm" onClick={handleSave} disabled={updateProfile.isPending}>
                {updateProfile.isPending ? "Saving..." : "Save"}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="ghost" size="sm" onClick={openEdit}>
              Edit
            </Button>
          )}
        </div>
        {updateProfile.isError && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(updateProfile.error)}
          </p>
        )}
        </CardContent>
      </Card>
    </div>
  );
}
