import { useTargetRoles } from "@/api/queries/career-profile";
import { useInterviewPrepSummary, useInterviewTopics } from "@/api/queries/interview-prep";
import type { components } from "@/api/schema.gen";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TabStrip } from "@/components/ui/tab-strip";
import { InterviewTopicsSection } from "@/features/interview-prep/InterviewTopicsSection";
import { groupInterviewTopicsBySection } from "@/lib/group-interview-topics-by-section";
import { scrollToAfterPaint } from "@/lib/scroll-to-after-paint";
import { cn } from "@/lib/utils";
import { useRoleScopeParam } from "@/stores/target-role-scope-store";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

const HUB_TABS = [{ id: "articles", label: "Articles" }] as const;
type HubTabId = (typeof HUB_TABS)[number]["id"];

export function KnowledgeHubPage() {
  const { targetRoleId, searchParams, setSearchParams } = useRoleScopeParam();
  const scopeKey = targetRoleId ?? "master";
  const { data: targetRoles } = useTargetRoles();
  const { data: topics } = useInterviewTopics(targetRoleId);
  const { data: summary } = useInterviewPrepSummary();
  const [sectionFilter, setSectionFilter] = useState<string | null>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const activeTab =
    HUB_TABS.find((tab) => tab.id === searchParams.get("tab"))?.id ?? HUB_TABS[0].id;
  const tabs = HUB_TABS.map((tab) => ({
    ...tab,
    label:
      topics && summary
        ? `${tab.label} (${topics.length}/${summary.total_topic_count})`
        : tab.label,
  }));

  const groups = groupInterviewTopicsBySection(topics ?? []);
  const sectionTabs: { id: string | null; label: string }[] =
    groups.length > 1
      ? [
          { id: "all", label: "All" },
          ...groups.map((group) => ({
            id: group.section,
            label: group.section ?? "Uncategorized",
          })),
        ]
      : [];

  useEffect(() => {
    setSectionFilter("all");
    setExpandedId(null);
  }, [scopeKey]);

  function handleScopeChange(value: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set("role", value);
      else next.delete("role");
      return next;
    });
  }

  function handleTabChange(tab: HubTabId) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (tab === "articles") next.delete("tab");
      else next.set("tab", tab);
      return next;
    });
  }

  function openTopic(id: string) {
    setExpandedId(id);
    scrollToAfterPaint(`interview-topic-${id}`);
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardContent className="flex flex-col gap-3 pt-6">
          <div className="flex flex-col gap-1.5">
            <Label
              htmlFor="knowledge-hub-scope"
              className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              Current Scope
            </Label>
            <Select
              id="knowledge-hub-scope"
              className="w-72"
              value={targetRoleId ?? ""}
              onChange={(event) => handleScopeChange(event.target.value)}
            >
              <option value="">Master (generic)</option>
              {targetRoles?.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.role_name}
                </option>
              ))}
            </Select>
          </div>
          {summary && summary.scopes.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {summary.scopes.map((scope, index) => (
                <span key={scope.target_role_id ?? "master"}>
                  {index > 0 && " | "}
                  <span className="font-medium text-foreground">{scope.role_name}:</span>{" "}
                  {scope.topic_count} {scope.topic_count === 1 ? "article" : "articles"}
                </span>
              ))}
            </p>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-2">
        <TabStrip
          tabs={tabs}
          activeId={activeTab}
          onChange={handleTabChange}
          ariaLabel="Knowledge Hub sections"
        />
        {sectionTabs.length > 0 && (
          <TabStrip
            tabs={sectionTabs}
            activeId={sectionFilter}
            onChange={setSectionFilter}
            ariaLabel="Filter articles by section"
            size="sm"
          />
        )}
      </div>

      <TopicsTableOfContents
        topics={topics ?? []}
        sectionFilter={sectionFilter}
        onSelectTopic={openTopic}
      />
      <InterviewTopicsSection
        key={`${scopeKey}-articles`}
        scope={targetRoleId}
        targetRoles={targetRoles ?? []}
        expandedId={expandedId}
        setExpandedId={setExpandedId}
        sectionFilter={sectionFilter}
        totalCount={summary?.total_topic_count}
      />
    </div>
  );
}

function TopicsTableOfContents({
  topics,
  sectionFilter,
  onSelectTopic,
}: {
  topics: components["schemas"]["InterviewTopicResponse"][];
  sectionFilter: string | null;
  onSelectTopic: (id: string) => void;
}) {
  const groups = groupInterviewTopicsBySection(topics);
  const visibleGroups =
    sectionFilter === "all" ? groups : groups.filter((group) => group.section === sectionFilter);
  if (visibleGroups.length === 0) return null;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Table of Contents
        </p>
        <div className="flex flex-col gap-2">
          {visibleGroups.map((group) => (
            <div key={group.section ?? "__ungrouped"}>
              {group.section && (
                <p className="text-xs font-medium text-muted-foreground">{group.section}:</p>
              )}
              <ul className="list-disc space-y-1 pl-5">
                {group.topics.map((topic) => (
                  <li key={topic.id}>
                    <TocEntryLink
                      onSelect={() => onSelectTopic(topic.id)}
                      hasContent={topicHasContent(topic)}
                    >
                      {topic.name}
                    </TocEntryLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function topicHasContent(topic: components["schemas"]["InterviewTopicResponse"]): boolean {
  return topic.blocks.some((block) =>
    block.columns.some((column) => {
      switch (column.type) {
        case "rich_text":
          return !!column.html;
        case "image":
          return !!column.image_url;
        case "video_embed":
          return !!column.video_embed_url;
        case "external_link":
          return !!column.external_url;
        case "article_link":
          return !!column.article_topic_id;
      }
    }),
  );
}

function TocEntryLink({
  onSelect,
  children,
  hasContent,
}: {
  onSelect: () => void;
  children: ReactNode;
  hasContent: boolean;
}) {
  return (
    <span
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      title={hasContent ? undefined : "No content yet"}
      className={cn(
        "cursor-pointer text-left text-sm font-medium underline underline-offset-2",
        hasContent ? "text-accent hover:text-accent/80" : "text-destructive hover:text-destructive/80",
      )}
    >
      {children}
    </span>
  );
}
