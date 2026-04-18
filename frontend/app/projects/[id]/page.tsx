"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeftRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Compass,
  DollarSign,
  FileText,
  ListChecks,
  MapPin,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";

import {
  deleteCandidate,
  getCandidates,
  getDashboard,
  getProject,
  updateProject,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Candidate, Dashboard, InvestigationItem, Project } from "@/lib/types";

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

type ButtonVariant = "default" | "outline" | "ghost" | "subtle";
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
        : variant === "subtle"
          ? "bg-gray-100 text-gray-700 hover:bg-gray-200"
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

function decisionTone(decision: Candidate["user_decision"]) {
  switch (decision) {
    case "shortlisted":
      return "emerald" as const;
    case "rejected":
      return "red" as const;
    default:
      return "neutral" as const;
  }
}

function recommendationLabel(value?: string | null) {
  switch (value) {
    case "shortlist_recommendation":
      return "Shortlist";
    case "likely_reject":
      return "Likely reject";
    default:
      return "Not ready";
  }
}

function recommendationTone(value?: string | null) {
  switch (value) {
    case "shortlist_recommendation":
      return "emerald" as const;
    case "likely_reject":
      return "red" as const;
    default:
      return "amber" as const;
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

function priorityTone(priority: InvestigationItem["priority"]) {
  switch (priority) {
    case "high":
      return "red" as const;
    case "medium":
      return "amber" as const;
    default:
      return "neutral" as const;
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
      return "Waiting in the background worker queue.";
    case "running_ocr":
      return "OCR is reading the uploaded screenshots.";
    case "extracting":
      return "Turning OCR text into structured fields and guidance.";
    case "failed":
      return candidate.processing_error || "Import stopped before a usable assessment was produced.";
    default:
      return candidate.processing_error || "This candidate is still being processed.";
  }
}

function categoryIcon(category: InvestigationItem["category"]) {
  switch (category) {
    case "cost":
      return DollarSign;
    case "clause":
      return FileText;
    case "timing":
      return Clock;
    case "match":
      return Compass;
    default:
      return ListChecks;
  }
}

function categoryLabel(category: InvestigationItem["category"]) {
  switch (category) {
    case "cost":
      return "Cost";
    case "clause":
      return "Clauses";
    case "timing":
      return "Timing";
    case "match":
      return "Fit";
    default:
      return category;
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
  const [editingCommute, setEditingCommute] = useState(false);
  const [commuteDestLabel, setCommuteDestLabel] = useState("");
  const [commuteDestQuery, setCommuteDestQuery] = useState("");
  const [commuteMode, setCommuteMode] = useState<"transit" | "driving" | "walking">("transit");
  const [maxCommuteMinutes, setMaxCommuteMinutes] = useState("");
  const [commuteSaving, setCommuteSaving] = useState(false);
  const [commuteError, setCommuteError] = useState("");

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
    if (
      !token ||
      !candidates.some(
        (candidate) =>
          candidate.processing_stage &&
          candidate.processing_stage !== "completed" &&
          candidate.processing_stage !== "failed"
      )
    ) {
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
      setCommuteDestLabel(projectData.commute_destination_label || "");
      setCommuteDestQuery(projectData.commute_destination_query || "");
      setCommuteMode(projectData.commute_mode || "transit");
      setMaxCommuteMinutes(
        projectData.max_commute_minutes ? String(projectData.max_commute_minutes) : ""
      );
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
      return "Pick two or more to compare";
    }
    if (selectedCandidateIds.length === 1) {
      return "Pick at least one more";
    }
    return `${selectedCandidateIds.length} selected`;
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

  const handleCommuteSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getToken();
    if (!token || !project) return;

    setCommuteSaving(true);
    setCommuteError("");
    try {
      const updated = await updateProject(token, projectId, {
        commute_destination_label: commuteDestLabel.trim() || undefined,
        commute_destination_query: commuteDestQuery.trim() || undefined,
        commute_mode: commuteDestQuery.trim() ? commuteMode : undefined,
        max_commute_minutes: maxCommuteMinutes.trim() ? parseInt(maxCommuteMinutes, 10) : undefined,
      });
      setProject(updated);
      setEditingCommute(false);
    } catch (err) {
      setCommuteError(err instanceof Error ? err.message : "Failed to update commute settings.");
    } finally {
      setCommuteSaving(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-sm text-gray-500">Loading workspace...</div>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-sm text-gray-500">Project not found.</div>
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
  const totalBlockers = (dashboard?.open_investigation_items ?? []).length;

  const commuteSummary = project.commute_enabled
    ? `${project.commute_destination_label || project.commute_destination_query} · ${project.commute_mode}${
        project.max_commute_minutes ? ` · max ${project.max_commute_minutes} min` : ""
      }`
    : "Not configured";
  const budgetSummary = project.max_budget
    ? `HKD ${project.max_budget.toLocaleString()}`
    : "Not set";

  return (
    <main className="relative min-h-screen overflow-hidden bg-gray-50">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[360px] bg-gradient-to-br from-violet-100 via-blue-50 to-emerald-50"
      />
      <div className="relative mx-auto max-w-6xl px-4 py-6 lg:px-6 lg:py-8">
        {deleteTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
            <Card className="w-full max-w-md p-6">
              <h2 className="text-lg font-semibold text-gray-900">Delete candidate</h2>
              <p className="mt-2 text-sm text-gray-600">
                Delete <span className="font-medium text-gray-900">{deleteTarget.name}</span> and
                all related assessments from this project? This cannot be undone.
              </p>
              {deleteError && <p className="mt-3 text-sm text-red-600">{deleteError}</p>}
              <div className="mt-5 flex justify-end gap-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setDeleteError("");
                    setDeleteTarget(null);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => void handleDeleteCandidate()}
                  disabled={deletingCandidateId === deleteTarget.id}
                  className="bg-red-600 hover:bg-red-700"
                >
                  {deletingCandidateId === deleteTarget.id ? "Deleting..." : "Confirm delete"}
                </Button>
              </div>
            </Card>
          </div>
        )}

        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              href="/projects"
              className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            >
              <ChevronLeft className="h-4 w-4" />
              Back to projects
            </Link>
            <div className="mt-2 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-900 text-white">
                <Sparkles className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">
                  RentWise · Project
                </p>
                <h1 className="truncate text-2xl font-semibold tracking-tight text-gray-900">
                  {project.title}
                </h1>
              </div>
            </div>
            <p className="mt-2 text-sm text-gray-600">
              Decide what to verify, follow up on, or drop next.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link href={`/projects/${projectId}/compare`}>
              <Button variant="outline" className="gap-1.5">
                <ArrowLeftRight className="h-4 w-4" />
                Compare
              </Button>
            </Link>
            <Link href={`/projects/${projectId}/import`}>
              <Button className="gap-1.5">
                <Plus className="h-4 w-4" />
                Add candidate
              </Button>
            </Link>
          </div>
        </header>

        <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <KpiCard label="Total" value={stats.total} tone="neutral" />
          <KpiCard label="Needs info" value={stats.needs_info} tone="amber" />
          <KpiCard label="Follow up" value={stats.follow_up} tone="blue" />
          <KpiCard label="High risk" value={stats.high_risk_pending} tone="red" />
          <KpiCard label="Shortlisted" value={stats.shortlisted} tone="emerald" />
        </section>

        <section className="mt-4 grid gap-3 md:grid-cols-2">
          <Card className="p-4">
            {editingBudget ? (
              <form onSubmit={handleBudgetSave} className="flex flex-wrap items-end gap-2">
                <label className="flex flex-col gap-1 text-xs text-gray-500">
                  Budget cap (HKD)
                  <input
                    type="number"
                    value={budgetInput}
                    onChange={(e) => setBudgetInput(e.target.value)}
                    className="w-40 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                    placeholder="22000"
                  />
                </label>
                <Button type="submit" size="sm" disabled={budgetSaving}>
                  {budgetSaving ? "Saving..." : "Save"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setBudgetInput(project.max_budget ? String(project.max_budget) : "");
                    setBudgetError("");
                    setEditingBudget(false);
                  }}
                >
                  Cancel
                </Button>
                {budgetError && <p className="w-full text-xs text-red-600">{budgetError}</p>}
              </form>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                    <DollarSign className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-wide text-gray-500">Budget cap</p>
                    <p className="truncate text-sm font-medium text-gray-900">{budgetSummary}</p>
                  </div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setEditingBudget(true)}>
                  <Pencil className="h-3.5 w-3.5" />
                  Edit
                </Button>
              </div>
            )}
          </Card>

          <Card className="p-4">
            {editingCommute ? (
              <form onSubmit={handleCommuteSave} className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <label className="flex flex-col gap-1 text-xs text-gray-500">
                    Destination name
                    <input
                      type="text"
                      value={commuteDestLabel}
                      onChange={(e) => setCommuteDestLabel(e.target.value)}
                      className="w-40 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                      placeholder="e.g. Office"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-gray-500">
                    Destination address
                    <input
                      type="text"
                      value={commuteDestQuery}
                      onChange={(e) => setCommuteDestQuery(e.target.value)}
                      className="w-56 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                      placeholder="e.g. Central, Hong Kong"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-gray-500">
                    Mode
                    <select
                      value={commuteMode}
                      onChange={(e) =>
                        setCommuteMode(e.target.value as "transit" | "driving" | "walking")
                      }
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                    >
                      <option value="transit">Transit</option>
                      <option value="driving">Driving</option>
                      <option value="walking">Walking</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-gray-500">
                    Max minutes
                    <input
                      type="number"
                      value={maxCommuteMinutes}
                      onChange={(e) => setMaxCommuteMinutes(e.target.value)}
                      className="w-24 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                      placeholder="60"
                      min={1}
                      max={180}
                    />
                  </label>
                </div>
                <div className="flex items-center gap-2">
                  <Button type="submit" size="sm" disabled={commuteSaving}>
                    {commuteSaving ? "Saving..." : "Save commute"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setCommuteDestLabel(project.commute_destination_label || "");
                      setCommuteDestQuery(project.commute_destination_query || "");
                      setCommuteMode(project.commute_mode || "transit");
                      setMaxCommuteMinutes(
                        project.max_commute_minutes ? String(project.max_commute_minutes) : ""
                      );
                      setCommuteError("");
                      setEditingCommute(false);
                    }}
                  >
                    Cancel
                  </Button>
                </div>
                {commuteError && <p className="text-xs text-red-600">{commuteError}</p>}
              </form>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                    <MapPin className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-wide text-gray-500">Commute target</p>
                    <p className="truncate text-sm font-medium text-gray-900">{commuteSummary}</p>
                  </div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setEditingCommute(true)}>
                  <Pencil className="h-3.5 w-3.5" />
                  {project.commute_enabled ? "Edit" : "Set up"}
                </Button>
              </div>
            )}
          </Card>
        </section>

        {processingCandidates.length > 0 && (
          <div className="mt-4 flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
            <Clock className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">
                {processingCandidates.length === 1
                  ? `${processingCandidates[0].name} is still being processed.`
                  : `${processingCandidates.length} candidates are still being processed.`}
              </p>
              <p className="mt-0.5 text-blue-800/80">
                The dashboard refreshes automatically once OCR and assessment finish.
              </p>
            </div>
          </div>
        )}

        {dashboard?.current_advice && (
          <div className="mt-4 flex items-start gap-3 rounded-lg border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-violet-700">
                Agent advice
              </p>
              <p className="mt-0.5 leading-6">{dashboard.current_advice}</p>
            </div>
          </div>
        )}

        {dashboard?.compare_preview && (
          <Card className="mt-4 p-5">
            <div className="flex flex-col items-start gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Suggested compare set
                </p>
                <p className="mt-1 text-base font-semibold text-gray-900">
                  {dashboard.compare_preview.headline}
                </p>
                <p className="mt-1 text-sm text-gray-600">
                  {dashboard.compare_preview.candidate_names.join(" · ")}
                </p>
                <p className="mt-1 text-sm text-gray-600">
                  {dashboard.compare_preview.action_prompt}
                </p>
              </div>
              <Button
                onClick={() =>
                  router.push(
                    `/projects/${projectId}/compare?ids=${encodeURIComponent(
                      dashboard.compare_preview?.candidate_ids.join(",") || ""
                    )}`
                  )
                }
                className="gap-1.5"
              >
                <ArrowLeftRight className="h-4 w-4" />
                Open suggested compare
              </Button>
            </div>
          </Card>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0 space-y-6">
            <section>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold text-gray-900">All candidates</h2>
                  <p className="text-sm text-gray-500">
                    Scan, select, and compare. Open detail for the full decision view.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">{compareSelectionLabel}</span>
                  {selectedCandidateIds.length > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedCandidateIds([])}
                    >
                      Clear
                    </Button>
                  )}
                  <Button
                    size="sm"
                    onClick={goToCompare}
                    disabled={selectedCandidateIds.length < 2}
                    className="gap-1.5"
                  >
                    <ArrowLeftRight className="h-4 w-4" />
                    Compare
                  </Button>
                </div>
              </div>

              {candidates.length === 0 ? (
                <Card className="p-8 text-center">
                  <p className="text-sm text-gray-600">No candidates yet.</p>
                  <Link
                    href={`/projects/${projectId}/import`}
                    className="mt-2 inline-block text-sm font-medium text-primary-600 hover:text-primary-700"
                  >
                    Import your first candidate →
                  </Link>
                </Card>
              ) : (
                <div className="space-y-2">
                  {candidates.map((candidate) => {
                    const selected = selectedCandidateIds.includes(candidate.id);
                    const isProcessing =
                      candidate.processing_stage && candidate.processing_stage !== "completed";
                    const rent = candidate.extracted_info?.monthly_rent;
                    const district = candidate.extracted_info?.district;
                    return (
                      <Card
                        key={candidate.id}
                        className={cn(
                          "p-3 transition hover:border-gray-300",
                          selected && "border-primary-300 ring-1 ring-primary-200"
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleCandidateSelection(candidate.id)}
                            disabled={Boolean(isProcessing)}
                            className="mt-1 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                            aria-label={`Select ${candidate.name} for comparison`}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div className="min-w-0">
                                <Link
                                  href={`/projects/${projectId}/candidates/${candidate.id}`}
                                  className="block truncate text-sm font-semibold text-gray-900 hover:text-primary-700"
                                >
                                  {candidate.name}
                                </Link>
                                <p className="mt-0.5 text-xs text-gray-500 truncate">
                                  {isProcessing
                                    ? processingStageDescription(candidate)
                                    : `${rent || "Rent unknown"} · ${district || "District unknown"}`}
                                </p>
                              </div>
                              <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                                {isProcessing && (
                                  <Badge tone="blue">
                                    <Clock className="h-3 w-3" />
                                    {processingStageLabel(candidate.processing_stage)}
                                  </Badge>
                                )}
                                {candidate.candidate_assessment?.top_level_recommendation && (
                                  <Badge
                                    tone={recommendationTone(
                                      candidate.candidate_assessment.top_level_recommendation
                                    )}
                                  >
                                    {recommendationLabel(
                                      candidate.candidate_assessment.top_level_recommendation
                                    )}
                                  </Badge>
                                )}
                                {candidate.candidate_assessment?.next_best_action && (
                                  <Badge tone="blue">
                                    {actionLabel(
                                      candidate.candidate_assessment.next_best_action
                                    )}
                                  </Badge>
                                )}
                                <Badge tone={decisionTone(candidate.user_decision)}>
                                  {decisionLabel(candidate.user_decision)}
                                </Badge>
                              </div>
                            </div>
                            <div className="mt-2 flex items-center justify-end gap-1">
                              <Link
                                href={`/projects/${projectId}/candidates/${candidate.id}`}
                                className="inline-flex items-center gap-0.5 rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-900"
                              >
                                Open detail
                                <ChevronRight className="h-3 w-3" />
                              </Link>
                              <button
                                type="button"
                                onClick={() => {
                                  setDeleteError("");
                                  setDeleteTarget(candidate);
                                }}
                                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-400 hover:bg-red-50 hover:text-red-600"
                              >
                                <Trash2 className="h-3 w-3" />
                                Delete
                              </button>
                            </div>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
            <Card className="p-5">
              <div className="flex items-center gap-2">
                <ListChecks className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-semibold text-gray-900">Priority queue</h3>
              </div>
              <p className="mt-0.5 text-xs text-gray-500">What deserves attention first.</p>
              <div className="mt-3 space-y-2">
                {(dashboard?.priority_candidates ?? []).length === 0 ? (
                  <p className="text-xs text-gray-500">
                    Add a candidate to generate recommendations.
                  </p>
                ) : (
                  dashboard?.priority_candidates.slice(0, 4).map((candidate, index) => (
                    <Link
                      key={candidate.id}
                      href={`/projects/${projectId}/candidates/${candidate.id}`}
                      className="group block rounded-lg border border-gray-200 p-3 hover:border-primary-300 hover:bg-gray-50"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                            #{index + 1}
                          </p>
                          <p className="mt-0.5 truncate text-sm font-medium text-gray-900 group-hover:text-primary-700">
                            {candidate.name}
                          </p>
                          <p className="mt-0.5 line-clamp-2 text-xs text-gray-600">
                            {candidate.reason}
                          </p>
                        </div>
                        <Badge tone="blue">{actionLabel(candidate.next_best_action)}</Badge>
                      </div>
                    </Link>
                  ))
                )}
              </div>
            </Card>

            <Card className="p-5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <h3 className="text-sm font-semibold text-gray-900">Investigation checklist</h3>
                </div>
                {totalBlockers > 0 && <Badge tone="amber">{totalBlockers}</Badge>}
              </div>
              <p className="mt-0.5 text-xs text-gray-500">Shared blockers across candidates.</p>

              {totalBlockers === 0 ? (
                <div className="mt-3 flex items-center gap-2 text-xs text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" />
                  Nothing outstanding right now.
                </div>
              ) : (
                <div className="mt-3 space-y-3">
                  {(["cost", "clause", "timing", "match"] as const).map((category) => {
                    const items = groupedItems[category];
                    if (items.length === 0) return null;
                    const Icon = categoryIcon(category);
                    return (
                      <div key={category}>
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-700">
                          <Icon className="h-3.5 w-3.5 text-gray-500" />
                          {categoryLabel(category)}
                        </div>
                        <ul className="mt-1.5 space-y-1.5">
                          {items.slice(0, 3).map((item) => (
                            <li
                              key={item.id}
                              className="border-l-2 border-gray-200 pl-2.5"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <p className="text-xs font-medium text-gray-900">{item.title}</p>
                                <Badge tone={priorityTone(item.priority)} className="shrink-0">
                                  {priorityLabel(item.priority)}
                                </Badge>
                              </div>
                              <p className="mt-0.5 text-xs text-gray-500">{item.question}</p>
                            </li>
                          ))}
                          {items.length > 3 && (
                            <li className="pl-2.5 text-xs text-gray-400">
                              +{items.length - 3} more
                            </li>
                          )}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </aside>
        </div>
      </div>
    </main>
  );
}

function KpiCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "neutral" | "amber" | "blue" | "red" | "emerald";
}) {
  const valueCls =
    tone === "amber"
      ? "text-amber-600"
      : tone === "blue"
        ? "text-blue-600"
        : tone === "red"
          ? "text-red-600"
          : tone === "emerald"
            ? "text-emerald-600"
            : "text-gray-900";
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide text-gray-500">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", valueCls)}>{value}</p>
    </Card>
  );
}
