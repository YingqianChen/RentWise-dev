"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { compareCandidates, getProject } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type {
  CompareCandidateCard,
  ComparisonResponse,
  Project,
} from "@/lib/types";

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
      return "Shortlist recommendation";
    case "likely_reject":
      return "Likely reject";
    default:
      return "Not ready";
  }
}

function recommendationTone(value: string) {
  switch (value) {
    case "shortlist_recommendation":
      return "bg-green-100 text-green-800 border-green-200";
    case "likely_reject":
      return "bg-red-100 text-red-800 border-red-200";
    default:
      return "bg-yellow-100 text-yellow-800 border-yellow-200";
  }
}

function groupHeading(group: CompareCandidateCard["compare_group"]) {
  switch (group) {
    case "best_current_option":
      return "Best current option";
    case "viable_alternative":
      return "Viable alternative";
    case "likely_drop":
      return "Likely drop";
    default:
      return "Not ready for fair comparison";
  }
}

function CompareCard({
  candidate,
  projectId,
}: {
  candidate: CompareCandidateCard;
  projectId: string;
}) {
  const [showMore, setShowMore] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-400 mb-2">
            {groupHeading(candidate.compare_group)}
          </p>
          <h3 className="text-lg font-semibold text-gray-900">{candidate.name}</h3>
          <p className="text-sm text-gray-600 mt-1">
            {candidate.monthly_rent || "Rent unknown"} / {candidate.district || "District unknown"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 justify-end">
          <span className={`text-xs border px-2 py-1 rounded-full ${recommendationTone(candidate.top_recommendation)}`}>
            {recommendationLabel(candidate.top_recommendation)}
          </span>
          <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full">
            {actionLabel(candidate.next_action)}
          </span>
        </div>
      </div>

      <div className="mt-4 space-y-3 text-sm">
        <div>
          <p className="font-medium text-gray-900">Why it is here</p>
          <p className="text-gray-700 mt-1">{candidate.decision_explanation}</p>
        </div>
        {candidate.benchmark?.status === "available" && (
          <div>
            <p className="font-medium text-gray-900">SDU district benchmark</p>
            <p className="text-gray-700 mt-1">
              HKD {candidate.benchmark.median_monthly_rent?.toLocaleString()} median in {candidate.benchmark.district}
              {" · "}
              {candidate.benchmark.source_period}
            </p>
            {candidate.benchmark.record_note === "fewer_than_10_records" && (
              <p className="text-amber-700 mt-1">Based on fewer than 10 rental records.</p>
            )}
          </div>
        )}
        {candidate.commute_evidence?.status === "ready" && (
          <div>
            <p className="font-medium text-gray-900">Commute</p>
            <p className="text-gray-700 mt-1">
              {candidate.commute_evidence.estimated_minutes} min ({candidate.commute_evidence.mode})
              {candidate.commute_evidence.destination_label && ` to ${candidate.commute_evidence.destination_label}`}
            </p>
            {candidate.commute_evidence.confidence_note && (
              <p className="text-amber-700 mt-1">{candidate.commute_evidence.confidence_note}</p>
            )}
          </div>
        )}
        {showMore && (
          <>
            <div>
              <p className="font-medium text-gray-900">Main tradeoff</p>
              <p className="text-gray-700 mt-1">{candidate.main_tradeoff}</p>
            </div>
            {candidate.open_blocker && (
              <div>
                <p className="font-medium text-gray-900">Open blocker</p>
                <p className="text-gray-700 mt-1">{candidate.open_blocker}</p>
              </div>
            )}
          </>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setShowMore((current) => !current)}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          {showMore ? "Show less" : "Show more"}
        </button>
        <Link
          href={`/projects/${projectId}/candidates/${candidate.candidate_id}`}
          className="text-sm text-primary-600 hover:text-primary-700"
        >
          Open candidate detail
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

  const visibleDifferences = comparison?.key_differences.slice(0, 2) ?? [];

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
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Building compare workspace...</div>
      </main>
    );
  }

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <Link href={`/projects/${projectId}`} className="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-block">
            Back to dashboard
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Compare shortlist</h1>
          <p className="text-sm text-gray-600 mt-1">
            {project ? `Decision workspace for ${project.title}.` : "Decision workspace for the selected compare set."}
          </p>
        </div>

        {error || !comparison ? (
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <p className="text-gray-700">{error || "Unable to build the compare workspace."}</p>
          </div>
        ) : (
          <div className="space-y-8">
            <section className="bg-primary-50 border border-primary-200 rounded-xl p-6">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-primary-700 mb-2">Agent briefing</p>
              <h2 className="text-2xl font-semibold text-primary-900">{comparison.summary.headline}</h2>
              <p className="text-sm text-primary-800 mt-3">
                Comparing {comparison.selected_count} candidate{comparison.selected_count > 1 ? "s" : ""}.
              </p>
              <div className="grid gap-4 lg:grid-cols-2 mt-5">
                <div>
                  <p className="text-sm font-medium text-primary-950">Current take</p>
                  <p className="text-primary-900 mt-1 leading-7">{comparison.agent_briefing.current_take}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-primary-950">Why now</p>
                  <p className="text-primary-900 mt-1 leading-7">{comparison.agent_briefing.why_now}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-primary-950">What could change</p>
                  <p className="text-primary-900 mt-1 leading-7">{comparison.agent_briefing.what_could_change}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-primary-950">Today's move</p>
                  <p className="text-primary-900 mt-1 leading-7">{comparison.agent_briefing.today_s_move}</p>
                </div>
              </div>
              <p className="text-sm text-primary-800 mt-4">{comparison.agent_briefing.confidence_note}</p>
            </section>

            <section className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Compare set</h2>
                  <p className="text-sm text-gray-600 mt-1">
                    Remove candidates here when you want a tighter compare set. Go back to the dashboard to add different ones.
                  </p>
                </div>
                <Link
                  href={`/projects/${projectId}`}
                  className="text-sm text-primary-600 hover:text-primary-700 whitespace-nowrap"
                >
                  Back to dashboard to add or swap
                </Link>
              </div>
              <div className="flex flex-wrap gap-2 mt-4">
                {orderedCards.map((card) => (
                  <div
                    key={card.candidate_id}
                    className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-2"
                  >
                    <span className="text-sm text-gray-800">{card.name}</span>
                    <button
                      type="button"
                      onClick={() => updateCompareSet(candidateIds.filter((id) => id !== card.candidate_id))}
                      disabled={candidateIds.length <= 2}
                      className={`text-xs ${
                        candidateIds.length <= 2
                          ? "text-gray-300 cursor-not-allowed"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              {candidateIds.length <= 2 && (
                <p className="text-sm text-gray-500 mt-3">
                  Keep at least two candidates here. If you want to swap one out, go back to the dashboard and choose a different set.
                </p>
              )}
            </section>

            <section className="grid gap-6">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Decision groups</h2>
                <p className="text-sm text-gray-600 mt-1">
                  This workspace groups candidates by decision readiness and tradeoff quality instead of forcing a fake exact ranking.
                </p>
              </div>

              {comparison.groups.best_current_option && (
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-gray-900">Best current option</h3>
                  <CompareCard candidate={comparison.groups.best_current_option} projectId={projectId} />
                </div>
              )}

              {comparison.groups.viable_alternatives.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-gray-900">Viable alternatives</h3>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {comparison.groups.viable_alternatives.map((candidate) => (
                      <CompareCard key={candidate.candidate_id} candidate={candidate} projectId={projectId} />
                    ))}
                  </div>
                </div>
              )}

              {comparison.groups.not_ready_for_fair_comparison.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-gray-900">Not ready for fair comparison</h3>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {comparison.groups.not_ready_for_fair_comparison.map((candidate) => (
                      <CompareCard key={candidate.candidate_id} candidate={candidate} projectId={projectId} />
                    ))}
                  </div>
                </div>
              )}

              {comparison.groups.likely_drop.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-lg font-semibold text-gray-900">Likely drop</h3>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {comparison.groups.likely_drop.map((candidate) => (
                      <CompareCard key={candidate.candidate_id} candidate={candidate} projectId={projectId} />
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="grid lg:grid-cols-[1.05fr_0.95fr] gap-6">
              <div className="bg-white border border-gray-200 rounded-xl p-6">
                <h2 className="text-lg font-semibold text-gray-900">Recommended next actions</h2>
                <div className="space-y-5 mt-4 text-sm text-gray-700">
                  <div>
                    <p className="font-medium text-gray-900">Contact first</p>
                    {comparison.recommended_next_actions.contact_first ? (
                      <p className="mt-1">
                        <span className="font-medium">{comparison.recommended_next_actions.contact_first.name}</span>
                        {" - "}
                        {comparison.recommended_next_actions.contact_first.reason}
                      </p>
                    ) : (
                      <p className="mt-1">No single contact target stands out yet.</p>
                    )}
                  </div>

                  <div>
                    <p className="font-medium text-gray-900">Questions to ask next</p>
                    {comparison.recommended_next_actions.questions_to_ask.length > 0 ? (
                      <ul className="mt-2 space-y-2">
                        {comparison.recommended_next_actions.questions_to_ask.map((question) => (
                          <li key={question} className="flex gap-2">
                            <span className="text-gray-400">*</span>
                            <span>{question}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1">There are no urgent follow-up questions right now.</p>
                    )}
                  </div>

                  <div>
                    <p className="font-medium text-gray-900">Viewing candidate</p>
                    {comparison.recommended_next_actions.viewing_candidate ? (
                      <p className="mt-1">
                        <span className="font-medium">{comparison.recommended_next_actions.viewing_candidate.name}</span>
                        {" - "}
                        {comparison.recommended_next_actions.viewing_candidate.reason}
                      </p>
                    ) : (
                      <p className="mt-1">No selected candidate is clearly ready for a viewing yet.</p>
                    )}
                  </div>

                  <div>
                    <p className="font-medium text-gray-900">Candidates to deprioritize</p>
                    {comparison.recommended_next_actions.deprioritize.length > 0 ? (
                      <div className="mt-2 space-y-2">
                        {comparison.recommended_next_actions.deprioritize.map((candidate) => (
                          <p key={candidate.candidate_id}>
                            <span className="font-medium">{candidate.name}</span>
                            {" - "}
                            {candidate.reason}
                          </p>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-1">Nothing needs to be pushed out of the compare set immediately.</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6">
                <h2 className="text-lg font-semibold text-gray-900">Key differences to keep in mind</h2>
                <p className="text-sm text-gray-600 mt-1">
                  Keep this short list in view while you make the tradeoff call.
                </p>
                <div className="space-y-4 mt-4">
                  {visibleDifferences.map((difference) => (
                    <div key={difference.category}>
                      <p className="font-medium text-gray-900">{difference.title}</p>
                      <p className="text-sm text-gray-700 mt-1">{difference.summary}</p>
                    </div>
                  ))}
                  {visibleDifferences.length === 0 && (
                    <p className="text-sm text-gray-500">No key differences stand out yet.</p>
                  )}
                </div>
              </div>
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
