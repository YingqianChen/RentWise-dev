"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeftRight,
  Bus,
  Car,
  ChevronLeft,
  ChevronRight,
  Clock,
  Compass,
  Crown,
  DollarSign,
  Eye,
  Footprints,
  MapPin,
  MessageSquare,
  TrainFront,
  TrendingUp,
  X,
} from "lucide-react";

import type { CommuteEvidence, CommuteRoute, CommuteSegment } from "@/lib/types";

import { compareCandidates, getProject } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type {
  CompareCandidateCard,
  ComparisonResponse,
  Project,
} from "@/lib/types";

const MAX_COMPARE_CANDIDATES = 5;

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

type ButtonVariant = "default" | "outline" | "ghost";
type ButtonSize = "default" | "sm";

function Button({
  variant = "default",
  size = "default",
  className,
  disabled,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
}) {
  const base =
    "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition focus:outline-none focus:ring-2 focus:ring-primary-500/40 disabled:opacity-50 disabled:pointer-events-none";
  const sizeCls = size === "sm" ? "h-8 px-2.5 text-sm" : "h-9 px-3.5 text-sm";
  const variantCls =
    variant === "outline"
      ? "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
      : variant === "ghost"
        ? "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        : "bg-gray-900 text-white hover:bg-black";
  return (
    <button
      type="button"
      disabled={disabled}
      className={cn(base, sizeCls, variantCls, className)}
      {...props}
    />
  );
}

function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "emerald" | "amber" | "red" | "blue" | "violet";
}) {
  const toneCls =
    tone === "emerald"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : tone === "amber"
        ? "bg-amber-50 text-amber-800 ring-amber-200"
        : tone === "red"
          ? "bg-red-50 text-red-700 ring-red-200"
          : tone === "blue"
            ? "bg-blue-50 text-blue-700 ring-blue-200"
            : tone === "violet"
              ? "bg-violet-50 text-violet-700 ring-violet-200"
              : "bg-gray-100 text-gray-700 ring-gray-200";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        toneCls,
        className
      )}
      {...props}
    />
  );
}

function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-gray-200 bg-white text-gray-900 shadow-sm",
        className
      )}
      {...props}
    />
  );
}

function actionLabel(action: string) {
  switch (action) {
    case "verify_cost":
      return "Verify cost";
    case "verify_clause":
      return "Verify clauses";
    case "schedule_viewing":
      return "Schedule viewing";
    case "keep_warm":
      return "Keep warm";
    case "reject":
      return "Reject";
    default:
      return action;
  }
}

function recommendationLabel(value: string) {
  switch (value) {
    case "shortlist_recommendation":
      return "System: shortlist";
    case "likely_reject":
      return "System: reject";
    default:
      return "System: not ready";
  }
}

function userDecisionLabel(value: CompareCandidateCard["user_decision"]) {
  if (value === "shortlisted") return "You: shortlisted";
  if (value === "rejected") return "You: rejected";
  return null;
}

function userDecisionTone(value: CompareCandidateCard["user_decision"]) {
  return value === "shortlisted" ? ("emerald" as const) : ("red" as const);
}

function recommendationTone(value: string) {
  switch (value) {
    case "shortlist_recommendation":
      return "emerald" as const;
    case "likely_reject":
      return "red" as const;
    default:
      return "amber" as const;
  }
}

function decisionConfidenceLabel(value: string) {
  switch (value) {
    case "high":
      return "High";
    case "medium":
      return "Medium";
    default:
      return "Low";
  }
}

function decisionConfidenceTone(value: string) {
  switch (value) {
    case "high":
      return "emerald" as const;
    case "medium":
      return "amber" as const;
    default:
      return "neutral" as const;
  }
}

function DecisionConfidenceBadge({ value }: { value: string }) {
  return (
    <Badge tone={decisionConfidenceTone(value)}>
      Decision confidence: {decisionConfidenceLabel(value)}
    </Badge>
  );
}

function evidenceStatusTone(value: string) {
  switch (value) {
    case "supported":
      return "emerald" as const;
    case "mixed":
      return "amber" as const;
    default:
      return "red" as const;
  }
}

function evidenceStatusLabel(value: string) {
  switch (value) {
    case "supported":
      return "Supported";
    case "mixed":
      return "Mixed";
    case "needs_confirmation":
      return "Needs confirmation";
    default:
      return value;
  }
}

function EvidenceStatusBadge({ value }: { value: string }) {
  return (
    <Badge tone={evidenceStatusTone(value)}>
      Evidence: {evidenceStatusLabel(value)}
    </Badge>
  );
}

function EvidenceSummary({
  summary,
}: {
  summary: CompareCandidateCard["evidence_summary"];
}) {
  const sourceText = summary.source_labels.length
    ? summary.source_labels.join(" · ")
    : "No direct source attached";

  return (
    <details className="mt-3 rounded-lg border border-gray-200 bg-gray-50">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-xs">
        <span className="font-semibold text-gray-700">Evidence coverage</span>
        <span className="text-gray-500">
          {summary.explicit_count} clear · {summary.unresolved_count} not confirmed
        </span>
      </summary>
      <div className="space-y-2 border-t border-gray-200 px-3 py-3 text-xs text-gray-600">
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          <span>Clear: {summary.explicit_count}</span>
          <span>Inferred: {summary.inferred_count}</span>
          <span>Not confirmed: {summary.unresolved_count}</span>
          <span>Conflicted: {summary.conflicted_count}</span>
        </div>
        <p>Source types: {sourceText}</p>
        <p className="text-gray-500">
          Open candidate detail to review the exact fields and evidence quotes.
        </p>
      </div>
    </details>
  );
}

function differenceIcon(category: string) {
  const key = category.toLowerCase();
  if (key.includes("cost") || key.includes("rent") || key.includes("budget")) return DollarSign;
  if (key.includes("commute") || key.includes("location")) return MapPin;
  if (key.includes("clause") || key.includes("risk")) return AlertTriangle;
  if (key.includes("time") || key.includes("move")) return Clock;
  if (key.includes("fit") || key.includes("match")) return Compass;
  return TrendingUp;
}

function segmentMeta(mode: string): {
  Icon: typeof MapPin;
  label: string;
} {
  switch (mode) {
    case "walking":
      return { Icon: Footprints, label: "Walk" };
    case "subway":
      return { Icon: TrainFront, label: "MTR" };
    case "rail":
      return { Icon: TrainFront, label: "Rail" };
    case "airport_express":
      return { Icon: TrainFront, label: "AEL" };
    case "minibus":
      return { Icon: Bus, label: "Minibus" };
    case "bus":
      return { Icon: Bus, label: "Bus" };
    case "taxi":
      return { Icon: Car, label: "Taxi" };
    default:
      return { Icon: MapPin, label: mode };
  }
}

function RouteStrip({ segments }: { segments: CommuteSegment[] }) {
  if (segments.length === 0) return null;
  return (
    <ol className="mt-2 flex flex-wrap items-center gap-1 text-xs">
      {segments.map((seg, idx) => {
        const { Icon, label } = segmentMeta(seg.mode);
        return (
          <li key={idx} className="flex items-center gap-1">
            {idx > 0 && <ChevronRight className="h-3 w-3 shrink-0 text-gray-300" />}
            <span className="inline-flex items-center gap-1 rounded-md bg-white px-1.5 py-0.5 text-gray-700 ring-1 ring-gray-200">
              <Icon className="h-3 w-3 text-gray-500" />
              <span className="font-medium">{label}</span>
              {seg.line_name && <span className="text-gray-500">·</span>}
              {seg.line_name && <span className="text-gray-600">{seg.line_name}</span>}
              {seg.duration_minutes != null && (
                <span className="text-gray-500">{seg.duration_minutes}min</span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

type CommutePanelRoute = {
  label: string;
  minutes: number | null;
  segments: CommuteSegment[] | null;
  isPrimary: boolean;
};

function buildPanelRoutes(commute: CommuteEvidence): CommutePanelRoute[] {
  const primary: CommutePanelRoute = {
    label: "Fastest",
    minutes: commute.estimated_minutes,
    segments: commute.segments,
    isPrimary: true,
  };
  const alternates: CommutePanelRoute[] = (commute.alternatives ?? []).map(
    (alt: CommuteRoute) => ({
      label: alt.label || "Alternative",
      minutes: alt.estimated_minutes,
      segments: alt.segments,
      isPrimary: false,
    })
  );
  return [primary, ...alternates];
}

function SingleWindowCommutePanelBody({
  commute,
}: {
  commute: CommuteEvidence;
}) {
  const routes = useMemo(() => buildPanelRoutes(commute), [commute]);
  const [activeIdx, setActiveIdx] = useState(0);
  // Reset to primary if the route count shrinks (e.g. cache invalidation).
  const safeIdx = Math.min(activeIdx, routes.length - 1);
  const active = routes[safeIdx];
  const showTabs = routes.length > 1;

  return (
    <>
      <p className="mt-1 text-sm text-gray-800">
        {commute.estimated_minutes} min ({commute.mode})
        {commute.destination_label && ` · ${commute.destination_label}`}
      </p>
      {showTabs && (
        <div
          role="tablist"
          aria-label="Route alternatives"
          className="mt-2 flex flex-wrap gap-1"
        >
          {routes.map((route, idx) => {
            const isActive = idx === safeIdx;
            return (
              <button
                key={`${route.label}-${idx}`}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveIdx(idx)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition",
                  isActive
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-white text-gray-700 ring-1 ring-gray-200 hover:bg-gray-50"
                )}
              >
                <span>{route.label}</span>
                {route.minutes != null && (
                  <span className={isActive ? "text-blue-100" : "text-gray-500"}>
                    {route.minutes}min
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
      {active.segments && active.segments.length > 0 ? (
        <RouteStrip segments={active.segments} />
      ) : (
        <p className="mt-2 text-xs text-gray-500">Route detail unavailable.</p>
      )}
      {commute.confidence_note && (
        <p className="mt-1 text-xs text-amber-700">{commute.confidence_note}</p>
      )}
    </>
  );
}

function CommutePanel({ commute }: { commute: CommuteEvidence }) {
  const paired = commute.paired_evidence;
  const hasPaired =
    paired != null &&
    paired.status === "ready" &&
    paired.estimated_minutes != null;
  const [activeWindow, setActiveWindow] = useState<"am" | "pm">("am");
  const active = hasPaired && activeWindow === "pm" ? paired! : commute;

  return (
    <div className="rounded-lg bg-blue-50/60 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
          <MapPin className="h-3 w-3" /> Commute
        </p>
        {hasPaired && (
          <div
            role="tablist"
            aria-label="Departure window"
            className="inline-flex overflow-hidden rounded-md ring-1 ring-blue-200"
          >
            {(
              [
                { key: "am", label: "AM 8:30", mins: commute.estimated_minutes },
                { key: "pm", label: "PM 18:30", mins: paired!.estimated_minutes },
              ] as const
            ).map(({ key, label, mins }) => {
              const isActive = activeWindow === key;
              return (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveWindow(key)}
                  className={cn(
                    "px-2 py-1 text-xs font-medium transition",
                    isActive
                      ? "bg-blue-600 text-white"
                      : "bg-white text-blue-700 hover:bg-blue-50"
                  )}
                >
                  {label}
                  {mins != null && <span className="ml-1 opacity-80">{mins}min</span>}
                </button>
              );
            })}
          </div>
        )}
      </div>
      <SingleWindowCommutePanelBody commute={active} />
    </div>
  );
}

function BestOptionHero({
  candidate,
  projectId,
}: {
  candidate: CompareCandidateCard;
  projectId: string;
}) {
  return (
    <Card className="relative overflow-hidden border-emerald-200">
      <div className="absolute inset-y-0 left-0 w-1 bg-emerald-500" />
      <div className="p-5 pl-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-emerald-500 text-white">
                <Crown className="h-3.5 w-3.5" />
              </div>
              <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
                Best current option
              </p>
            </div>
            <h3 className="mt-2 text-xl font-semibold text-gray-900">{candidate.name}</h3>
            <p className="mt-0.5 text-sm text-gray-600">
              {candidate.monthly_rent || "Rent unknown"} ·{" "}
              {candidate.district || "District unknown"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={recommendationTone(candidate.top_recommendation)}>
              {recommendationLabel(candidate.top_recommendation)}
            </Badge>
            <DecisionConfidenceBadge value={candidate.decision_confidence} />
            {userDecisionLabel(candidate.user_decision) && (
              <Badge tone={userDecisionTone(candidate.user_decision)}>
                {userDecisionLabel(candidate.user_decision)}
              </Badge>
            )}
            <Badge tone="blue">{actionLabel(candidate.next_action)}</Badge>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-gray-700">{candidate.decision_explanation}</p>

        <EvidenceSummary summary={candidate.evidence_summary} />

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {candidate.commute_evidence?.status === "ready" && (
            <CommutePanel commute={candidate.commute_evidence} />
          )}
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Main tradeoff
            </p>
            <p className="mt-0.5 text-sm text-gray-700">{candidate.main_tradeoff}</p>
          </div>
          {candidate.open_blocker && (
            <div>
              <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
                <AlertTriangle className="h-3 w-3" /> Open blocker
              </p>
              <p className="mt-0.5 text-sm text-gray-700">{candidate.open_blocker}</p>
            </div>
          )}
        </div>

        <div className="mt-4 flex justify-end">
          <Link
            href={`/projects/${projectId}/candidates/${candidate.candidate_id}`}
            className="inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            Open detail →
          </Link>
        </div>
      </div>
    </Card>
  );
}

function AlternativeCard({
  candidate,
  projectId,
}: {
  candidate: CompareCandidateCard;
  projectId: string;
}) {
  return (
    <Card className="flex h-full flex-col p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold text-gray-900">{candidate.name}</h4>
          <p className="mt-0.5 text-xs text-gray-500">
            {candidate.monthly_rent || "Rent unknown"} ·{" "}
            {candidate.district || "District unknown"}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Badge tone={recommendationTone(candidate.top_recommendation)}>
            {recommendationLabel(candidate.top_recommendation)}
          </Badge>
          <DecisionConfidenceBadge value={candidate.decision_confidence} />
          {userDecisionLabel(candidate.user_decision) && (
            <Badge tone={userDecisionTone(candidate.user_decision)}>
              {userDecisionLabel(candidate.user_decision)}
            </Badge>
          )}
        </div>
      </div>

      <p className="mt-2 text-xs leading-5 text-gray-600 line-clamp-3">
        {candidate.decision_explanation}
      </p>

      <EvidenceSummary summary={candidate.evidence_summary} />

      <div className="mt-2 space-y-1.5 text-xs text-gray-700">
        {candidate.commute_evidence?.status === "ready" && (
          <div className="flex items-center gap-1.5">
            <MapPin className="h-3 w-3 text-gray-400" />
            {candidate.commute_evidence.estimated_minutes} min
            {candidate.commute_evidence.destination_label &&
              ` · ${candidate.commute_evidence.destination_label}`}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 border-t border-gray-100 pt-3">
        <Badge tone="blue">{actionLabel(candidate.next_action)}</Badge>
        <Link
          href={`/projects/${projectId}/candidates/${candidate.candidate_id}`}
          className="text-xs font-medium text-primary-600 hover:text-primary-700"
        >
          Detail →
        </Link>
      </div>
    </Card>
  );
}

function TertiaryCard({
  candidate,
  projectId,
  accent,
}: {
  candidate: CompareCandidateCard;
  projectId: string;
  accent: "amber" | "gray";
}) {
  const barCls = accent === "amber" ? "bg-amber-400" : "bg-gray-300";
  return (
    <div className="flex items-start gap-3 rounded-lg border border-gray-200 p-3">
      <div className={cn("mt-0.5 h-full w-1 rounded-full self-stretch", barCls)} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-gray-900">{candidate.name}</p>
            <p className="text-xs text-gray-500">
              {candidate.monthly_rent || "Rent unknown"} · {candidate.district || "—"}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            <Badge tone={recommendationTone(candidate.top_recommendation)}>
              {recommendationLabel(candidate.top_recommendation)}
            </Badge>
            <DecisionConfidenceBadge value={candidate.decision_confidence} />
            {userDecisionLabel(candidate.user_decision) && (
              <Badge tone={userDecisionTone(candidate.user_decision)}>
                {userDecisionLabel(candidate.user_decision)}
              </Badge>
            )}
          </div>
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-gray-600">{candidate.decision_explanation}</p>
        <EvidenceSummary summary={candidate.evidence_summary} />
        {candidate.open_blocker && (
          <p className="mt-1 text-xs text-amber-700">
            <AlertTriangle className="inline h-3 w-3 mr-0.5" />
            {candidate.open_blocker}
          </p>
        )}
        <Link
          href={`/projects/${projectId}/candidates/${candidate.candidate_id}`}
          className="mt-1 inline-block text-xs font-medium text-primary-600 hover:text-primary-700"
        >
          Detail →
        </Link>
      </div>
    </div>
  );
}

export default function ComparePage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const candidateIds = useMemo(() => {
    const raw = searchParams.get("ids");
    if (!raw) return [];
    return raw
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
  }, [searchParams]);

  const [project, setProject] = useState<Project | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const selectionError =
    candidateIds.length < 2
      ? "Select at least two candidates from the dashboard before opening compare."
      : null;

  const orderedCards = useMemo(() => {
    if (!comparison) return [];
    const allCards = [
      ...(comparison.groups.best_current_option ? [comparison.groups.best_current_option] : []),
      ...comparison.groups.viable_alternatives,
      ...comparison.groups.not_ready_for_fair_comparison,
      ...comparison.groups.likely_drop,
    ];
    const cardMap = new Map(allCards.map((card) => [card.candidate_id, card]));
    return candidateIds.map((id) => cardMap.get(id)).filter(Boolean) as CompareCandidateCard[];
  }, [comparison, candidateIds]);

  const loadCompare = useCallback(
    async (token: string) => {
      try {
        const [projectData, compareData] = await Promise.all([
          getProject(token, projectId),
          compareCandidates(token, projectId, candidateIds),
        ]);
        setProject(projectData);
        setComparison(compareData);
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load compare workspace.";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [candidateIds, projectId]
  );

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    if (candidateIds.length < 2) {
      return;
    }

    void loadCompare(token);
  }, [candidateIds.length, loadCompare, router]);

  const updateCompareSet = (nextIds: string[]) => {
    if (nextIds.length < 2) {
      return;
    }
    router.push(`/projects/${projectId}/compare?ids=${encodeURIComponent(nextIds.join(","))}`);
  };

  if (loading && !selectionError) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-sm text-gray-500">Building compare workspace...</div>
      </main>
    );
  }

  const tertiaryCount =
    (comparison?.groups.not_ready_for_fair_comparison.length ?? 0) +
    (comparison?.groups.likely_drop.length ?? 0);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-6xl px-4 py-6 lg:px-6 lg:py-8">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              href={`/projects/${projectId}`}
              className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            >
              <ChevronLeft className="h-4 w-4" />
              Back to dashboard
            </Link>
            <div className="mt-2 flex items-center gap-2">
              <ArrowLeftRight className="h-5 w-5 text-gray-500" />
              <h1 className="text-2xl font-semibold text-gray-900">Compare shortlist</h1>
            </div>
            <p className="mt-1 text-sm text-gray-600">
              {project ? `Decision workspace for ${project.title}.` : "Decision workspace."}
            </p>
          </div>
        </header>

        {selectionError || error || !comparison ? (
          <Card className="mt-6 p-6">
            <p className="text-sm text-gray-700">
              {selectionError || error || "Unable to build the compare workspace."}
            </p>
            <Link
              href={`/projects/${projectId}`}
              className="mt-3 inline-block text-sm font-medium text-primary-600 hover:text-primary-700"
            >
              ← Back to dashboard
            </Link>
          </Card>
        ) : (
          <>
            <section className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-xs text-gray-500">
                Compare set: {candidateIds.length} / {MAX_COMPARE_CANDIDATES}
              </span>
              {orderedCards.map((card) => (
                <div
                  key={card.candidate_id}
                  className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-2.5 py-1 text-sm"
                >
                  <span className="text-gray-800">{card.name}</span>
                  <button
                    type="button"
                    onClick={() =>
                      updateCompareSet(candidateIds.filter((id) => id !== card.candidate_id))
                    }
                    disabled={candidateIds.length <= 2}
                    className={cn(
                      "rounded-full p-0.5",
                      candidateIds.length <= 2
                        ? "text-gray-300 cursor-not-allowed"
                        : "text-gray-400 hover:bg-gray-100 hover:text-gray-700"
                    )}
                    aria-label={`Remove ${card.name}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
              {candidateIds.length <= 2 && (
                <span className="text-xs text-gray-400">
                  Keep ≥2 candidates here — swap from the dashboard.
                </span>
              )}
            </section>

            <Card className="mt-4 border-violet-200 bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-violet-700">
                Agent briefing · {comparison.selected_count} candidate
                {comparison.selected_count > 1 ? "s" : ""}
              </p>
              <h2 className="mt-2 text-lg font-semibold text-gray-900">
                {comparison.summary.headline}
              </h2>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Current take
                  </p>
                  <p className="mt-0.5 text-sm leading-6 text-gray-800">
                    {comparison.agent_briefing.current_take}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Why now
                  </p>
                  <p className="mt-0.5 text-sm leading-6 text-gray-800">
                    {comparison.agent_briefing.why_now}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    What could change
                  </p>
                  <p className="mt-0.5 text-sm leading-6 text-gray-800">
                    {comparison.agent_briefing.what_could_change}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Today&apos;s move
                  </p>
                  <p className="mt-0.5 text-sm leading-6 text-gray-800">
                    {comparison.agent_briefing.today_s_move}
                  </p>
                </div>
              </div>
              {comparison.agent_briefing.confidence_note && (
                <p className="mt-3 text-xs italic text-gray-500">
                  {comparison.agent_briefing.confidence_note}
                </p>
              )}
            </Card>

            <Card className="mt-4 border-gray-200 bg-gray-50 p-5">
              <h2 className="text-sm font-semibold text-gray-900">
                How to read this comparison
              </h2>
              <p className="mt-1 text-xs leading-5 text-gray-600">
                This is a working snapshot, not a final verdict. Unknown information is not treated as a negative.
              </p>
              <div className="mt-3 grid gap-3 text-xs leading-5 text-gray-700 sm:grid-cols-3">
                <div>
                  <p className="font-semibold text-gray-900">Current lead</p>
                  <p>Strongest option with the evidence available today, not a final decision.</p>
                </div>
                <div>
                  <p className="font-semibold text-gray-900">Decision confidence</p>
                  <p>How much to trust the current assessment, not how good the home is.</p>
                </div>
                <div>
                  <p className="font-semibold text-gray-900">Evidence status</p>
                  <p>Supported is clear, Mixed includes inference, and Needs confirmation means unknown or conflicting information.</p>
                </div>
              </div>
            </Card>

            <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="min-w-0 space-y-6">
                {comparison.groups.best_current_option && (
                  <BestOptionHero
                    candidate={comparison.groups.best_current_option}
                    projectId={projectId}
                  />
                )}

                {comparison.groups.viable_alternatives.length > 0 && (
                  <section>
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-semibold text-gray-900">
                          Viable alternatives
                        </h3>
                        <p className="text-xs text-gray-500">
                          Close on paper but not the top pick yet.
                        </p>
                      </div>
                      <Badge tone="neutral">
                        {comparison.groups.viable_alternatives.length}
                      </Badge>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {comparison.groups.viable_alternatives.map((candidate) => (
                        <AlternativeCard
                          key={candidate.candidate_id}
                          candidate={candidate}
                          projectId={projectId}
                        />
                      ))}
                    </div>
                  </section>
                )}

                {tertiaryCount > 0 && (
                  <details className="group rounded-xl border border-gray-200 bg-white shadow-sm">
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 hover:bg-gray-50">
                      <div>
                        <h3 className="text-sm font-semibold text-gray-900">
                          Not ready · Likely drop
                        </h3>
                        <p className="text-xs text-gray-500">
                          Parked or ruled out for now. Expand to review.
                        </p>
                      </div>
                      <Badge tone="neutral">{tertiaryCount}</Badge>
                    </summary>
                    <div className="space-y-4 border-t border-gray-100 p-5">
                      {comparison.groups.not_ready_for_fair_comparison.length > 0 && (
                        <div>
                          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                            Not ready for fair comparison
                          </p>
                          <div className="space-y-2">
                            {comparison.groups.not_ready_for_fair_comparison.map((candidate) => (
                              <TertiaryCard
                                key={candidate.candidate_id}
                                candidate={candidate}
                                projectId={projectId}
                                accent="amber"
                              />
                            ))}
                          </div>
                        </div>
                      )}
                      {comparison.groups.likely_drop.length > 0 && (
                        <div>
                          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                            Likely drop
                          </p>
                          <div className="space-y-2">
                            {comparison.groups.likely_drop.map((candidate) => (
                              <TertiaryCard
                                key={candidate.candidate_id}
                                candidate={candidate}
                                projectId={projectId}
                                accent="gray"
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </details>
                )}

                <Card className="p-5">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-gray-500" />
                    <h3 className="text-sm font-semibold text-gray-900">
                      Key differences to keep in mind
                    </h3>
                  </div>
                  {comparison.key_differences.length === 0 ? (
                    <p className="mt-3 text-sm text-gray-500">
                      No standout differences yet. Add more evidence to candidates.
                    </p>
                  ) : (
                    <div className="mt-3 divide-y divide-gray-100">
                      {comparison.key_differences.map((difference) => {
                        const Icon = differenceIcon(difference.category);
                        return (
                          <div
                            key={difference.category}
                            className="flex items-start gap-3 py-3 first:pt-0 last:pb-0"
                          >
                            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-gray-100 text-gray-600">
                              <Icon className="h-3.5 w-3.5" />
                            </div>
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-medium text-gray-900">
                                  {difference.title}
                                </p>
                                <EvidenceStatusBadge value={difference.evidence_status} />
                              </div>
                              <p className="mt-0.5 text-sm leading-6 text-gray-600">
                                {difference.summary}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </Card>
              </div>

              <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
                <Card className="p-5">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-gray-500" />
                    <h3 className="text-sm font-semibold text-gray-900">
                      Recommended next actions
                    </h3>
                  </div>

                  <div className="mt-4 space-y-4 text-sm">
                    <div>
                      <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        <MessageSquare className="h-3 w-3" /> Contact first
                      </p>
                      {comparison.recommended_next_actions.contact_first ? (
                        <div className="mt-1">
                          <p className="font-medium text-gray-900">
                            {comparison.recommended_next_actions.contact_first.name}
                          </p>
                          <p className="mt-0.5 text-xs leading-5 text-gray-600">
                            {comparison.recommended_next_actions.contact_first.reason}
                          </p>
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-gray-500">
                          No single contact target stands out yet.
                        </p>
                      )}
                    </div>

                    <div>
                      <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        <Eye className="h-3 w-3" /> Viewing candidate
                      </p>
                      {comparison.recommended_next_actions.viewing_candidate ? (
                        <div className="mt-1">
                          <p className="font-medium text-gray-900">
                            {comparison.recommended_next_actions.viewing_candidate.name}
                          </p>
                          <p className="mt-0.5 text-xs leading-5 text-gray-600">
                            {comparison.recommended_next_actions.viewing_candidate.reason}
                          </p>
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-gray-500">
                          No candidate is clearly ready for a viewing yet.
                        </p>
                      )}
                    </div>

                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Questions to ask
                      </p>
                      {comparison.recommended_next_actions.questions_to_ask.length > 0 ? (
                        <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-5 text-gray-700 marker:text-gray-300">
                          {comparison.recommended_next_actions.questions_to_ask.map((question) => (
                            <li key={question}>{question}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-1 text-xs text-gray-500">
                          No urgent follow-ups right now.
                        </p>
                      )}
                    </div>

                    {comparison.recommended_next_actions.deprioritize.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                          Deprioritize
                        </p>
                        <div className="mt-1 space-y-1.5">
                          {comparison.recommended_next_actions.deprioritize.map((candidate) => (
                            <div key={candidate.candidate_id} className="text-xs">
                              <span className="font-medium text-gray-900">{candidate.name}</span>
                              <span className="text-gray-600"> · {candidate.reason}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </Card>

                <Link
                  href={`/projects/${projectId}`}
                  className="block text-center text-xs text-gray-500 hover:text-gray-700"
                >
                  ← Back to dashboard to swap candidates
                </Link>
              </aside>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
