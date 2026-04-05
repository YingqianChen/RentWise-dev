"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { deleteCandidate, getCandidates, getDashboard, getProject, updateProject } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Candidate, Dashboard, InvestigationItem, Project } from "@/lib/types";

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

function decisionLabel(decision: Candidate["user_decision"]) {
  switch (decision) {
    case "shortlisted":
      return "Shortlisted";
    case "rejected":
      return "Rejected";
    default:
      return "Undecided";
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

function priorityLabel(priority: InvestigationItem["priority"]) {
  switch (priority) {
    case "high":
      return "High";
    case "medium":
      return "Medium";
    default:
      return "Low";
  }
}

function processingStageLabel(stage?: Candidate["processing_stage"]) {
  switch (stage) {
    case "queued":
      return "Queued";
    case "running_ocr":
      return "Running OCR";
    case "extracting":
      return "Assessing";
    case "failed":
      return "Needs attention";
    default:
      return "Processing";
  }
}

function processingStageDescription(candidate: Candidate) {
  switch (candidate.processing_stage) {
    case "queued":
      return "This import has been accepted and is waiting for the background worker to begin.";
    case "running_ocr":
      return "OCR is still reading the uploaded screenshots, so the extracted fields are not ready yet.";
    case "extracting":
      return "OCR is done. RentWise is turning the text into structured details and decision guidance now.";
    case "failed":
      return candidate.processing_error || "The import stopped before a usable assessment was produced.";
    default:
      return candidate.processing_error || "This candidate is still being processed.";
  }
}

export default function ProjectDashboardPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingBudget, setEditingBudget] = useState(false);
  const [budgetInput, setBudgetInput] = useState("");
  const [budgetSaving, setBudgetSaving] = useState(false);
  const [budgetError, setBudgetError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Candidate | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [deletingCandidateId, setDeletingCandidateId] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    void loadData(token);
  }, [projectId, router]);

  useEffect(() => {
    const token = getToken();
    if (!token || !candidates.some((candidate) => candidate.processing_stage && candidate.processing_stage !== "completed" && candidate.processing_stage !== "failed")) {
      return;
    }

    const interval = window.setInterval(() => {
      void loadData(token);
    }, 3000);

    return () => window.clearInterval(interval);
  }, [candidates, projectId]);

  const loadData = async (token: string) => {
    try {
      const [projectData, dashboardData, candidatesData] = await Promise.all([
        getProject(token, projectId),
        getDashboard(token, projectId),
        getCandidates(token, projectId),
      ]);

      setProject(projectData);
      setBudgetInput(projectData.max_budget ? String(projectData.max_budget) : "");
      setDashboard(dashboardData);
      setCandidates(candidatesData.candidates);
    } catch (err) {
      console.error("Failed to load project:", err);
      router.push("/projects");
    } finally {
      setLoading(false);
    }
  };

  const groupedItems = useMemo(() => {
    const items = dashboard?.open_investigation_items ?? [];
    return {
      cost: items.filter((item) => item.category === "cost"),
      clause: items.filter((item) => item.category === "clause"),
      timing: items.filter((item) => item.category === "timing"),
      match: items.filter((item) => item.category === "match"),
    };
  }, [dashboard]);

  const compareSelectionLabel = useMemo(() => {
    if (selectedCandidateIds.length === 0) {
      return "Choose candidates to compare";
    }
    if (selectedCandidateIds.length === 1) {
      return "Choose at least one more candidate";
    }
    return `${selectedCandidateIds.length} candidates selected`;
  }, [selectedCandidateIds]);

  const toggleCandidateSelection = (candidateId: string) => {
    setSelectedCandidateIds((current) =>
      current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId]
    );
  };

  const goToCompare = () => {
    if (selectedCandidateIds.length < 2) {
      return;
    }
    const ids = encodeURIComponent(selectedCandidateIds.join(","));
    router.push(`/projects/${projectId}/compare?ids=${ids}`);
  };

  const handleBudgetSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getToken();
    if (!token || !project) return;

    setBudgetSaving(true);
    setBudgetError("");
    try {
      const updated = await updateProject(token, projectId, {
        max_budget: budgetInput.trim() ? parseInt(budgetInput, 10) : undefined,
      });
      setProject(updated);
      setBudgetInput(updated.max_budget ? String(updated.max_budget) : "");
      setEditingBudget(false);
      await loadData(token);
    } catch (err) {
      setBudgetError(err instanceof Error ? err.message : "Failed to update budget.");
    } finally {
      setBudgetSaving(false);
    }
  };

  const handleDeleteCandidate = async () => {
    const token = getToken();
    if (!token || !deleteTarget) return;

    setDeletingCandidateId(deleteTarget.id);
    setDeleteError("");
    try {
      await deleteCandidate(token, projectId, deleteTarget.id);
      setSelectedCandidateIds((current) => current.filter((id) => id !== deleteTarget.id));
      setDeleteTarget(null);
      await loadData(token);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete candidate.");
    } finally {
      setDeletingCandidateId(null);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading workspace...</div>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Project not found.</div>
      </main>
    );
  }

  const stats = dashboard?.stats ?? {
    total: 0,
    new: 0,
    needs_info: 0,
    follow_up: 0,
    high_risk_pending: 0,
    recommended_reject: 0,
    shortlisted: 0,
    rejected: 0,
  };
  const processingCandidates = candidates.filter(
    (candidate) =>
      candidate.processing_stage &&
      candidate.processing_stage !== "completed" &&
      candidate.processing_stage !== "failed"
  );

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        {deleteTarget && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-md">
              <h2 className="text-xl font-bold mb-4">Delete candidate</h2>
              <p className="text-gray-600 mb-6">
                Delete {deleteTarget.name} and all related assessments from this project? This cannot be undone.
              </p>
              {deleteError && <p className="text-sm text-red-600 mb-4">{deleteError}</p>}
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => {
                    setDeleteError("");
                    setDeleteTarget(null);
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-900"
                >
                  Cancel
                </button>
                <button
                  onClick={() => void handleDeleteCandidate()}
                  disabled={deletingCandidateId === deleteTarget.id}
                  className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-black disabled:opacity-50"
                >
                  {deletingCandidateId === deleteTarget.id ? "Deleting..." : "Confirm delete"}
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-between items-center mb-8">
          <div>
            <Link href="/projects" className="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-block">
              Back to projects
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">{project.title}</h1>
            <p className="text-sm text-gray-600 mt-1">
              Candidate-pool workspace for deciding what to verify, follow up, or drop next.
            </p>
            <div className="mt-3">
              {editingBudget ? (
                <form onSubmit={handleBudgetSave} className="flex flex-wrap items-center gap-3">
                  <label className="text-sm text-gray-600">Budget cap (HKD)</label>
                  <input
                    type="number"
                    value={budgetInput}
                    onChange={(e) => setBudgetInput(e.target.value)}
                    className="w-36 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
                    placeholder="22000"
                  />
                  <button
                    type="submit"
                    disabled={budgetSaving}
                    className="px-3 py-2 bg-gray-900 text-white rounded-lg hover:bg-black disabled:opacity-50 text-sm"
                  >
                    {budgetSaving ? "Saving..." : "Save budget"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setBudgetInput(project.max_budget ? String(project.max_budget) : "");
                      setBudgetError("");
                      setEditingBudget(false);
                    }}
                    className="text-sm text-gray-500 hover:text-gray-700"
                  >
                    Cancel
                  </button>
                  {budgetError && <p className="w-full text-sm text-red-600">{budgetError}</p>}
                </form>
              ) : (
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-gray-600">
                    Budget cap: {project.max_budget ? `HKD ${project.max_budget.toLocaleString()}` : "Not set"}
                  </span>
                  <button
                    type="button"
                    onClick={() => setEditingBudget(true)}
                    className="text-primary-600 hover:text-primary-700"
                  >
                    Edit budget
                  </button>
                </div>
              )}
            </div>
          </div>
          <Link
            href={`/projects/${projectId}/import`}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
          >
            Add candidate
          </Link>
        </div>

        {processingCandidates.length > 0 && (
          <section className="bg-blue-50 border border-blue-200 rounded-lg p-5 mb-8">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-blue-700 mb-2">
              Background processing
            </p>
            <p className="text-blue-900 leading-7">
              {processingCandidates.length === 1
                ? `${processingCandidates[0].name} is still being processed in the background.`
                : `${processingCandidates.length} candidates are still being processed in the background.`}
            </p>
            <p className="text-sm text-blue-700 mt-2">
              The dashboard refreshes automatically, and these candidates will move into the normal priority flow once OCR and assessment finish.
            </p>
          </section>
        )}

        {dashboard?.current_advice && (
          <div className="bg-primary-50 border border-primary-200 rounded-lg p-5 mb-8">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary-700 mb-2">Current advice</p>
            <p className="text-primary-900 text-lg leading-7">{dashboard.current_advice}</p>
          </div>
        )}

        {dashboard?.compare_preview && (
          <section className="bg-white rounded-lg border border-gray-200 p-5 mb-8">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500 mb-2">
                  Suggested compare set
                </p>
                <h2 className="text-xl font-semibold text-gray-900">{dashboard.compare_preview.headline}</h2>
                <p className="text-gray-700 mt-2 leading-7">{dashboard.compare_preview.summary}</p>
                <p className="text-sm text-gray-600 mt-3">
                  Candidates: {dashboard.compare_preview.candidate_names.join(", ")}
                </p>
                <p className="text-sm text-gray-600 mt-1">{dashboard.compare_preview.action_prompt}</p>
              </div>
              <button
                type="button"
                onClick={() =>
                  router.push(
                    `/projects/${projectId}/compare?ids=${encodeURIComponent(
                      dashboard.compare_preview?.candidate_ids.join(",") || ""
                    )}`
                  )
                }
                className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-black transition whitespace-nowrap"
              >
                Open suggested compare
              </button>
            </div>
          </section>
        )}

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
            <div className="text-sm text-gray-600">Total candidates</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-yellow-600">{stats.needs_info}</div>
            <div className="text-sm text-gray-600">Need more info</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-blue-600">{stats.follow_up}</div>
            <div className="text-sm text-gray-600">Ready to follow up</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-red-600">{stats.high_risk_pending}</div>
            <div className="text-sm text-gray-600">High-risk pending</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-green-600">{stats.shortlisted}</div>
            <div className="text-sm text-gray-600">Shortlisted</div>
          </div>
        </div>

        <div className="grid lg:grid-cols-[1.15fr_0.85fr] gap-8">
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Priority queue</h2>
              <p className="text-sm text-gray-500">What deserves attention first</p>
            </div>
            {(dashboard?.priority_candidates ?? []).length === 0 ? (
              <div className="bg-white border border-gray-200 rounded-lg p-6 text-sm text-gray-500">
                Add at least one candidate to generate action-oriented recommendations.
              </div>
            ) : (
              <div className="space-y-3">
                {dashboard?.priority_candidates.map((candidate, index) => (
                  <Link
                    key={candidate.id}
                    href={`/projects/${projectId}/candidates/${candidate.id}`}
                    className="block bg-white rounded-lg border border-gray-200 p-5 hover:border-primary-300 transition"
                  >
                    <div className="flex justify-between items-start gap-4">
                      <div>
                        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-400 mb-2">
                          Priority {index + 1}
                        </p>
                        <h3 className="font-semibold text-gray-900">{candidate.name}</h3>
                        <p className="text-sm text-gray-600 mt-1">
                          {candidate.monthly_rent || "Rent unknown"} / {candidate.district || "District unknown"}
                        </p>
                        <p className="text-sm text-gray-700 mt-3">{candidate.reason}</p>
                      </div>
                      <span className="text-xs bg-blue-100 text-blue-700 px-2.5 py-1 rounded-full whitespace-nowrap">
                        {actionLabel(candidate.next_best_action)}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Investigation checklist</h2>
              <p className="text-sm text-gray-500">The shared blockers that still need attention</p>
            </div>
            <div className="space-y-4">
              {(["cost", "clause", "timing", "match"] as const).map((category) => {
                const items = groupedItems[category];
                if (items.length === 0) return null;

                return (
                  <div key={category} className="bg-white rounded-lg border border-gray-200 p-4">
                    <h3 className="font-medium text-gray-900 capitalize mb-3">{category}</h3>
                    <div className="space-y-3">
                      {items.map((item) => (
                        <div key={item.id} className="border-l-2 border-gray-200 pl-3">
                          <div className="flex justify-between items-start gap-3">
                            <p className="font-medium text-gray-900">{item.title}</p>
                            <span
                              className={`text-xs px-2 py-1 rounded ${
                                item.priority === "high"
                                  ? "bg-red-100 text-red-700"
                                  : item.priority === "medium"
                                    ? "bg-yellow-100 text-yellow-700"
                                    : "bg-gray-100 text-gray-700"
                              }`}
                            >
                              {priorityLabel(item.priority)}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 mt-1">{item.question}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}

              {(dashboard?.open_investigation_items ?? []).length === 0 && (
                <div className="bg-white rounded-lg border border-gray-200 p-6 text-sm text-gray-500">
                  There are no open investigation items right now.
                </div>
              )}
            </div>
          </section>
        </div>

        <section className="mt-8">
          <div className="flex items-center justify-between mb-4 gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">All candidates</h2>
              <p className="text-sm text-gray-500">
                Scan the pool quickly here, then open detail only when you need the deeper reasoning.
              </p>
            </div>
            <div className="flex items-center gap-3 flex-wrap justify-end">
              <span className="text-sm text-gray-500">{compareSelectionLabel}</span>
              {selectedCandidateIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedCandidateIds([])}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Clear
                </button>
              )}
              <button
                type="button"
                onClick={goToCompare}
                disabled={selectedCandidateIds.length < 2}
                className={`px-4 py-2 rounded-lg transition ${
                  selectedCandidateIds.length < 2
                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                    : "bg-gray-900 text-white hover:bg-black"
                }`}
              >
                Compare selected
              </button>
            </div>
          </div>
          {candidates.length === 0 ? (
            <div className="text-center py-10 bg-gray-50 rounded-lg border border-gray-200">
              <p className="text-gray-600 mb-4">No candidates have been added yet.</p>
              <Link href={`/projects/${projectId}/import`} className="text-primary-600 hover:underline">
                Import your first candidate
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {candidates.map((candidate) => (
                <div
                  key={candidate.id}
                  className={`bg-white rounded-lg border p-4 transition ${
                    selectedCandidateIds.includes(candidate.id)
                      ? "border-primary-300 ring-1 ring-primary-100"
                      : "border-gray-200"
                  }`}
                >
                  <div className="flex justify-between items-start gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={selectedCandidateIds.includes(candidate.id)}
                            onChange={() => toggleCandidateSelection(candidate.id)}
                            disabled={Boolean(candidate.processing_stage && candidate.processing_stage !== "completed")}
                            className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                            aria-label={`Select ${candidate.name} for comparison`}
                          />
                          <div>
                            <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-400">
                              Include in compare
                            </p>
                            <h3 className="font-medium text-gray-900 mt-1">{candidate.name}</h3>
                          </div>
                        </div>
                        <Link
                          href={`/projects/${projectId}/candidates/${candidate.id}`}
                          className="text-sm text-primary-600 hover:text-primary-700 whitespace-nowrap"
                        >
                          Open detail
                        </Link>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">
                        {candidate.processing_stage && candidate.processing_stage !== "completed" ? (
                          processingStageDescription(candidate)
                        ) : (
                          <>
                            {candidate.extracted_info?.monthly_rent || "Rent unknown"} /{" "}
                            {candidate.extracted_info?.district || "District unknown"}
                          </>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap justify-end max-w-sm">
                      {candidate.processing_stage && candidate.processing_stage !== "completed" && (
                        <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full">
                          {processingStageLabel(candidate.processing_stage)}
                        </span>
                      )}
                      {candidate.candidate_assessment?.top_level_recommendation && (
                        <span
                          className={`text-xs border px-2 py-1 rounded-full ${recommendationTone(
                            candidate.candidate_assessment.top_level_recommendation
                          )}`}
                        >
                          {recommendationLabel(candidate.candidate_assessment.top_level_recommendation)}
                        </span>
                      )}
                      {candidate.candidate_assessment?.next_best_action && (
                        <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full">
                          {actionLabel(candidate.candidate_assessment.next_best_action)}
                        </span>
                      )}
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${
                          candidate.user_decision === "shortlisted"
                            ? "bg-green-100 text-green-700"
                            : candidate.user_decision === "rejected"
                              ? "bg-red-100 text-red-700"
                              : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {decisionLabel(candidate.user_decision)}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteError("");
                          setDeleteTarget(candidate);
                        }}
                        className="text-xs text-gray-500 hover:text-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
