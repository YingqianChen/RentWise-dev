"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, Check, Pencil, RotateCcw, X } from "lucide-react";

import type {
  CandidateFieldActionRequest,
  CandidateFieldFact,
  CandidateFieldState,
} from "@/lib/types";

const GROUPS: Array<{
  key: CandidateFieldFact["group"];
  title: string;
  description: string;
}> = [
  {
    key: "monthly_cost",
    title: "Monthly cost",
    description: "Rent and recurring charges used in your personal budget check.",
  },
  {
    key: "move_in_and_lease",
    title: "Move-in cost and lease",
    description: "Deposit, agent fee, and the length of the commitment.",
  },
  {
    key: "repairs_and_timing",
    title: "Responsibilities and timing",
    description: "Move-in availability and who is expected to handle repairs.",
  },
  {
    key: "location",
    title: "Location",
    description: "Location facts that may also support commute lookup.",
  },
];

const MONEY_FIELDS = new Set(["monthly_rent", "management_fee_amount", "rates_amount"]);
const BOOLEAN_FIELDS = new Set(["management_fee_included", "rates_included"]);

const STATE_COPY: Record<CandidateFieldState, { label: string; help: string; tone: string }> = {
  explicit: {
    label: "Stated in source",
    help: "The value is directly stated in the supplied material.",
    tone: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  inferred: {
    label: "System inferred",
    help: "This is a useful clue, but it is not directly stated and cannot affect the decision yet.",
    tone: "border-blue-200 bg-blue-50 text-blue-800",
  },
  conflicted: {
    label: "Sources conflict",
    help: "Different sources give different answers. Resolve the conflict before relying on this field.",
    tone: "border-amber-200 bg-amber-50 text-amber-800",
  },
  unknown: {
    label: "Not known",
    help: "No reliable value was found.",
    tone: "border-gray-200 bg-gray-50 text-gray-700",
  },
  user_confirmed: {
    label: "You confirmed",
    help: "You confirmed the displayed value, so it may be used in the decision.",
    tone: "border-violet-200 bg-violet-50 text-violet-800",
  },
  user_corrected: {
    label: "You corrected",
    help: "Your corrected value overrides the current system result.",
    tone: "border-violet-200 bg-violet-50 text-violet-800",
  },
  user_marked_unknown: {
    label: "You marked unknown",
    help: "The previous value is excluded until you confirm or correct it.",
    tone: "border-gray-300 bg-gray-100 text-gray-800",
  },
};

function displayValue(fact: CandidateFieldFact, value: unknown = fact.value): string {
  if (value === null || value === undefined || value === "") return "Not confirmed";
  if (typeof value === "boolean") return value ? "Included" : "Separate charge";
  if (MONEY_FIELDS.has(fact.key) && typeof value === "number") {
    return `HKD ${value.toLocaleString()}`;
  }
  return String(value);
}

function CorrectionEditor({
  fact,
  busy,
  onCancel,
  onSubmit,
}: {
  fact: CandidateFieldFact;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (request: CandidateFieldActionRequest) => Promise<void>;
}) {
  const initialValue = fact.value ?? fact.system_value ?? "";
  const [value, setValue] = useState(String(initialValue));
  const [note, setNote] = useState(fact.user_note ?? "");
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    let normalized: number | boolean | string;
    if (MONEY_FIELDS.has(fact.key)) {
      const amount = Number(value);
      if (!value.trim() || !Number.isFinite(amount) || amount < 0) {
        setError("Enter a valid non-negative amount.");
        return;
      }
      normalized = amount;
    } else if (BOOLEAN_FIELDS.has(fact.key)) {
      if (!value) {
        setError("Choose included or separate charge.");
        return;
      }
      normalized = value === "true";
    } else {
      normalized = value.trim();
      if (!normalized) {
        setError("Enter a value, or use Mark unknown instead.");
        return;
      }
    }
    await onSubmit({ action: "correct", value: normalized, note: note.trim() || undefined });
  };

  return (
    <form onSubmit={submit} className="mt-4 space-y-3 rounded-lg border border-violet-200 bg-violet-50/50 p-3">
      <div>
        <label htmlFor={`correct-${fact.key}`} className="mb-1 block text-xs font-medium text-gray-700">Correct value</label>
        {BOOLEAN_FIELDS.has(fact.key) ? (
          <select
            id={`correct-${fact.key}`}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">Choose one</option>
            <option value="true">Included</option>
            <option value="false">Separate charge</option>
          </select>
        ) : (
          <input
            id={`correct-${fact.key}`}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            type={MONEY_FIELDS.has(fact.key) ? "number" : "text"}
            min={MONEY_FIELDS.has(fact.key) ? 0 : undefined}
            step={MONEY_FIELDS.has(fact.key) ? "any" : undefined}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
          />
        )}
      </div>
      <div>
        <label htmlFor={`note-${fact.key}`} className="mb-1 block text-xs font-medium text-gray-700">Note (optional)</label>
        <input
          id={`note-${fact.key}`}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={1000}
          placeholder="For example: confirmed by the agent on WhatsApp"
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
        />
      </div>
      {error && <p className="text-xs text-red-700">{error}</p>}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={busy} className="rounded-md px-3 py-1.5 text-sm text-gray-700 hover:bg-white">
          Cancel
        </button>
        <button type="submit" disabled={busy} className="rounded-md bg-violet-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
          {busy ? "Saving..." : "Save correction"}
        </button>
      </div>
    </form>
  );
}

export function CandidateFieldFacts({
  facts,
  onAction,
}: {
  facts: CandidateFieldFact[];
  onAction: (fact: CandidateFieldFact, request: CandidateFieldActionRequest) => Promise<void>;
}) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const grouped = useMemo(
    () => GROUPS.map((group) => ({ ...group, facts: facts.filter((fact) => fact.group === group.key) })),
    [facts]
  );

  const runAction = async (fact: CandidateFieldFact, request: CandidateFieldActionRequest) => {
    setBusyKey(fact.key);
    setErrors((current) => ({ ...current, [fact.key]: "" }));
    try {
      await onAction(fact, request);
      setEditingKey(null);
    } catch (error) {
      setErrors((current) => ({
        ...current,
        [fact.key]: error instanceof Error ? error.message : "Could not update this field.",
      }));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-base font-semibold text-gray-900">Key facts and evidence</h2>
        <p className="mt-1 text-sm text-gray-500">
          Only facts marked as stated in source or confirmed by you can affect the recommendation.
        </p>
      </div>
      <div className="mt-5 space-y-6">
        {grouped.map((group) => (
          <div key={group.key}>
            <h3 className="text-sm font-semibold text-gray-900">{group.title}</h3>
            <p className="mt-0.5 text-xs text-gray-500">{group.description}</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {group.facts.map((fact) => {
                const state = STATE_COPY[fact.state];
                const busy = busyKey === fact.key;
                return (
                  <article key={fact.key} className="rounded-lg border border-gray-200 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-gray-500">{fact.label}</p>
                        <p className="mt-1 break-words text-base font-semibold text-gray-900">{displayValue(fact)}</p>
                      </div>
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${state.tone}`}>
                        {state.label}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-gray-500">{state.help}</p>

                    {fact.evidence.length > 0 && (
                      <details className="mt-3 rounded-md bg-gray-50 p-3">
                        <summary className="cursor-pointer text-xs font-medium text-gray-700">
                          View {fact.evidence.length} source {fact.evidence.length === 1 ? "quote" : "quotes"}
                        </summary>
                        <div className="mt-3 space-y-3">
                          {fact.evidence.map((evidence) => (
                            <blockquote key={evidence.id} className="border-l-2 border-gray-300 pl-3">
                              <p className="text-xs font-medium text-gray-600">{evidence.source_label}</p>
                              <p className="mt-1 text-sm leading-5 text-gray-800">“{evidence.quote}”</p>
                              {fact.state === "conflicted" && (
                                <p className="mt-1 text-xs text-amber-700">Claimed value: {displayValue(fact, evidence.claim_value)}</p>
                              )}
                            </blockquote>
                          ))}
                        </div>
                      </details>
                    )}

                    {fact.user_note && <p className="mt-3 text-xs text-violet-700">Your note: {fact.user_note}</p>}
                    {errors[fact.key] && (
                      <p className="mt-3 flex items-start gap-1 text-xs text-red-700">
                        <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> {errors[fact.key]}
                      </p>
                    )}

                    <div className="mt-4 flex flex-wrap gap-2">
                      {!fact.user_action && fact.value !== null && ["explicit", "inferred"].includes(fact.state) && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void runAction(fact, { action: "confirm" })}
                          className="inline-flex items-center gap-1 rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                        >
                          <Check className="h-3 w-3" /> Confirm
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setEditingKey(editingKey === fact.key ? null : fact.key)}
                        className="inline-flex items-center gap-1 rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        <Pencil className="h-3 w-3" /> Correct
                      </button>
                      {fact.state !== "user_marked_unknown" && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void runAction(fact, { action: "mark_unknown" })}
                          className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                        >
                          <X className="h-3 w-3" /> Mark unknown
                        </button>
                      )}
                      {fact.user_action && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void runAction(fact, { action: "revert" })}
                          className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-violet-700 hover:bg-violet-50 disabled:opacity-50"
                        >
                          <RotateCcw className="h-3 w-3" /> Restore system value
                        </button>
                      )}
                    </div>

                    {editingKey === fact.key && (
                      <CorrectionEditor
                        key={`${fact.key}-${String(fact.value)}`}
                        fact={fact}
                        busy={busy}
                        onCancel={() => setEditingKey(null)}
                        onSubmit={(request) => runAction(fact, request)}
                      />
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
