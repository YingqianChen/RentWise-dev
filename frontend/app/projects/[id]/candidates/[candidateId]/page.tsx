"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import {
  compareCandidates,
  deleteCandidate,
  generateCandidateContactPlan,
  getCandidates,
  getCandidate,
  reassessCandidate,
  rejectCandidate,
  shortlistCandidate,
  updateCandidate,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import type {
  BenchmarkEvidence,
  Candidate,
  CandidateContactPlan,
  CompareCandidateCard,
  ComparisonResponse,
  DecisionSignal,
} from "@/lib/types";

function actionLabel(action?: string | null) {
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
      return "Needs review";
  }
}

function recommendationLabel(value?: string | null) {
  switch (value) {
    case "shortlist_recommendation":
      return "Shortlist recommendation";
    case "likely_reject":
      return "Likely reject";
    default:
      return "Not ready";
  }
}

function recommendationTone(value?: string | null) {
  switch (value) {
    case "shortlist_recommendation":
      return "bg-green-100 text-green-800 border-green-200";
    case "likely_reject":
      return "bg-red-100 text-red-800 border-red-200";
    default:
      return "bg-yellow-100 text-yellow-800 border-yellow-200";
  }
}

function riskLabel(flag?: string | null) {
  switch (flag) {
    case "none":
      return "Low";
    case "high_risk":
      return "High";
    case "over_budget":
      return "Over budget";
    case "hidden_cost_risk":
      return "Hidden cost risk";
    case "possible_additional_cost":
      return "Possible extra cost";
    case "needs_confirmation":
      return "Needs confirmation";
    default:
      return "Unknown";
  }
}

function confidenceLabel(level?: string | null) {
  switch (level) {
    case "high":
      return "High";
    case "medium":
      return "Medium";
    default:
      return "Low";
  }
}

function repairResponsibilityLabel(level?: string | null) {
  switch (level) {
    case "clear":
      return "Clear";
    case "supported_but_unconfirmed":
      return "Positive signal, still unconfirmed";
    case "tenant_heavy":
      return "Tenant-heavy";
    case "unclear":
      return "Unclear";
    default:
      return "Unknown";
  }
}

function leaseTermLabel(level?: string | null) {
  switch (level) {
    case "standard":
      return "Looks broadly standard";
    case "rigid":
      return "More rigid than ideal";
    case "unstable":
      return "Too unstable right now";
    default:
      return "Still unclear";
  }
}

function leaseTermDescription(level?: string | null) {
  switch (level) {
    case "standard":
      return "The lease wording looks close to a normal rental arrangement.";
    case "rigid":
      return "The lease may lock you in more tightly or give you less flexibility than you want.";
    case "unstable":
      return "The arrangement looks short-term or too loose to rely on yet.";
    default:
      return "You still need clearer wording on lease length, break terms, or renewal.";
  }
}

function moveInTimingLabel(level?: string | null) {
  switch (level) {
    case "fit":
      return "Timing looks workable";
    case "mismatch":
      return "Timing may not fit";
    default:
      return "Timing still uncertain";
  }
}

function moveInTimingDescription(level?: string | null) {
  switch (level) {
    case "fit":
      return "The current availability signal looks compatible with your target timing.";
    case "mismatch":
      return "The stated availability looks later than your target timing, so it may block this option.";
    default:
      return "The earliest realistic move-in date still needs confirmation.";
  }
}

function processingStageLabel(stage?: string | null) {
  switch (stage) {
    case "queued":
      return "Queued for background analysis";
    case "running_ocr":
      return "Running OCR on uploaded images";
    case "extracting":
      return "Extracting details and generating assessment";
    case "failed":
      return "Import needs attention";
    default:
      return "Processing";
  }
}

function processingStageDescription(stage?: string | null) {
  switch (stage) {
    case "queued":
      return "The candidate was created successfully and is waiting for the in-app background worker to begin.";
    case "running_ocr":
      return "RentWise is reading the uploaded screenshots now. This stage is usually the slowest on larger images.";
    case "extracting":
      return "OCR finished. RentWise is now extracting fields and generating the decision guidance.";
    case "failed":
      return "The background import stopped before a usable assessment was produced.";
    default:
      return "RentWise is still processing this candidate in the background.";
  }
}

function benchmarkStatusCopy(benchmark: BenchmarkEvidence) {
  switch (benchmark.status) {
    case "no_benchmark_record":
      return "No district benchmark record is available for this candidate yet.";
    case "no_district":
      return "District is still missing, so benchmark context is unavailable.";
    default:
      return "This listing does not look like an SDU, so the SDU benchmark is not shown.";
  }
}

function buildCompareSetIds(comparison: ComparisonResponse): string[] {
  return [
    ...(comparison.groups.best_current_option ? [comparison.groups.best_current_option.candidate_id] : []),
    ...comparison.groups.viable_alternatives.map((item) => item.candidate_id),
    ...comparison.groups.not_ready_for_fair_comparison.map((item) => item.candidate_id),
    ...comparison.groups.likely_drop.map((item) => item.candidate_id),
  ];
}

function buildCompareSetNames(comparison: ComparisonResponse): string[] {
  return [
    ...(comparison.groups.best_current_option ? [comparison.groups.best_current_option.name] : []),
    ...comparison.groups.viable_alternatives.map((item) => item.name),
    ...comparison.groups.not_ready_for_fair_comparison.map((item) => item.name),
    ...comparison.groups.likely_drop.map((item) => item.name),
  ];
}

function buildDecisionBlockers(candidate: Candidate): string[] {
  const blockers: string[] = [];
  const cost = candidate.cost_assessment;
  const clause = candidate.clause_assessment;
  const signals = candidate.extracted_info?.decision_signals ?? [];

  if (cost?.cost_risk_flag === "hidden_cost_risk") {
    blockers.push("The real monthly cost is still incomplete.");
  }
  if (clause?.repair_responsibility_level === "supported_but_unconfirmed") {
    blockers.push("Repair support looks promising, but the final responsibility is still not explicit.");
  } else if (clause?.repair_responsibility_level && ["unknown", "unclear", "tenant_heavy"].includes(clause.repair_responsibility_level)) {
    blockers.push("Repair responsibility is still too unclear.");
  }
  if (clause?.lease_term_level && ["unknown", "rigid", "unstable"].includes(clause.lease_term_level)) {
    blockers.push("Lease flexibility still needs confirmation.");
  }
  if (clause?.move_in_date_level && ["unknown", "uncertain", "mismatch"].includes(clause.move_in_date_level)) {
    blockers.push("Move-in timing may still break the fit.");
  }
  for (const signal of signals) {
    if (signal.key === "holding_fee_risk") {
      blockers.push("Payment handling looks risky and needs written confirmation.");
    } else if (signal.key === "trust_concern" || signal.key === "agent_pressure") {
      blockers.push("The current agent interaction adds trust pressure to this option.");
    } else if (signal.key === "source_conflict" || signal.key === "listing_ambiguity") {
      blockers.push("Core facts still conflict across the listing, chat, or notes.");
    } else if (signal.key === "bathroom_sharing") {
      blockers.push("Bathroom arrangement may be less private than expected.");
    }
  }

  return blockers.slice(0, 3);
}

function signalCategoryLabel(category: string) {
  switch (category) {
    case "fit":
      return "Fit";
    case "building":
      return "Building";
    case "condition":
      return "Condition";
    case "living_arrangement":
      return "Living";
    case "conflict":
      return "Conflict";
    case "trust":
      return "Trust";
    case "cost":
      return "Cost";
    case "timing":
      return "Timing";
    default:
      return "Signal";
  }
}

function signalSourceLabel(source: string) {
  switch (source) {
    case "listing":
      return "Listing";
    case "chat":
      return "Chat";
    case "note":
      return "Notes";
    case "ocr":
      return "OCR";
    default:
      return "Mixed";
  }
}

function signalTone(category: string) {
  switch (category) {
    case "trust":
    case "conflict":
      return "bg-red-50 border-red-200";
    case "cost":
    case "timing":
    case "living_arrangement":
      return "bg-amber-50 border-amber-200";
    default:
      return "bg-gray-50 border-gray-200";
  }
}

export default function CandidateDetailPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;
  const candidateId = params.candidateId as string;

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState<"shortlist" | "reject" | "delete" | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [contactPlan, setContactPlan] = useState<CandidateContactPlan | null>(null);
  const [contactPlanLoading, setContactPlanLoading] = useState(false);
  const [contactPlanError, setContactPlanError] = useState("");
  const [contactPlanCopied, setContactPlanCopied] = useState(false);
  const [compareContext, setCompareContext] = useState<{
    comparison: ComparisonResponse;
    card: CompareCandidateCard;
  } | null>(null);
  const [formState, setFormState] = useState({
    name: "",
    raw_listing_text: "",
    raw_chat_text: "",
    raw_note_text: "",
  });
  const isProcessing =
    candidate?.processing_stage !== null &&
    candidate?.processing_stage !== undefined &&
    !["completed", "failed"].includes(candidate.processing_stage);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    void loadCandidate(token);
  }, [candidateId, router]);

  useEffect(() => {
    const token = getToken();
    if (!token || !isProcessing) {
      return;
    }

    const interval = window.setInterval(() => {
      void loadCandidate(token);
    }, 3000);

    return () => window.clearInterval(interval);
  }, [isProcessing, candidateId, projectId]);

  const loadCandidate = async (token: string) => {
    try {
      const [data, candidatesData] = await Promise.all([
        getCandidate(token, projectId, candidateId),
        getCandidates(token, projectId),
      ]);
      setCandidate(data);
      setFormState({
        name: data.name,
        raw_listing_text: data.raw_listing_text ?? "",
        raw_chat_text: data.raw_chat_text ?? "",
        raw_note_text: data.raw_note_text ?? "",
      });
      setContactPlan(null);
      setContactPlanError("");
      setContactPlanCopied(false);
      const compareIds = buildSuggestedCompareIds(candidatesData.candidates, data.id);
      try {
        if (compareIds.length >= 2) {
          const comparison = await compareCandidates(token, projectId, compareIds);
          const card = findCompareCardForCandidate(comparison, data.id);
          setCompareContext(card ? { comparison, card } : null);
        } else {
          setCompareContext(null);
        }
      } catch (compareError) {
        console.error("Failed to load compare context:", compareError);
        setCompareContext(null);
      }
    } catch (err) {
      console.error("Failed to load candidate:", err);
      router.push(`/projects/${projectId}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action: "shortlist" | "reject") => {
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    try {
      const apiCall = action === "shortlist" ? shortlistCandidate : rejectCandidate;
      const updated = await apiCall(token, projectId, candidateId);
      setCandidate(updated);
      setShowConfirm(null);
      await loadCandidate(token);
    } catch (err) {
      console.error(`Failed to ${action}:`, err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReassess = async () => {
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    try {
      const updated = await reassessCandidate(token, projectId, candidateId);
      setCandidate(updated);
      await loadCandidate(token);
    } catch (err) {
      console.error("Failed to reassess candidate:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    setSaveError("");

    try {
      const updated = await updateCandidate(token, projectId, candidateId, {
        name: formState.name.trim() || candidate?.name,
        raw_listing_text: formState.raw_listing_text,
        raw_chat_text: formState.raw_chat_text,
        raw_note_text: formState.raw_note_text,
      });
      setCandidate(updated);
      setFormState({
        name: updated.name,
        raw_listing_text: updated.raw_listing_text ?? "",
        raw_chat_text: updated.raw_chat_text ?? "",
        raw_note_text: updated.raw_note_text ?? "",
      });
      setIsEditing(false);
      await loadCandidate(token);
    } catch (err) {
      console.error("Failed to update candidate:", err);
      setSaveError(err instanceof Error ? err.message : "Failed to update candidate.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleEditCancel = () => {
    if (!candidate) return;
    setFormState({
      name: candidate.name,
      raw_listing_text: candidate.raw_listing_text ?? "",
      raw_chat_text: candidate.raw_chat_text ?? "",
      raw_note_text: candidate.raw_note_text ?? "",
    });
    setSaveError("");
    setIsEditing(false);
  };

  const handleDelete = async () => {
    const token = getToken();
    if (!token) return;

    setActionLoading(true);
    setSaveError("");
    try {
      await deleteCandidate(token, projectId, candidateId);
      router.push(`/projects/${projectId}`);
    } catch (err) {
      console.error("Failed to delete candidate:", err);
      setSaveError(err instanceof Error ? err.message : "Failed to delete candidate.");
    } finally {
      setActionLoading(false);
      setShowConfirm(null);
    }
  };

  const handleGenerateContactPlan = async () => {
    const token = getToken();
    if (!token) return;

    setContactPlanLoading(true);
    setContactPlanError("");
    setContactPlanCopied(false);
    try {
      const plan = await generateCandidateContactPlan(token, projectId, candidateId);
      setContactPlan(plan);
    } catch (err) {
      console.error("Failed to generate contact plan:", err);
      setContactPlanError(err instanceof Error ? err.message : "Failed to generate contact plan.");
    } finally {
      setContactPlanLoading(false);
    }
  };

  const handleCopyContactDraft = async () => {
    if (!contactPlan?.message_draft) return;

    try {
      await navigator.clipboard.writeText(contactPlan.message_draft);
      setContactPlanCopied(true);
      window.setTimeout(() => setContactPlanCopied(false), 1800);
    } catch (err) {
      console.error("Failed to copy contact draft:", err);
      setContactPlanError("Could not copy the message draft. Please copy it manually.");
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading candidate...</div>
      </main>
    );
  }

  if (!candidate) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Candidate not found.</div>
      </main>
    );
  }

  const extracted = candidate.extracted_info;
  const cost = candidate.cost_assessment;
  const clause = candidate.clause_assessment;
  const assessment = candidate.candidate_assessment;
  const benchmark = candidate.benchmark;
  const decisionBlockers = buildDecisionBlockers(candidate);

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <Link
            href={`/projects/${projectId}`}
            className="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-block"
          >
            Back to project
          </Link>
          <div className="flex justify-between items-start gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{candidate.name}</h1>
              <p className="text-sm text-gray-600 mt-1">
                Review this candidate as a decision task, not just a data record.
              </p>
            </div>
            <div className="flex gap-2 flex-wrap justify-end">
              <button
                onClick={() => {
                  setSaveError("");
                  setIsEditing((current) => !current);
                }}
                disabled={actionLoading || isProcessing}
                className="px-4 py-2 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition disabled:opacity-50"
              >
                {isEditing ? "Close editor" : "Edit candidate"}
              </button>
              <button
                onClick={handleReassess}
                disabled={actionLoading || isProcessing}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
              >
                Reassess
              </button>
              {candidate.user_decision === "undecided" ? (
                <>
                  <button
                    onClick={() => setShowConfirm("shortlist")}
                    disabled={isProcessing}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50"
                  >
                    Shortlist
                  </button>
                  <button
                    onClick={() => setShowConfirm("reject")}
                    disabled={isProcessing}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => setShowConfirm("delete")}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
                  >
                    Delete
                  </button>
                </>
              ) : (
                <div className="flex items-center gap-3">
                  <span
                    className={`px-3 py-1 rounded-lg text-sm ${
                      candidate.user_decision === "shortlisted"
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {candidate.user_decision === "shortlisted" ? "Shortlisted" : "Rejected"}
                  </span>
                  <button
                    onClick={() => setShowConfirm("delete")}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {candidate.processing_stage && candidate.processing_stage !== "completed" && (
          <section
            className={`rounded-lg border p-5 mb-6 ${
              candidate.processing_stage === "failed"
                ? "bg-red-50 border-red-200"
                : "bg-blue-50 border-blue-200"
            }`}
          >
            <p
              className={`text-sm font-medium uppercase tracking-[0.18em] mb-2 ${
                candidate.processing_stage === "failed" ? "text-red-700" : "text-blue-700"
              }`}
            >
              {processingStageLabel(candidate.processing_stage)}
            </p>
            <p className={`${candidate.processing_stage === "failed" ? "text-red-900" : "text-blue-900"} leading-7`}>
              {candidate.processing_error || processingStageDescription(candidate.processing_stage)}
            </p>
            {candidate.processing_stage !== "failed" && (
              <p className="text-sm text-blue-700 mt-3">
                This page refreshes automatically while the background import is still running.
              </p>
            )}
          </section>
        )}

        {showConfirm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-md">
              <h2 className="text-xl font-bold mb-4">
                {showConfirm === "shortlist"
                  ? "Confirm shortlist"
                  : showConfirm === "reject"
                    ? "Confirm rejection"
                    : "Delete candidate"}
              </h2>
              <p className="text-gray-600 mb-6">
                {showConfirm === "shortlist"
                  ? "Add this candidate to your shortlist?"
                  : showConfirm === "reject"
                    ? "Mark this candidate as rejected? You can reassess it later if needed."
                    : "Delete this candidate and all related assessments from the project? This cannot be undone."}
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowConfirm(null)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-900"
                >
                  Cancel
                </button>
                <button
                  onClick={() =>
                    showConfirm === "delete" ? void handleDelete() : void handleAction(showConfirm)
                  }
                  disabled={actionLoading}
                  className={`px-4 py-2 text-white rounded-lg ${
                    showConfirm === "shortlist"
                      ? "bg-green-600 hover:bg-green-700"
                      : showConfirm === "reject"
                        ? "bg-red-600 hover:bg-red-700"
                        : "bg-gray-900 hover:bg-black"
                  }`}
                >
                  {actionLoading
                    ? showConfirm === "delete"
                      ? "Deleting..."
                      : "Working..."
                    : showConfirm === "delete"
                      ? "Confirm delete"
                      : "Confirm"}
                </button>
              </div>
            </div>
          </div>
        )}

        {assessment && (
          <section className="bg-primary-50 border border-primary-200 rounded-lg p-6 mb-6">
            <div className="grid lg:grid-cols-[1.15fr_0.85fr] gap-6">
              <div>
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${recommendationTone(
                      assessment.top_level_recommendation
                    )}`}
                  >
                    {recommendationLabel(assessment.top_level_recommendation)}
                  </span>
                  <span className="inline-flex items-center rounded-full border border-primary-200 bg-white px-3 py-1 text-sm text-primary-900">
                    Next move: {actionLabel(assessment.next_best_action)}
                  </span>
                </div>
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary-700 mb-2">Decision snapshot</p>
                <h2 className="text-2xl font-semibold text-primary-950">What matters now</h2>
                <p className="text-primary-900 mt-3 leading-7">{assessment.summary}</p>
                {assessment.labels.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    {assessment.labels.map((label) => (
                      <span key={label} className="text-xs bg-white text-primary-800 px-2 py-1 rounded-full border border-primary-200">
                        {label}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="grid sm:grid-cols-3 lg:grid-cols-1 gap-3">
                <div className="rounded-lg border border-primary-200 bg-white/80 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-primary-700">Confidence</p>
                  <p className="mt-2 text-lg font-semibold text-primary-950">{confidenceLabel(assessment.recommendation_confidence)}</p>
                </div>
                <div className="rounded-lg border border-primary-200 bg-white/80 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-primary-700">Decision risk</p>
                  <p className="mt-2 text-lg font-semibold text-primary-950">{confidenceLabel(assessment.decision_risk_level)}</p>
                </div>
                <div className="rounded-lg border border-primary-200 bg-white/80 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-primary-700">Known monthly cost</p>
                  <p className="mt-2 text-lg font-semibold text-primary-950">
                    {cost?.known_monthly_cost ? `HKD ${cost.known_monthly_cost.toLocaleString()}` : "Unknown"}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 border-t border-primary-200 pt-5 grid lg:grid-cols-[1fr_0.72fr] gap-5">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary-700 mb-2">
                  Current decision blockers
                </p>
                {decisionBlockers.length > 0 ? (
                  <ul className="space-y-2 text-sm text-primary-950">
                    {decisionBlockers.map((blocker) => (
                      <li key={blocker} className="flex gap-2">
                        <span className="text-primary-400">*</span>
                        <span>{blocker}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-primary-900">
                    No single blocker dominates right now, so this decision is mainly about whether the current fit is strong enough to pursue.
                  </p>
                )}
              </div>
              <div className="rounded-lg border border-primary-200 bg-white/70 px-4 py-4">
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary-700 mb-2">
                  Keep the page light
                </p>
                <p className="text-sm text-primary-900 leading-7">
                  If you need to contact the landlord or agent, use the outreach draft below. Benchmark notes, OCR text, and deeper assessment evidence stay secondary until you need them.
                </p>
              </div>
            </div>
          </section>
        )}

        {compareContext && (
          <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mb-2">
                  Current compare context
                </p>
                <h2 className="text-xl font-semibold text-gray-900">
                  {compareContext.comparison.summary.headline}
                </h2>
                <p className="text-gray-700 mt-2">{compareContext.card.decision_explanation}</p>
                <div className="flex flex-wrap gap-2 mt-3">
                  {buildCompareSetNames(compareContext.comparison).map((name) => (
                    <span key={name} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full">
                      {name}
                    </span>
                  ))}
                </div>
                <p className="text-sm text-gray-600 mt-3">
                  Main tradeoff: {compareContext.card.main_tradeoff}
                </p>
                {compareContext.card.open_blocker && (
                  <p className="text-sm text-gray-600 mt-1">
                    Open blocker: {compareContext.card.open_blocker}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Link
                  href={`/projects/${projectId}/compare?ids=${encodeURIComponent(
                    buildCompareSetIds(compareContext.comparison).join(",")
                  )}`}
                  className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-black transition whitespace-nowrap text-center"
                >
                  Open compare workspace
                </Link>
                <Link
                  href={`/projects/${projectId}`}
                  className="text-sm text-primary-600 hover:text-primary-700 text-center"
                >
                  Choose different candidates
                </Link>
              </div>
            </div>
          </section>
        )}

        <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
            <div className="max-w-2xl">
              <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mb-2">
                Ask agent / landlord
              </p>
              <h2 className="text-xl font-semibold text-gray-900">Draft the next message only when you need it</h2>
              <p className="text-gray-700 mt-2 leading-7">
                This uses the current assessment to turn your open questions into a short outreach plan, instead of repeating the whole analysis again.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {contactPlan && (
                <button
                  onClick={handleCopyContactDraft}
                  className="px-4 py-2 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition whitespace-nowrap"
                >
                  {contactPlanCopied ? "Copied" : "Copy message"}
                </button>
              )}
              <button
                onClick={handleGenerateContactPlan}
                disabled={contactPlanLoading || isProcessing}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50 whitespace-nowrap"
              >
                {contactPlanLoading ? "Drafting..." : contactPlan ? "Refresh draft" : "Draft outreach"}
              </button>
            </div>
          </div>

          {contactPlanError && <p className="text-sm text-red-600 mt-4">{contactPlanError}</p>}

          {contactPlan && (
            <div className="mt-5 border-t border-gray-200 pt-5 grid lg:grid-cols-[0.95fr_1.2fr] gap-5">
              <div className="rounded-lg bg-gray-50 border border-gray-200 p-4">
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mb-2">
                  Contact goal
                </p>
                <p className="text-sm text-gray-800 leading-7">{contactPlan.contact_goal}</p>

                <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mt-5 mb-2">
                  Best questions to ask
                </p>
                <ol className="space-y-3 text-sm text-gray-700">
                  {contactPlan.questions.map((question, index) => (
                    <li key={question} className="flex gap-3">
                      <span className="text-xs font-semibold text-gray-400 pt-0.5">{index + 1}.</span>
                      <span>{question}</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="rounded-lg bg-gray-50 border border-gray-200 p-4">
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mb-2">
                  English message draft
                </p>
                <p className="text-xs text-gray-500 mb-3">
                  Keep this lightweight, then edit tone or details before sending.
                </p>
                <p className="text-sm text-gray-800 leading-7 whitespace-pre-wrap">{contactPlan.message_draft}</p>
              </div>
            </div>
          )}
        </section>

        {candidate.commute_evidence && (
          <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mb-2">Commute estimate</p>
            {candidate.commute_evidence.status === "ready" ? (
              <>
                <h2 className="text-xl font-semibold text-gray-900">
                  {candidate.commute_evidence.estimated_minutes} min to {candidate.commute_evidence.destination_label}
                </h2>
                <p className="text-sm text-gray-600 mt-2">
                  Mode: {candidate.commute_evidence.mode}
                  {candidate.commute_evidence.route_summary && ` — ${candidate.commute_evidence.route_summary}`}
                </p>
                {candidate.commute_evidence.confidence_note && (
                  <p className="text-sm text-amber-700 mt-2">{candidate.commute_evidence.confidence_note}</p>
                )}
              </>
            ) : candidate.commute_evidence.status === "not_configured" ? (
              <p className="text-sm text-gray-600">
                Add a commute destination in project settings to see travel estimates.
              </p>
            ) : candidate.commute_evidence.status === "insufficient_candidate_location" ? (
              <p className="text-sm text-gray-600">
                Commute unavailable: location not precise enough. Edit the candidate to add an address or building name.
              </p>
            ) : (
              <p className="text-sm text-gray-600">
                {candidate.commute_evidence.confidence_note || "Commute calculation failed."}
              </p>
            )}
          </section>
        )}

        {benchmark && (
          <details className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <summary className="cursor-pointer">
              <p className="text-lg font-semibold text-gray-900">Benchmark context</p>
              <p className="text-sm text-gray-500 mt-1">
                Open this only when district-level SDU pricing would meaningfully change your read.
              </p>
            </summary>
            <div className="mt-4">
              <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mb-2">
                SDU district benchmark
              </p>
            {benchmark.status === "available" ? (
              <>
                <h2 className="text-xl font-semibold text-gray-900">
                  Median rent in {benchmark.district}: HKD {benchmark.median_monthly_rent?.toLocaleString()}
                </h2>
                <p className="text-sm text-gray-600 mt-2">
                  {benchmark.source_period} | HKD {benchmark.median_monthly_rent_per_sqm?.toLocaleString()} per sq m per month
                </p>
                {benchmark.fit_note && <p className="text-sm text-gray-700 mt-3">{benchmark.fit_note}</p>}
                {benchmark.record_note === "fewer_than_10_records" && (
                  <p className="text-sm text-amber-700 mt-3">Based on fewer than 10 rental records.</p>
                )}
                <p className="text-sm text-gray-500 mt-3">{benchmark.disclaimer}</p>
              </>
            ) : (
              <>
                <p className="text-sm text-gray-700">{benchmarkStatusCopy(benchmark)}</p>
                <p className="text-sm text-gray-500 mt-3">
                  For subdivided units only. General reference, not property-specific.
                </p>
              </>
            )}
            </div>
          </details>
        )}

        {isEditing && (
          <section className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Edit candidate</h2>
                <p className="text-sm text-gray-600 mt-1">
                  Update the source text and we will rerun extraction and assessment.
                </p>
              </div>
            </div>
            <form className="space-y-4" onSubmit={handleEditSave}>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Candidate name</label>
                <input
                  type="text"
                  value={formState.name}
                  onChange={(e) => setFormState((current) => ({ ...current, name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="Candidate name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Listing text</label>
                <textarea
                  value={formState.raw_listing_text}
                  onChange={(e) =>
                    setFormState((current) => ({ ...current, raw_listing_text: e.target.value }))
                  }
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="Paste the listing description here."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Chat transcript</label>
                <textarea
                  value={formState.raw_chat_text}
                  onChange={(e) =>
                    setFormState((current) => ({ ...current, raw_chat_text: e.target.value }))
                  }
                  rows={5}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="Paste agent or landlord messages here."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  value={formState.raw_note_text}
                  onChange={(e) =>
                    setFormState((current) => ({ ...current, raw_note_text: e.target.value }))
                  }
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="Add anything you observed or want to remember."
                />
              </div>
              {saveError && <p className="text-sm text-red-600">{saveError}</p>}
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={handleEditCancel}
                  className="px-4 py-2 text-gray-600 hover:text-gray-900"
                  disabled={actionLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {actionLoading ? "Saving..." : "Save and reassess"}
                </button>
              </div>
            </form>
          </section>
        )}

        <section className="mt-6 space-y-4">
          {candidate.source_assets.length > 0 && (
            <details className="bg-white rounded-lg border border-gray-200 p-6">
              <summary className="cursor-pointer">
                <p className="text-lg font-semibold text-gray-900">OCR evidence</p>
                <p className="text-sm text-gray-500 mt-1">
                  Inspect the raw text from each uploaded file before you question the downstream extraction.
                </p>
              </summary>
              <div className="space-y-4 mt-4">
                {candidate.source_assets.map((asset) => (
                  <div key={asset.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                      <div>
                        <p className="font-medium text-gray-900">{asset.original_filename}</p>
                        <p className="text-sm text-gray-500">
                          {asset.file_size ? `${Math.round(asset.file_size / 1024)} KB` : "Unknown size"}
                        </p>
                      </div>
                      <span
                        className={`text-xs px-2.5 py-1 rounded-full ${
                          asset.ocr_status === "succeeded"
                            ? "bg-green-100 text-green-700"
                            : asset.ocr_status === "failed"
                              ? "bg-red-100 text-red-700"
                              : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        OCR {asset.ocr_status}
                      </span>
                    </div>
                    {asset.ocr_text ? (
                      <pre className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-3 rounded-lg overflow-auto max-h-64">
                        {asset.ocr_text}
                      </pre>
                    ) : (
                      <p className="text-sm text-gray-600">
                        No OCR text was saved for this file.
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}

          <details className="bg-white rounded-lg border border-gray-200 p-6">
            <summary className="cursor-pointer">
              <p className="text-lg font-semibold text-gray-900">Supporting assessment details</p>
              <p className="text-sm text-gray-500 mt-1">
                Open the deeper cost, clause, and extraction context only when you need to inspect why the decision looks this way.
              </p>
            </summary>
            <div className="grid md:grid-cols-2 gap-6 mt-4">
              {cost && (
                <section>
                  <h2 className="text-base font-semibold text-gray-900 mb-4">Cost view</h2>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-sm text-gray-600">Known monthly cost</div>
                      <div className="text-xl font-semibold">
                        {cost.known_monthly_cost ? `HKD ${cost.known_monthly_cost.toLocaleString()}` : "Unknown"}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Confidence</div>
                      <div className="text-xl font-semibold">{confidenceLabel(cost.monthly_cost_confidence)}</div>
                    </div>
                  </div>
                  <div className="mb-4">
                    <div className="text-sm text-gray-600">Cost risk</div>
                    <div className="text-lg font-medium">{riskLabel(cost.cost_risk_flag)}</div>
                  </div>
                  <p className="text-sm text-gray-700">{cost.summary}</p>
                  {cost.monthly_cost_missing_items.length > 0 && (
                    <div className="mt-4">
                      <div className="text-sm text-gray-600 mb-1">Missing cost fields</div>
                      <div className="flex flex-wrap gap-2">
                        {cost.monthly_cost_missing_items.map((item) => (
                          <span key={item} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-full">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </section>
              )}

              {clause && (
                <section>
                  <h2 className="text-base font-semibold text-gray-900 mb-4">Clause view</h2>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-sm text-gray-600">Repair responsibility</div>
                      <div className="text-lg font-medium">{repairResponsibilityLabel(clause.repair_responsibility_level)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Lease term</div>
                      <div className="text-lg font-medium">{leaseTermLabel(clause.lease_term_level)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Move-in timing</div>
                      <div className="text-lg font-medium">{moveInTimingLabel(clause.move_in_date_level)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-600">Clause confidence</div>
                      <div className="text-lg font-medium">{confidenceLabel(clause.clause_confidence)}</div>
                    </div>
                  </div>
                  <div className="space-y-2 mb-4">
                    <p className="text-sm text-gray-700">
                      <span className="font-medium text-gray-900">Lease read:</span> {leaseTermDescription(clause.lease_term_level)}
                    </p>
                    <p className="text-sm text-gray-700">
                      <span className="font-medium text-gray-900">Timing read:</span> {moveInTimingDescription(clause.move_in_date_level)}
                    </p>
                  </div>
                  <div className="mb-4">
                    <div className="text-sm text-gray-600">Clause risk</div>
                    <div className="text-lg font-medium">{riskLabel(clause.clause_risk_flag)}</div>
                  </div>
                  <p className="text-sm text-gray-700">{clause.summary}</p>
                </section>
              )}
            </div>
          </details>

          <details className="bg-white rounded-lg border border-gray-200 p-6">
            <summary className="text-lg font-semibold text-gray-900 cursor-pointer">
              Structured listing details
            </summary>
            <dl className="grid md:grid-cols-2 gap-x-8 gap-y-3 mt-4">
              {extracted?.monthly_rent && (
                <>
                  <dt className="text-gray-600">Monthly rent</dt>
                  <dd className="font-medium text-gray-900">{extracted.monthly_rent}</dd>
                </>
              )}
              {extracted?.district && (
                <>
                  <dt className="text-gray-600">District</dt>
                  <dd className="font-medium text-gray-900">{extracted.district}</dd>
                </>
              )}
              {extracted?.deposit && (
                <>
                  <dt className="text-gray-600">Deposit</dt>
                  <dd className="text-gray-900">{extracted.deposit}</dd>
                </>
              )}
              {extracted?.agent_fee && (
                <>
                  <dt className="text-gray-600">Agent fee</dt>
                  <dd className="text-gray-900">{extracted.agent_fee}</dd>
                </>
              )}
              {extracted?.management_fee_amount && (
                <>
                  <dt className="text-gray-600">Management fee</dt>
                  <dd className="text-gray-900">
                    {extracted.management_fee_amount}
                    {extracted.management_fee_included === true
                      ? " (included)"
                      : extracted.management_fee_included === false
                        ? " (separate)"
                        : ""}
                  </dd>
                </>
              )}
              {extracted?.lease_term && (
                <>
                  <dt className="text-gray-600">Lease term</dt>
                  <dd className="text-gray-900">{extracted.lease_term}</dd>
                </>
              )}
              {extracted?.move_in_date && (
                <>
                  <dt className="text-gray-600">Move-in date</dt>
                  <dd className="text-gray-900">{extracted.move_in_date}</dd>
                </>
              )}
              {extracted?.furnished && (
                <>
                  <dt className="text-gray-600">Furnishing</dt>
                  <dd className="text-gray-900">{extracted.furnished}</dd>
                </>
              )}
              {extracted?.size_sqft && (
                <>
                  <dt className="text-gray-600">Size</dt>
                  <dd className="text-gray-900">{extracted.size_sqft} sqft</dd>
                </>
              )}
            </dl>
          </details>

          {extracted && extracted.decision_signals.length > 0 && (
            <details className="bg-white rounded-lg border border-gray-200 p-6">
              <summary className="text-lg font-semibold text-gray-900 cursor-pointer">
                Decision signals
              </summary>
              <div className="mt-4 space-y-3">
                {extracted.decision_signals.map((signal: DecisionSignal, index) => (
                  <div
                    key={`${signal.key}-${index}`}
                    className={`rounded-lg border p-4 ${signalTone(signal.category)}`}
                  >
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="text-sm font-medium text-gray-900">{signal.label}</span>
                      <span className="text-xs text-gray-600 bg-white/70 border border-gray-200 px-2 py-0.5 rounded-full">
                        {signalCategoryLabel(signal.category)}
                      </span>
                      <span className="text-xs text-gray-600 bg-white/70 border border-gray-200 px-2 py-0.5 rounded-full">
                        {signalSourceLabel(signal.source)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700">{signal.evidence}</p>
                    {signal.note && <p className="text-sm text-gray-600 mt-2">{signal.note}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}

          {candidate.combined_text && (
            <details className="bg-white rounded-lg border border-gray-200 p-6">
              <summary className="text-lg font-semibold text-gray-900 cursor-pointer">
                Source text
              </summary>
              <pre className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-4 rounded-lg overflow-auto max-h-64 mt-4">
                {candidate.combined_text}
              </pre>
            </details>
          )}
        </section>
      </div>
    </main>
  );
}

function buildSuggestedCompareIds(candidates: Candidate[], anchorCandidateId: string): string[] {
  const anchor = candidates.find((candidate) => candidate.id === anchorCandidateId);
  if (!anchor) return [];

  const others = candidates
    .filter((candidate) => candidate.id !== anchorCandidateId && candidate.user_decision !== "rejected" && candidate.candidate_assessment)
    .sort((a, b) => compareSuggestionScore(b) - compareSuggestionScore(a))
    .slice(0, 3)
    .map((candidate) => candidate.id);

  return [anchorCandidateId, ...others];
}

function compareSuggestionScore(candidate: Candidate): number {
  const assessment = candidate.candidate_assessment;
  if (!assessment) return 0;

  let score = 0;
  if (candidate.user_decision === "shortlisted") score += 8;
  if (assessment.top_level_recommendation === "shortlist_recommendation") score += 6;
  if (assessment.next_best_action === "schedule_viewing") score += 5;
  if (assessment.next_best_action === "keep_warm") score += 3;
  if (assessment.next_best_action === "verify_clause") score += 2;
  if (assessment.potential_value_level === "high") score += 3;
  if (assessment.recommendation_confidence === "high") score += 2;
  return score;
}

function findCompareCardForCandidate(
  comparison: ComparisonResponse,
  candidateId: string
): CompareCandidateCard | null {
  const pools = [
    comparison.groups.best_current_option ? [comparison.groups.best_current_option] : [],
    comparison.groups.viable_alternatives,
    comparison.groups.not_ready_for_fair_comparison,
    comparison.groups.likely_drop,
  ];

  for (const pool of pools) {
    const match = pool.find((candidate) => candidate.candidate_id === candidateId);
    if (match) return match;
  }

  return null;
}

