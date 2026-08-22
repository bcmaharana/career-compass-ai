import { useCurrentUser, useUpdateCurrentUser } from "@/api/queries/auth";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { SettingsBackLink } from "@/features/settings/SettingsBackLink";
import { getErrorMessage } from "@/lib/errors";
import { getCountryOptions, getLanguageOptions } from "@/lib/locale-options";
import { formatPhoneForCountry } from "@/lib/phone-format";
import { VISA_STATUS_OPTIONS } from "@/lib/visa-status-options";
import { type FormEvent, useState } from "react";

type CurrentUserResponse = components["schemas"]["CurrentUserResponse"];

const COUNTRY_OPTIONS = getCountryOptions();
const LANGUAGE_OPTIONS = getLanguageOptions();

export function SettingsProfilePage() {
  const { data: user, isLoading, isError, error } = useCurrentUser();

  return (
    <div className="max-w-xl">
      <SettingsBackLink />
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>
            Your name and contact details, as they appear throughout Career Compass.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {isError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(error)}
            </p>
          )}
          {user && <SettingsProfileForm user={user} />}
        </CardContent>
      </Card>
    </div>
  );
}

/**
 * Its own component, mounted only once `user` data exists, so its local
 * form state's useState initializer seeds exactly once from real data —
 * no useEffect re-syncing from the query on every background refetch
 * (see CLAUDE.md's frontend conventions: that pattern silently overwrote
 * in-progress edits elsewhere in this app, and is deliberately avoided
 * here too).
 */
function SettingsProfileForm({ user }: { user: CurrentUserResponse }) {
  const updateCurrentUser = useUpdateCurrentUser();

  const [salutation, setSalutation] = useState(user.salutation ?? "");
  const [firstName, setFirstName] = useState(user.first_name);
  const [middleName, setMiddleName] = useState(user.middle_name ?? "");
  const [lastName, setLastName] = useState(user.last_name);
  const [handle, setHandle] = useState(user.handle ?? "");
  const [country, setCountry] = useState(user.country ?? "");
  const [phoneNumber, setPhoneNumber] = useState(
    formatPhoneForCountry(user.phone_number ?? "", user.country ?? ""),
  );
  const [language, setLanguage] = useState(user.language ?? "");
  const [addressLine1, setAddressLine1] = useState(user.address_line1 ?? "");
  const [addressLine2, setAddressLine2] = useState(user.address_line2 ?? "");
  const [city, setCity] = useState(user.city ?? "");
  const [state, setState] = useState(user.state ?? "");
  const [postalCode, setPostalCode] = useState(user.postal_code ?? "");
  const [visaStatus, setVisaStatus] = useState(user.visa_status ?? "");
  const [linkedinUrl, setLinkedinUrl] = useState(user.linkedin_url ?? "");
  const [otherProfessionalUrl, setOtherProfessionalUrl] = useState(
    user.other_professional_url ?? "",
  );
  const [savedJustNow, setSavedJustNow] = useState(false);

  const isUS = country === "US";

  function handleCountryChange(newCountry: string) {
    setCountry(newCountry);
    setPhoneNumber((current) => formatPhoneForCountry(current, newCountry));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSavedJustNow(false);
    updateCurrentUser.mutate(
      {
        salutation: salutation.trim() || null,
        first_name: firstName,
        middle_name: middleName.trim() || null,
        last_name: lastName,
        handle: handle.trim() || null,
        phone_number: phoneNumber.trim() || null,
        country: country.trim() || null,
        language: language.trim() || null,
        address_line1: addressLine1.trim() || null,
        address_line2: addressLine2.trim() || null,
        city: city.trim() || null,
        state: state.trim() || null,
        postal_code: postalCode.trim() || null,
        visa_status: visaStatus.trim() || null,
        linkedin_url: linkedinUrl.trim() || null,
        other_professional_url: otherProfessionalUrl.trim() || null,
      },
      { onSuccess: () => setSavedJustNow(true) },
    );
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-email">Email</Label>
        <Input id="settings-email" value={user.email} disabled />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-salutation">Salutation</Label>
        <Input
          id="settings-salutation"
          placeholder="e.g. Ms., Mr., Dr."
          value={salutation}
          onChange={(e) => setSalutation(e.target.value)}
          maxLength={20}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-first-name">First name</Label>
        <Input
          id="settings-first-name"
          required
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          maxLength={150}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-middle-name">Middle name</Label>
        <Input
          id="settings-middle-name"
          placeholder="Optional"
          value={middleName}
          onChange={(e) => setMiddleName(e.target.value)}
          maxLength={150}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-last-name">Last name</Label>
        <Input
          id="settings-last-name"
          required
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          maxLength={150}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-handle">Profile handle</Label>
        <Input
          id="settings-handle"
          placeholder="e.g. BCM"
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
          maxLength={32}
        />
        <p className="text-xs text-muted-foreground">
          {handle.trim()
            ? `Your public sharing links start with ${window.location.origin}/${handle.trim()}/...`
            : "Used in the URL for anything you make public (a Showcase Page, an Article). Leave blank and one is assigned automatically the first time you share something."}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-country">Country</Label>
        <Select
          id="settings-country"
          value={country}
          onChange={(e) => handleCountryChange(e.target.value)}
        >
          <option value="">Not set</option>
          {COUNTRY_OPTIONS.map((option) => (
            <option key={option.code} value={option.code}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-phone">Phone number</Label>
        <Input
          id="settings-phone"
          type="tel"
          placeholder="e.g. +1 (555) 123-4567"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(formatPhoneForCountry(e.target.value, country))}
          maxLength={30}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-language">Language</Label>
        <Select
          id="settings-language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="">Not set</option>
          {LANGUAGE_OPTIONS.map((option) => (
            <option key={option.code} value={option.code}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-address-line1">Address line 1</Label>
        <Input
          id="settings-address-line1"
          placeholder="Street address"
          value={addressLine1}
          onChange={(e) => setAddressLine1(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-address-line2">Address line 2</Label>
        <Input
          id="settings-address-line2"
          placeholder="Apt, suite, unit (optional)"
          value={addressLine2}
          onChange={(e) => setAddressLine2(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-city">City</Label>
        <Input
          id="settings-city"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          maxLength={100}
        />
      </div>

      {isUS ? (
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="settings-state">State</Label>
            <Input
              id="settings-state"
              placeholder="e.g. CA"
              value={state}
              onChange={(e) => setState(e.target.value)}
              maxLength={100}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="settings-postal-code">ZIP code</Label>
            <Input
              id="settings-postal-code"
              placeholder="e.g. 94103"
              value={postalCode}
              onChange={(e) => setPostalCode(e.target.value)}
              maxLength={20}
            />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="settings-postal-code">Postal code</Label>
            <Input
              id="settings-postal-code"
              value={postalCode}
              onChange={(e) => setPostalCode(e.target.value)}
              maxLength={20}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="settings-state">State / Province (optional)</Label>
            <Input
              id="settings-state"
              value={state}
              onChange={(e) => setState(e.target.value)}
              maxLength={100}
            />
          </div>
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-visa-status">Visa status</Label>
        <Select
          id="settings-visa-status"
          value={visaStatus}
          onChange={(e) => setVisaStatus(e.target.value)}
        >
          <option value="">Not set</option>
          {VISA_STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-linkedin-url">LinkedIn profile URL</Label>
        <Input
          id="settings-linkedin-url"
          type="text"
          placeholder="linkedin.com/in/yourname"
          value={linkedinUrl}
          onChange={(e) => setLinkedinUrl(e.target.value)}
          maxLength={2048}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-other-professional-url">Other professional URL</Label>
        <Input
          id="settings-other-professional-url"
          type="text"
          placeholder="e.g. a portfolio site or GitHub profile"
          value={otherProfessionalUrl}
          onChange={(e) => setOtherProfessionalUrl(e.target.value)}
          maxLength={2048}
        />
      </div>

      <div className="flex items-center gap-3">
        <Button
          type="submit"
          disabled={!firstName.trim() || !lastName.trim() || updateCurrentUser.isPending}
        >
          {updateCurrentUser.isPending ? "Saving..." : "Save changes"}
        </Button>
        {savedJustNow && !updateCurrentUser.isPending && (
          <span className="text-sm text-muted-foreground">Saved.</span>
        )}
      </div>

      {updateCurrentUser.isError && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(updateCurrentUser.error)}
        </p>
      )}
    </form>
  );
}
