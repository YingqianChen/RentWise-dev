"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  Bus,
  CheckCircle2,
  ChevronLeft,
  Clock,
  Copy,
  DollarSign,
  FileText,
  Footprints,
  Gauge,
  MapPin,
  MessageSquare,
  Pencil,
  Plane,
  RefreshCw,
  Sparkles,
  Train,
  TrainFront,
  Trash2,
  XCircle,
} from "lucide-react";

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
  CommuteSegment,
  CompareCandidateCard,
  ComparisonResponse,
  DecisionSignal,
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
  variant = "default",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: "default" | "outline" | "secondary" }) {
  const base =
    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap";
  const variantCls =
    variant === "outline"
      ? "border border-gray-200 bg-white text-gray-700"
      : variant === "secondary"
        ? "bg-gray-100 text-gray-700"
        : "bg-gray-900 text-white";
  return <span className={cn(base, variantCls, className)} {...props} />;
}

function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 overflow-hidden rounded-xl border border-gray-200 bg-white text-gray-900 shadow-sm",
        className
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pt-5 pb-0", className)} {...props} />;
}

function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("text-base font-semibold leading-snug text-gray-900", className)}
      {...props}
    />
  );
}

function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-1 text-sm text-gray-500", className)} {...props} />;
}

function Separator({ className }: { className?: string }) {
  return <div className={cn("h-px w-full bg-gray-200", className)} />;
}

const COMMUTE_MODE_STYLE: Record<string, { cls: string; label: string; Icon: React.ComponentType<{ className?: string }> }> = {
  walking: { cls: "bg-gray-100 text-gray-700 ring-gray-200", label: "Walk", Icon: Footprints },
  subway: { cls: "bg-violet-50 text-violet-800 ring-violet-200", label: "MTR", Icon: TrainFront },
  rail: { cls: "bg-indigo-50 text-indigo-800 ring-indigo-200", label: "Rail", Icon: Train },
  airport_express: { cls: "bg-purple-50 text-purple-800 ring-purple-200", label: "Airport Express", Icon: Plane },
  bus: { cls: "bg-blue-50 text-blue-800 ring-blue-200", label: "Bus", Icon: Bus },
  minibus: { cls: "bg-emerald-50 text-emerald-800 ring-emerald-200", label: "Minibus", Icon: Bus },
  taxi: { cls: "bg-amber-50 text-amber-800 ring-amber-200", label: "Taxi", Icon: Bus },
};

function CommuteLegChip({ leg }: { leg: CommuteSegment }) {
  const style = COMMUTE_MODE_STYLE[leg.mode] ?? COMMUTE_MODE_STYLE.bus;
  const Icon = style.Icon;
  const labelParts: string[] = [];
  if (leg.mode === "walking") {
    labelParts.push("Walk");
  } else if (leg.line_name) {
    labelParts.push(leg.line_name);
  } else {
    labelParts.push(style.label);
  }
  if (leg.duration_minutes) {
    labelParts.push(`${leg.duration_minutes} min`);
  } else if (leg.mode === "walking" && leg.distance_meters) {
    labelParts.push(`${leg.distance_meters} m`);
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        style.cls,
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {labelParts.join(" · ")}
    </span>
  );
}

function Alert({
  variant = "default",
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: "default" | "destructive" | "info" }) {
  const variantCls =
    variant === "destructive"
      ? "border-red-200 bg-red-50 text-red-900"
      : variant === "info"
        ? "border-blue-200 bg-blue-50 text-blue-900"
        : "border-gray-200 bg-white text-gray-900";
  return (
    <div
      role="alert"
      className={cn("flex items-start gap-3 rounded-lg border p-4 text-sm", variantCls, className)}
      {...props}
    />
  );
}

function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("font-semibold", className)} {...props} />;
}

function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-0.5 text-sm opacity-90", className)} {...props} />;
}

type TabsContextValue = {
  value: string;
  setValue: (value: string) => void;
};

const TabsContext = createContext<TabsContextValue | null>(null);

function Tabs({
  defaultValue,
  children,
  className,
}: {
  defaultValue: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [value, setValue] = useState(defaultValue);
  return (
    <TabsContext.Provider value={{ value, setValue }}>
      <div className={cn("flex flex-col gap-4", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

function TabsList({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "inline-flex h-9 w-fit items-center justify-start gap-1 rounded-lg bg-gray-100 p-1 text-sm text-gray-600",
        className
      )}
    >
      {children}
    </div>
  );
}

function TabsTrigger({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("TabsTrigger must be inside Tabs");
  const active = ctx.value === value;
  return (
    <button
      type="button"
      onClick={() => ctx.setValue(value)}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-md px-3 font-medium transition",
        active ? "bg-white text-gray-900 shadow-sm" : "text-gray-600 hover:text-gray-900",
        className
      )}
    >
      {children}
    </button>
  );
}

function TabsContent({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  const ctx = useContext(TabsContext);
  if (!ctx) return null;
  if (ctx.value !== value) return null;
  return <div className={className}>{children}</div>;
}

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
      return "bg-emerald-50 text-emerald-700 ring-emerald-200";
    case "likely_reject":
      return "bg-red-50 text-red-700 ring-red-200";
    default:
      return "bg-amber-50 text-amber-700 ring-amber-200";
  }
}

function recommendationAccentBar(value?: string | null) {
  switch (value) {
    case "shortlist_recommendation":
      return "bg-emerald-500";
    case "likely_reject":
      return "bg-red-500";
    default:
      return "bg-amber-500";
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

function riskTone(flag?: string | null) {
  switch (flag) {
    case "none":
      return "text-emerald-700 bg-emerald-50 ring-emerald-200";
    case "high_risk":
    case "over_budget":
    case "hidden_cost_risk":
      return "text-red-700 bg-red-50 ring-red-200";
    case "possible_additional_cost":
    case "needs_confirmation":
      return "text-amber-700 bg-amber-50 ring-amber-200";
    default:
      return "text-gray-600 bg-gray-100 ring-gray-200";
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

function confidenceRatio(level?: string | null) {
  switch (level) {
    case "high":
      return 0.92;
    case "medium":
      return 0.58;
    default:
      return 0.25;
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
      return "bg-red-50 border-red-200 text-red-900";
    case "cost":
    case "timing":
    case "living_arrangement":
      return "bg-amber-50 border-amber-200 text-amber-900";
    default:
      return "bg-gray-50 border-gray-200 text-gray-800";
  }
}

function KeyFact({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-gray-100 text-gray-600">
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">{label}</p>
        <p className="mt-0.5 truncate text-sm font-medium text-gray-900">{value}</p>
      </div>
    </div>
  );
}

function ConfidenceBar({ level }: { level?: string | null }) {
  const ratio = confidenceRatio(level);
  const color =
    level === "high"
      ? "bg-emerald-500"
      : level === "medium"
        ? "bg-amber-500"
        : "bg-red-500";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
      <div
        className={cn("h-full rounded-full transition-all", color)}
        style={{ width: `${Math.round(ratio * 100)}%` }}
      />
    </div>
  );
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

  const keyFacts = useMemo(() => {
    if (!candidate) return [];
    const extracted = candidate.extracted_info;
    const facts: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }[] = [];
    const rent = candidate.cost_assessment?.known_monthly_cost
      ? `HKD ${candidate.cost_assessment.known_monthly_cost.toLocaleString()}`
      : extracted?.monthly_rent && extracted.monthly_rent !== "unknown"
        ? extracted.monthly_rent
        : "Unknown";
    facts.push({ icon: DollarSign, label: "Monthly cost", value: rent });
    if (extracted?.district && extracted.district !== "unknown") {
      facts.push({ icon: MapPin, label: "District", value: extracted.district });
    }
    if (extracted?.building_name) {
      facts.push({ icon: MapPin, label: "Building", value: extracted.building_name });
    }
    if (extracted?.nearest_station) {
      facts.push({ icon: MapPin, label: "Nearest station", value: extracted.nearest_station });
    }
    if (extracted?.deposit && extracted.deposit !== "unknown") {
      facts.push({ icon: DollarSign, label: "Deposit", value: extracted.deposit });
    }
    if (extracted?.size_sqft && extracted.size_sqft !== "unknown") {
      facts.push({ icon: Gauge, label: "Size", value: `${extracted.size_sqft} sqft` });
    }
    if (extracted?.move_in_date && extracted.move_in_date !== "unknown") {
      facts.push({ icon: Clock, label: "Move-in", value: extracted.move_in_date });
    }
    if (candidate.commute_evidence?.status === "ready" && candidate.commute_evidence.estimated_minutes) {
      const ce = candidate.commute_evidence;
      const leg = ce.origin_station && ce.destination_station
        ? ` · ${ce.origin_station} → ${ce.destination_station}`
        : "";
      facts.push({
        icon: Clock,
        label: "Commute",
        value: `${ce.estimated_minutes} min to ${ce.destination_label ?? "destination"}${leg}`,
      });
    }
    return facts;
  }, [candidate]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="flex items-center gap-2 text-gray-500">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>Loading candidate...</span>
        </div>
      </main>
    );
  }

  if (!candidate) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-gray-500">Candidate not found.</div>
      </main>
    );
  }

  const extracted = candidate.extracted_info;
  const cost = candidate.cost_assessment;
  const clause = candidate.clause_assessment;
  const assessment = candidate.candidate_assessment;
  const benchmark = candidate.benchmark;
  const decisionBlockers = buildDecisionBlockers(candidate);
  const monthlyCostDisplay = cost?.known_monthly_cost
    ? `HKD ${cost.known_monthly_cost.toLocaleString()}`
    : "Unknown";

  return (
    <main className="relative min-h-screen overflow-hidden bg-gray-50">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[360px] bg-gradient-to-br from-violet-100 via-blue-50 to-emerald-50"
      />
      <div className="relative mx-auto max-w-6xl px-4 py-6 lg:px-6 lg:py-8">
        {/* Header */}
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <Link
              href={`/projects/${projectId}`}
              className="inline-flex items-center gap-1 text-sm text-gray-500 transition hover:text-gray-900"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Back to project
            </Link>
            <div className="mt-2 flex items-center gap-3">
              <div className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-gray-900 text-white">
                <Sparkles className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">
                  RentWise · Candidate
                </p>
                <h1 className="truncate text-2xl font-semibold tracking-tight text-gray-900">
                  {candidate.name}
                </h1>
              </div>
            </div>
            <p className="mt-2 text-sm text-gray-500">
              Review this candidate as a decision task, not just a data record.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSaveError("");
                setIsEditing((current) => !current);
              }}
              disabled={actionLoading || isProcessing}
            >
              <Pencil className="h-3.5 w-3.5" />
              {isEditing ? "Close editor" : "Edit"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleReassess}
              disabled={actionLoading || isProcessing}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", actionLoading && "animate-spin")} />
              Reassess
            </Button>
            {candidate.user_decision !== "undecided" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowConfirm("delete")}
                className="text-red-600 hover:text-red-700"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
            )}
          </div>
        </div>

        {/* Processing banner */}
        {candidate.processing_stage && candidate.processing_stage !== "completed" && (
          <Alert
            variant={candidate.processing_stage === "failed" ? "destructive" : "info"}
            className="mb-6"
          >
            <RefreshCw
              className={cn(
                "h-4 w-4 shrink-0",
                candidate.processing_stage !== "failed" && "animate-spin"
              )}
            />
            <div className="flex-1">
              <AlertTitle>{processingStageLabel(candidate.processing_stage)}</AlertTitle>
              <AlertDescription>
                {candidate.processing_error || processingStageDescription(candidate.processing_stage)}
                {candidate.processing_stage !== "failed" && (
                  <p className="mt-2">This page refreshes automatically while the import runs.</p>
                )}
              </AlertDescription>
            </div>
          </Alert>
        )}

        {/* Two-pane layout */}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0 space-y-6">
            {/* Decision Hero */}
            {assessment && (
              <Card className="py-0">
                <div className={cn("h-1 w-full", recommendationAccentBar(assessment.top_level_recommendation))} />
                <div className="grid gap-6 p-6 md:grid-cols-[1.4fr_1fr]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1",
                          recommendationTone(assessment.top_level_recommendation)
                        )}
                      >
                        {assessment.top_level_recommendation === "shortlist_recommendation" && (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        )}
                        {assessment.top_level_recommendation === "likely_reject" && (
                          <XCircle className="h-3.5 w-3.5" />
                        )}
                        {assessment.top_level_recommendation === "not_ready" && (
                          <AlertTriangle className="h-3.5 w-3.5" />
                        )}
                        {recommendationLabel(assessment.top_level_recommendation)}
                      </span>
                      <Badge variant="outline">
                        <Sparkles className="h-3 w-3" />
                        Next: {actionLabel(assessment.next_best_action)}
                      </Badge>
                    </div>
                    <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-gray-500">
                      Decision snapshot
                    </p>
                    <h2 className="mt-1 text-xl font-semibold text-gray-900">What matters now</h2>
                    <p className="mt-2 text-sm leading-relaxed text-gray-700">{assessment.summary}</p>
                    {assessment.labels.length > 0 && (
                      <div className="mt-4 flex flex-wrap gap-1.5">
                        {assessment.labels.map((label) => (
                          <Badge key={label} variant="secondary">
                            {label}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="space-y-4 rounded-lg bg-gray-50 p-4">
                    <div>
                      <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
                        Known monthly cost
                      </p>
                      <p className="mt-1 text-2xl font-semibold tracking-tight text-gray-900">
                        {monthlyCostDisplay}
                      </p>
                    </div>
                    <Separator />
                    <div>
                      <div className="flex items-center justify-between">
                        <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
                          Confidence
                        </p>
                        <span className="text-xs font-medium text-gray-900">
                          {confidenceLabel(assessment.recommendation_confidence)}
                        </span>
                      </div>
                      <div className="mt-1.5">
                        <ConfidenceBar level={assessment.recommendation_confidence} />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between">
                        <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
                          Decision risk
                        </p>
                        <span className="text-xs font-medium text-gray-900">
                          {confidenceLabel(assessment.decision_risk_level)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {/* Tabs: Cost / Clause / Commute / Fit */}
            <Tabs defaultValue="cost">
              <TabsList>
                <TabsTrigger value="cost">
                  <DollarSign className="h-3.5 w-3.5" />
                  Cost
                </TabsTrigger>
                <TabsTrigger value="clause">
                  <FileText className="h-3.5 w-3.5" />
                  Clause
                </TabsTrigger>
                <TabsTrigger value="commute">
                  <MapPin className="h-3.5 w-3.5" />
                  Commute
                </TabsTrigger>
                <TabsTrigger value="fit">
                  <Gauge className="h-3.5 w-3.5" />
                  Fit
                </TabsTrigger>
              </TabsList>

              <TabsContent value="cost">
                <Card>
                  <CardHeader>
                    <CardTitle>Cost read</CardTitle>
                    <CardDescription>
                      What the assistant can confirm about the real monthly cost and move-in cost.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-gray-500">Known monthly cost</p>
                        <p className="mt-1 text-lg font-semibold text-gray-900">{monthlyCostDisplay}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Confidence</p>
                        <p className="mt-1 text-lg font-semibold text-gray-900">
                          {confidenceLabel(cost?.monthly_cost_confidence)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Cost risk</p>
                        <span
                          className={cn(
                            "mt-1 inline-flex rounded-md px-2 py-0.5 text-sm font-medium ring-1",
                            riskTone(cost?.cost_risk_flag)
                          )}
                        >
                          {riskLabel(cost?.cost_risk_flag)}
                        </span>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Move-in cost (known part)</p>
                        <p className="mt-1 text-sm font-medium text-gray-900">
                          {cost?.move_in_cost_known_part
                            ? `HKD ${cost.move_in_cost_known_part.toLocaleString()}`
                            : "Unknown"}
                        </p>
                      </div>
                    </div>
                    {cost?.summary && (
                      <p className="text-sm leading-relaxed text-gray-700">{cost.summary}</p>
                    )}
                    {cost?.monthly_cost_missing_items && cost.monthly_cost_missing_items.length > 0 && (
                      <div>
                        <p className="text-xs text-gray-500">Missing cost fields</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {cost.monthly_cost_missing_items.map((item) => (
                            <Badge key={item} variant="outline">
                              {item}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="clause">
                <Card>
                  <CardHeader>
                    <CardTitle>Clause read</CardTitle>
                    <CardDescription>
                      Repair, lease flexibility, and move-in timing. Drill down for the nuance.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Repair responsibility</p>
                        <p className="mt-1 text-sm font-medium text-gray-900">
                          {repairResponsibilityLabel(clause?.repair_responsibility_level)}
                        </p>
                      </div>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Lease term</p>
                        <p className="mt-1 text-sm font-medium text-gray-900">
                          {leaseTermLabel(clause?.lease_term_level)}
                        </p>
                        <p className="mt-1 text-xs text-gray-500">
                          {leaseTermDescription(clause?.lease_term_level)}
                        </p>
                      </div>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Move-in timing</p>
                        <p className="mt-1 text-sm font-medium text-gray-900">
                          {moveInTimingLabel(clause?.move_in_date_level)}
                        </p>
                        <p className="mt-1 text-xs text-gray-500">
                          {moveInTimingDescription(clause?.move_in_date_level)}
                        </p>
                      </div>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Clause risk</p>
                        <p className="mt-1">
                          <span
                            className={cn(
                              "inline-flex rounded-md px-2 py-0.5 text-sm font-medium ring-1",
                              riskTone(clause?.clause_risk_flag)
                            )}
                          >
                            {riskLabel(clause?.clause_risk_flag)}
                          </span>
                        </p>
                      </div>
                    </div>
                    {clause?.summary && (
                      <p className="text-sm leading-relaxed text-gray-700">{clause.summary}</p>
                    )}
                    {clause?.legal_references && clause.legal_references.length > 0 && (
                      <div className="rounded-lg border border-violet-100 bg-violet-50/60 p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-violet-700">
                          Ordinance reference
                        </p>
                        <ul className="mt-2 space-y-2">
                          {clause.legal_references.map((ref, idx) => (
                            <li key={ref.chunk_id ?? idx} className="text-xs leading-relaxed text-gray-700">
                              <span className="italic">「{ref.quote}」</span>
                              <span className="ml-1 text-gray-500">
                                — 《业主与租客（综合）条例》指南 p.{ref.source_page}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="commute">
                <Card>
                  <CardHeader>
                    <CardTitle>Commute estimate</CardTitle>
                    <CardDescription>
                      How this candidate fits your configured commute destination.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {!candidate.commute_evidence ? (
                      <p className="text-sm text-gray-500">No commute information recorded yet.</p>
                    ) : candidate.commute_evidence.status === "ready" ? (
                      <div className="space-y-4">
                        <div className="flex items-baseline gap-3">
                          <p className="text-3xl font-semibold tracking-tight text-gray-900">
                            {candidate.commute_evidence.estimated_minutes}
                          </p>
                          <p className="text-sm text-gray-500">
                            min to {candidate.commute_evidence.destination_label}
                          </p>
                        </div>
                        {candidate.commute_evidence.origin_station && (
                          <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
                            <TrainFront className="h-4 w-4 text-gray-500" />
                            <span>{candidate.commute_evidence.origin_station}</span>
                            <ArrowRight className="h-3.5 w-3.5 text-gray-400" />
                            <span>{candidate.commute_evidence.destination_station ?? candidate.commute_evidence.destination_label}</span>
                          </div>
                        )}
                        {candidate.commute_evidence.segments && candidate.commute_evidence.segments.length > 0 && (
                          <div className="flex flex-wrap items-center gap-x-1.5 gap-y-2">
                            {candidate.commute_evidence.segments.map((leg, idx) => (
                              <span key={idx} className="inline-flex items-center gap-1.5">
                                {idx > 0 && <ArrowRight className="h-3 w-3 text-gray-300" />}
                                <CommuteLegChip leg={leg} />
                              </span>
                            ))}
                          </div>
                        )}
                        {candidate.commute_evidence.confidence_note && (
                          <p className="text-xs text-gray-500">
                            {candidate.commute_evidence.confidence_note}
                          </p>
                        )}
                      </div>
                    ) : candidate.commute_evidence.status === "not_configured" ? (
                      <p className="text-sm text-gray-500">
                        Add a commute destination in project settings to see travel estimates.
                      </p>
                    ) : candidate.commute_evidence.status === "insufficient_candidate_location" ? (
                      <Alert className="border-amber-200 bg-amber-50 text-amber-900">
                        <AlertTriangle className="h-4 w-4 flex-none text-amber-600" />
                        <div className="min-w-0">
                          <AlertTitle>Location not precise enough</AlertTitle>
                          <AlertDescription className="text-amber-800">
                            {candidate.commute_evidence.confidence_note ??
                              "Add a more specific address or Chinese place name, then reassess."}
                          </AlertDescription>
                        </div>
                      </Alert>
                    ) : (
                      <p className="text-sm text-gray-500">
                        {candidate.commute_evidence.confidence_note || "Commute calculation failed."}
                      </p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="fit">
                <Card>
                  <CardHeader>
                    <CardTitle>Market and fit context</CardTitle>
                    <CardDescription>District benchmark and situational fit signals.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {benchmark && benchmark.status === "available" ? (
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <p className="text-sm font-medium text-gray-900">
                            Median rent in {benchmark.district}
                          </p>
                          <p className="text-lg font-semibold text-gray-900">
                            HKD {benchmark.median_monthly_rent?.toLocaleString()}
                          </p>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">
                          {benchmark.source_period} · HKD{" "}
                          {benchmark.median_monthly_rent_per_sqm?.toLocaleString()} per sq m / mo
                        </p>
                        {benchmark.fit_note && (
                          <p className="mt-3 text-sm text-gray-700">{benchmark.fit_note}</p>
                        )}
                        {benchmark.record_note === "fewer_than_10_records" && (
                          <p className="mt-2 text-xs text-amber-700">
                            Based on fewer than 10 rental records.
                          </p>
                        )}
                        {benchmark.disclaimer && (
                          <p className="mt-2 text-xs text-gray-500">{benchmark.disclaimer}</p>
                        )}
                      </div>
                    ) : benchmark ? (
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                        <p className="text-sm text-gray-700">{benchmarkStatusCopy(benchmark)}</p>
                        <p className="mt-2 text-xs text-gray-500">
                          For subdivided units only. General reference, not property-specific.
                        </p>
                      </div>
                    ) : null}

                    {assessment && (
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                          <p className="text-xs text-gray-500">Potential value</p>
                          <p className="mt-1 text-sm font-medium text-gray-900">
                            {confidenceLabel(assessment.potential_value_level)}
                          </p>
                        </div>
                        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                          <p className="text-xs text-gray-500">Completeness</p>
                          <p className="mt-1 text-sm font-medium text-gray-900">
                            {confidenceLabel(assessment.completeness_level)}
                          </p>
                        </div>
                        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                          <p className="text-xs text-gray-500">Critical uncertainty</p>
                          <p className="mt-1 text-sm font-medium text-gray-900">
                            {confidenceLabel(assessment.critical_uncertainty_level)}
                          </p>
                        </div>
                        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                          <p className="text-xs text-gray-500">Information gain</p>
                          <p className="mt-1 text-sm font-medium text-gray-900">
                            {confidenceLabel(assessment.information_gain_level)}
                          </p>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            {/* Outreach Draft */}
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <MessageSquare className="h-4 w-4" />
                      Outreach draft
                    </CardTitle>
                    <CardDescription>
                      Turn the open questions into a short message you can send.
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {contactPlan && (
                      <Button variant="outline" size="sm" onClick={handleCopyContactDraft}>
                        {contactPlanCopied ? (
                          <>
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            Copy message
                          </>
                        )}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      onClick={handleGenerateContactPlan}
                      disabled={contactPlanLoading || isProcessing}
                    >
                      {contactPlanLoading ? (
                        <>
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          Drafting...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-3.5 w-3.5" />
                          {contactPlan ? "Refresh draft" : "Draft outreach"}
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {contactPlanError && <p className="mb-3 text-sm text-red-600">{contactPlanError}</p>}
                {contactPlan ? (
                  <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
                        Contact goal
                      </p>
                      <p className="mt-1 text-sm leading-relaxed text-gray-700">
                        {contactPlan.contact_goal}
                      </p>
                      <p className="mt-4 text-[11px] font-medium uppercase tracking-wider text-gray-500">
                        Best questions to ask
                      </p>
                      <ol className="mt-2 space-y-2.5 text-sm text-gray-700">
                        {contactPlan.questions.map((question, index) => (
                          <li key={question} className="flex gap-2">
                            <span className="shrink-0 text-xs font-semibold text-gray-400">
                              {index + 1}.
                            </span>
                            <span>{question}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
                        English message draft
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        Keep it lightweight; edit tone before sending.
                      </p>
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                        {contactPlan.message_draft}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">
                    Draft on demand — the assistant will pull in the current gaps and open questions.
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Edit form (conditional) */}
            {isEditing && (
              <Card>
                <CardHeader>
                  <CardTitle>Edit candidate</CardTitle>
                  <CardDescription>
                    Update source text and the assistant will rerun extraction and assessment.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form className="space-y-4" onSubmit={handleEditSave}>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">
                        Candidate name
                      </label>
                      <input
                        type="text"
                        value={formState.name}
                        onChange={(e) =>
                          setFormState((current) => ({ ...current, name: e.target.value }))
                        }
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                        placeholder="Candidate name"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">
                        Listing text
                      </label>
                      <textarea
                        value={formState.raw_listing_text}
                        onChange={(e) =>
                          setFormState((current) => ({ ...current, raw_listing_text: e.target.value }))
                        }
                        rows={6}
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                        placeholder="Paste the listing description here."
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">
                        Chat transcript
                      </label>
                      <textarea
                        value={formState.raw_chat_text}
                        onChange={(e) =>
                          setFormState((current) => ({ ...current, raw_chat_text: e.target.value }))
                        }
                        rows={5}
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                        placeholder="Paste agent or landlord messages here."
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">Notes</label>
                      <textarea
                        value={formState.raw_note_text}
                        onChange={(e) =>
                          setFormState((current) => ({ ...current, raw_note_text: e.target.value }))
                        }
                        rows={4}
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                        placeholder="Add anything you observed or want to remember."
                      />
                    </div>
                    {saveError && <p className="text-sm text-red-600">{saveError}</p>}
                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={handleEditCancel}
                        disabled={actionLoading}
                      >
                        Cancel
                      </Button>
                      <Button type="submit" disabled={actionLoading}>
                        {actionLoading ? "Saving..." : "Save and reassess"}
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            )}

            {/* Evidence drill-down */}
            <Card>
              <CardHeader>
                <CardTitle>Evidence</CardTitle>
                <CardDescription>
                  Raw extraction, OCR text, and observations — open only when you need to audit a claim.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <details className="group rounded-lg border border-gray-200 bg-gray-50 p-4 open:bg-white">
                  <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-medium text-gray-900">
                    <span className="inline-flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-gray-500" />
                      Structured listing fields
                    </span>
                    <span className="text-xs text-gray-500 group-open:hidden">Expand</span>
                    <span className="hidden text-xs text-gray-500 group-open:inline">Collapse</span>
                  </summary>
                  <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm md:grid-cols-2">
                    {extracted?.monthly_rent && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Monthly rent</dt>
                        <dd className="font-medium text-gray-900">{extracted.monthly_rent}</dd>
                      </div>
                    )}
                    {extracted?.district && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">District</dt>
                        <dd className="font-medium text-gray-900">{extracted.district}</dd>
                      </div>
                    )}
                    {extracted?.building_name && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Building</dt>
                        <dd className="font-medium text-gray-900">{extracted.building_name}</dd>
                      </div>
                    )}
                    {extracted?.nearest_station && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Nearest station</dt>
                        <dd className="font-medium text-gray-900">{extracted.nearest_station}</dd>
                      </div>
                    )}
                    {extracted?.deposit && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Deposit</dt>
                        <dd className="text-gray-900">{extracted.deposit}</dd>
                      </div>
                    )}
                    {extracted?.agent_fee && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Agent fee</dt>
                        <dd className="text-gray-900">{extracted.agent_fee}</dd>
                      </div>
                    )}
                    {extracted?.management_fee_amount && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Management fee</dt>
                        <dd className="text-gray-900">
                          {extracted.management_fee_amount}
                          {extracted.management_fee_included === true
                            ? " (included)"
                            : extracted.management_fee_included === false
                              ? " (separate)"
                              : ""}
                        </dd>
                      </div>
                    )}
                    {extracted?.lease_term && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Lease term</dt>
                        <dd className="text-gray-900">{extracted.lease_term}</dd>
                      </div>
                    )}
                    {extracted?.move_in_date && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Move-in date</dt>
                        <dd className="text-gray-900">{extracted.move_in_date}</dd>
                      </div>
                    )}
                    {extracted?.furnished && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Furnishing</dt>
                        <dd className="text-gray-900">{extracted.furnished}</dd>
                      </div>
                    )}
                    {extracted?.size_sqft && (
                      <div className="flex justify-between gap-4 border-b border-gray-200/60 py-1.5">
                        <dt className="text-gray-500">Size</dt>
                        <dd className="text-gray-900">{extracted.size_sqft} sqft</dd>
                      </div>
                    )}
                  </dl>
                </details>

                {extracted && extracted.raw_facts && extracted.raw_facts.length > 0 && (
                  <details className="group rounded-lg border border-gray-200 bg-gray-50 p-4 open:bg-white">
                    <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-medium text-gray-900">
                      <span className="inline-flex items-center gap-2">
                        <Sparkles className="h-3.5 w-3.5 text-gray-500" />
                        Other observations
                      </span>
                      <span className="text-xs text-gray-500 group-open:hidden">
                        {extracted.raw_facts.length} notes
                      </span>
                    </summary>
                    <p className="mt-2 text-xs text-gray-500">
                      Facts the assistant noticed but did not fit typed fields. Shown for context; not used in the recommendation.
                    </p>
                    <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-gray-700">
                      {extracted.raw_facts.map((fact, index) => (
                        <li key={`raw-fact-${index}`}>{fact}</li>
                      ))}
                    </ul>
                  </details>
                )}

                {extracted && extracted.decision_signals.length > 0 && (
                  <details className="group rounded-lg border border-gray-200 bg-gray-50 p-4 open:bg-white">
                    <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-medium text-gray-900">
                      <span className="inline-flex items-center gap-2">
                        <AlertTriangle className="h-3.5 w-3.5 text-gray-500" />
                        Decision signals
                      </span>
                      <span className="text-xs text-gray-500 group-open:hidden">
                        {extracted.decision_signals.length} signals
                      </span>
                    </summary>
                    <div className="mt-4 space-y-2">
                      {extracted.decision_signals.map((signal: DecisionSignal, index) => (
                        <div
                          key={`${signal.key}-${index}`}
                          className={cn("rounded-lg border p-3", signalTone(signal.category))}
                        >
                          <div className="mb-1 flex flex-wrap items-center gap-1.5">
                            <span className="text-sm font-medium">{signal.label}</span>
                            <Badge variant="outline" className="bg-white/70">
                              {signalCategoryLabel(signal.category)}
                            </Badge>
                            <Badge variant="outline" className="bg-white/70">
                              {signalSourceLabel(signal.source)}
                            </Badge>
                          </div>
                          <p className="text-sm opacity-90">{signal.evidence}</p>
                          {signal.note && <p className="mt-1.5 text-xs opacity-75">{signal.note}</p>}
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {candidate.source_assets.length > 0 && (
                  <details className="group rounded-lg border border-gray-200 bg-gray-50 p-4 open:bg-white">
                    <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-medium text-gray-900">
                      <span className="inline-flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-gray-500" />
                        OCR evidence
                      </span>
                      <span className="text-xs text-gray-500 group-open:hidden">
                        {candidate.source_assets.length} files
                      </span>
                    </summary>
                    <div className="mt-4 space-y-3">
                      {candidate.source_assets.map((asset) => (
                        <div key={asset.id} className="rounded-lg border border-gray-200 bg-white p-3">
                          <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-gray-900">
                                {asset.original_filename}
                              </p>
                              <p className="text-xs text-gray-500">
                                {asset.file_size
                                  ? `${Math.round(asset.file_size / 1024)} KB`
                                  : "Unknown size"}
                              </p>
                            </div>
                            <span
                              className={cn(
                                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                                asset.ocr_status === "succeeded"
                                  ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                                  : asset.ocr_status === "failed"
                                    ? "bg-red-50 text-red-700 ring-1 ring-red-200"
                                    : "bg-gray-100 text-gray-700"
                              )}
                            >
                              OCR {asset.ocr_status}
                            </span>
                          </div>
                          {asset.ocr_text ? (
                            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-xs text-gray-600">
                              {asset.ocr_text}
                            </pre>
                          ) : (
                            <p className="text-xs text-gray-500">No OCR text was saved.</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {candidate.combined_text && (
                  <details className="group rounded-lg border border-gray-200 bg-gray-50 p-4 open:bg-white">
                    <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-gray-900">
                      <FileText className="h-3.5 w-3.5 text-gray-500" />
                      Source text
                    </summary>
                    <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-white p-3 text-xs text-gray-600">
                      {candidate.combined_text}
                    </pre>
                  </details>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sticky sidebar */}
          <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
            {/* CTAs */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Decide</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {candidate.user_decision === "undecided" ? (
                  <>
                    <Button
                      className="w-full bg-emerald-600 hover:bg-emerald-700"
                      onClick={() => setShowConfirm("shortlist")}
                      disabled={isProcessing}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Shortlist
                    </Button>
                    <Button
                      variant="outline"
                      className="w-full text-red-600 hover:text-red-700"
                      onClick={() => setShowConfirm("reject")}
                      disabled={isProcessing}
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reject
                    </Button>
                    <Button
                      variant="ghost"
                      className="w-full"
                      onClick={() => setShowConfirm("delete")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </Button>
                  </>
                ) : (
                  <div
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm font-medium ring-1",
                      candidate.user_decision === "shortlisted"
                        ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                        : "bg-red-50 text-red-700 ring-red-200"
                    )}
                  >
                    {candidate.user_decision === "shortlisted" ? "Shortlisted" : "Rejected"}
                  </div>
                )}
                <Link
                  href={`/projects/${projectId}/compare?ids=${candidateId}`}
                  className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
                >
                  <ArrowLeftRight className="h-3.5 w-3.5" />
                  Add to compare
                </Link>
              </CardContent>
            </Card>

            {/* Key facts */}
            {keyFacts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Key facts</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {keyFacts.map((fact) => (
                    <KeyFact key={fact.label} icon={fact.icon} label={fact.label} value={fact.value} />
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Blockers */}
            {decisionBlockers.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5 text-sm">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                    Open blockers
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm text-gray-700">
                    {decisionBlockers.map((blocker) => (
                      <li key={blocker} className="flex gap-2">
                        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                        <span>{blocker}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {/* Compare context */}
            {compareContext && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Compare context</CardTitle>
                  <CardDescription className="text-xs">
                    {compareContext.comparison.summary.headline}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs leading-relaxed text-gray-700">
                    {compareContext.card.decision_explanation}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {buildCompareSetNames(compareContext.comparison).map((name) => (
                      <Badge key={name} variant="secondary">
                        {name}
                      </Badge>
                    ))}
                  </div>
                  <Link
                    href={`/projects/${projectId}/compare?ids=${encodeURIComponent(
                      buildCompareSetIds(compareContext.comparison).join(",")
                    )}`}
                    className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-3 text-sm font-medium text-white transition hover:bg-black"
                  >
                    Open compare workspace
                  </Link>
                </CardContent>
              </Card>
            )}
          </aside>
        </div>

        {/* Confirm modal */}
        {showConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>
                  {showConfirm === "shortlist"
                    ? "Confirm shortlist"
                    : showConfirm === "reject"
                      ? "Confirm rejection"
                      : "Delete candidate"}
                </CardTitle>
                <CardDescription>
                  {showConfirm === "shortlist"
                    ? "Add this candidate to your shortlist?"
                    : showConfirm === "reject"
                      ? "Mark this candidate as rejected? You can reassess it later if needed."
                      : "Delete this candidate and all related assessments? This cannot be undone."}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setShowConfirm(null)}>
                  Cancel
                </Button>
                <Button
                  onClick={() =>
                    showConfirm === "delete" ? void handleDelete() : void handleAction(showConfirm)
                  }
                  disabled={actionLoading}
                  className={cn(
                    showConfirm === "shortlist" && "bg-emerald-600 hover:bg-emerald-700",
                    showConfirm === "reject" && "bg-red-600 hover:bg-red-700",
                    showConfirm === "delete" && "bg-gray-900 hover:bg-black"
                  )}
                >
                  {actionLoading
                    ? showConfirm === "delete"
                      ? "Deleting..."
                      : "Working..."
                    : showConfirm === "delete"
                      ? "Confirm delete"
                      : "Confirm"}
                </Button>
              </CardContent>
            </Card>
          </div>
        )}
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
