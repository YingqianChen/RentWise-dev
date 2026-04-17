"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeftRight,
  CheckCircle2,
  ChevronLeft,
  Clock,
  Compass,
  Crown,
  DollarSign,
  Eye,
  MapPin,
  MessageSquare,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";

import { compareCandidates, getProject } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type {
  CompareCandidateCard,
  ComparisonResponse,
  Project,
} from "@/lib/types";

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
      return "Shortlist";
    case "likely_reject":
      return "Likely reject";
    default:
      return "Not ready";
  }
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

function differenceIcon(category: string) {
  const key = category.toLowerCase();
  if (key.includes("cost") || key.includes("rent") || key.includes("budget")) return DollarSign;
  if (key.includes("commute") || key.includes("location")) return MapPin;
  if (key.includes("clause") || key.includes("risk")) return AlertTriangle;
  if (key.includes("time") || key.includes("move")) return Clock;
  if (key.includes("fit") || key.includes("match")) return Compass;
  return TrendingUp;
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
            <Badge tone="blue">{actionLabel(candidate.next_action)}</Badge>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-gray-700">{candidate.decision_explanation}</p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {candidate.benchmark?.status === "available" && (
            <div className="rounded-lg bg-emerald-50/60 p-3">
              <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
                <TrendingUp className="h-3 w-3" /> District benchmark
              </p>
              <p className="mt-1 text-sm text-gray-800">
                HKD {candidate.benchmark.median_monthly_rent?.toLocaleString()} median in{" "}
                {candidate.benchmark.district}
              </p>
              {candidate.benchmark.record_note === "fewer_than_10_records" && (
                <p className="mt-0.5 text-xs text-amber-700">Fewer than 10 records.</p>
              )}
            </div>
          )}
          {candidate.commute_evidence?.status === "ready" && (
            <div className="rounded-lg bg-blue-50/60 p-3">
              <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
                <MapPin className="h-3 w-3" /> Commute
              </p>
              <p className="mt-1 text-sm text-gray-800">
                {candidate.commute_evidence.estimated_minutes} min (
                {candidate.commute_evidence.mode})
                {candidate.commute_evidence.destination_label &&
                  ` · ${candidate.commute_evidence.destination_label}`}
              </p>
              {candidate.commute_evidence.confidence_note && (
                <p className="mt-0.5 text-xs text-amber-700">
                  {candidate.commute_evidence.confidence_note}
                </p>
              )}
            </div>
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
        <Badge tone={recommendationTone(candidate.top_recommendation)}>
          {recommendationLabel(candidate.top_recommendation)}
        </Badge>
      </div>

      <p className="mt-2 text-xs leading-5 text-gray-600 line-clamp-3">
        {candidate.decision_explanation}
      </p>

      <div className="mt-2 space-y-1.5 text-xs text-gray-700">
        {candidate.commute_evidence?.status === "ready" && (
          <div className="flex items-center gap-1.5">
            <MapPin className="h-3 w-3 text-gray-400" />
            {candidate.commute_evidence.estimated_minutes} min
            {candidate.commute_evidence.destination_label &&
              ` · ${candidate.commute_evidence.destination_label}`}
          </div>
        )}
        {candidate.benchmark?.status === "available" &&
          candidate.benchmark.median_monthly_rent !== undefined && (
            <div className="flex items-center gap-1.5">
              <TrendingUp className="h-3 w-3 text-gray-400" />
              Median HKD {candidate.benchmark.median_monthly_rent?.toLocaleString()}
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
          <Badge tone={recommendationTone(candidate.top_recommendation)}>
            {recommendationLabel(candidate.top_recommendation)}
          </Badge>
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-gray-600">{candidate.decision_explanation}</p>
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

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    if (candidateIds.length < 2) {
      setLoading(false);
      setError("Select at least two candidates from the dashboard before opening compare.");
      return;
    }

    void loadCompare(token);
  }, [candidateIds, projectId, router]);

  const loadCompare = async (token: string) => {
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
  };

  const updateCompareSet = (nextIds: string[]) => {
    if (nextIds.length < 2) {
      return;
    }
    router.push(`/projects/${projectId}/compare?ids=${encodeURIComponent(nextIds.join(","))}`);
  };

  if (loading) {
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

        {error || !comparison ? (
          <Card className="mt-6 p-6">
            <p className="text-sm text-gray-700">
              {error || "Unable to build the compare workspace."}
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
              <span className="text-xs text-gray-500">Compare set:</span>
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

            <Card className="mt-4 border-violet-200 bg-gradient-to-br from-violet-50 via-white to-white p-5">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-violet-600" />
                <p className="text-xs font-semibold uppercase tracking-wider text-violet-700">
                  Agent briefing · {comparison.selected_count} candidate
                  {comparison.selected_count > 1 ? "s" : ""}
                </p>
              </div>
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
                    Today's move
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
                              <p className="text-sm font-medium text-gray-900">
                                {difference.title}
                              </p>
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
                        <ul className="mt-1.5 space-y-1.5">
                          {comparison.recommended_next_actions.questions_to_ask.map((question) => (
                            <li key={question} className="flex gap-2 text-xs leading-5 text-gray-700">
                              <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-gray-400" />
                              <span>{question}</span>
                            </li>
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
