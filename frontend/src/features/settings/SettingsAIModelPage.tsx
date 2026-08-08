import { useModelSelection, useSetModelPreference } from "@/api/queries/ai-platform";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { getErrorMessage } from "@/lib/errors";
import { type FormEvent, useState } from "react";

type ModelSelectionResponse = components["schemas"]["ModelSelectionResponse"];

export function SettingsAIModelPage() {
  const { data: selection, isLoading, isError, error } = useModelSelection();

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>AI Model</CardTitle>
        <CardDescription>
          Choose which AI model powers your AI Career Coach conversations.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {isError && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(error)}
          </p>
        )}
        {selection && <SettingsAIModelForm selection={selection} />}
      </CardContent>
    </Card>
  );
}

/**
 * Its own component, mounted only once `selection` data exists, so its
 * local form state's useState initializer seeds exactly once from real
 * data — no useEffect re-syncing from the query on every background
 * refetch (see SettingsProfilePage / CLAUDE.md's frontend conventions).
 */
function SettingsAIModelForm({ selection }: { selection: ModelSelectionResponse }) {
  const setModelPreference = useSetModelPreference();
  const [modelVersionId, setModelVersionId] = useState(selection.selected_id);
  const [savedJustNow, setSavedJustNow] = useState(false);

  const defaultOption = selection.available.find((option) => option.is_default);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSavedJustNow(false);
    setModelPreference.mutate(
      // Selecting the platform default explicitly clears the override
      // (model_version_id: null) rather than pinning to that model's
      // id — so this user automatically follows if the platform default
      // is ever changed to a different model.
      { model_version_id: modelVersionId === defaultOption?.id ? null : modelVersionId },
      { onSuccess: () => setSavedJustNow(true) },
    );
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="settings-ai-model">Model</Label>
        <Select
          id="settings-ai-model"
          value={modelVersionId}
          onChange={(e) => setModelVersionId(e.target.value)}
        >
          {selection.available.map((option) => (
            <option key={option.id} value={option.id}>
              {option.display_name}
              {option.is_default ? " (default)" : ""}
            </option>
          ))}
        </Select>
        <p className="text-xs text-muted-foreground">
          Applies to new messages in the AI Career Coach chat.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={setModelPreference.isPending}>
          {setModelPreference.isPending ? "Saving..." : "Save changes"}
        </Button>
        {savedJustNow && !setModelPreference.isPending && (
          <span className="text-sm text-muted-foreground">Saved.</span>
        )}
      </div>

      {setModelPreference.isError && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(setModelPreference.error)}
        </p>
      )}
    </form>
  );
}
