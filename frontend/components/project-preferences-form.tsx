"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Pencil, SlidersHorizontal } from "lucide-react";

import { updateProject } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Project } from "@/lib/types";

function joinPreferences(values: string[]): string {
  return values.join("\n");
}

function parsePreferences(value: string, splitOnComma = false): string[] {
  const separator = splitOnComma ? /[,\n]/ : /\n/;
  const result: string[] = [];
  const seen = new Set<string>();

  for (const item of value.split(separator)) {
    const normalized = item.trim();
    if (!normalized) continue;
    const key = normalized.toLocaleLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(normalized);
  }

  return result;
}

export function ProjectPreferencesForm({
  project,
  onSaved,
}: {
  project: Project;
  onSaved: (project: Project) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [districts, setDistricts] = useState("");
  const [moveInTarget, setMoveInTarget] = useState("");
  const [mustHave, setMustHave] = useState("");
  const [dealBreakers, setDealBreakers] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const resetForm = useCallback(() => {
    setDistricts(joinPreferences(project.preferred_districts));
    setMoveInTarget(project.move_in_target ?? "");
    setMustHave(joinPreferences(project.must_have));
    setDealBreakers(joinPreferences(project.deal_breakers));
  }, [project]);

  useEffect(() => {
    if (!editing) resetForm();
  }, [editing, resetForm]);

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    const token = getToken();
    if (!token) {
      setError("Your session has expired. Please sign in again.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const updated = await updateProject(token, project.id, {
        preferred_districts: parsePreferences(districts, true),
        move_in_target: moveInTarget || null,
        must_have: parsePreferences(mustHave),
        deal_breakers: parsePreferences(dealBreakers),
      });
      onSaved(updated);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your conditions.");
    } finally {
      setSaving(false);
    }
  };

  const hasPreferences =
    project.preferred_districts.length > 0 ||
    Boolean(project.move_in_target) ||
    project.must_have.length > 0 ||
    project.deal_breakers.length > 0;

  return (
    <section className="rounded-xl border border-violet-200 bg-violet-50/40 p-4">
      {editing ? (
        <form onSubmit={handleSave} className="space-y-4">
          <div className="flex items-start gap-3">
            <SlidersHorizontal className="mt-0.5 h-5 w-5 shrink-0 text-violet-700" />
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Your rental conditions</h2>
              <p className="mt-1 text-xs leading-5 text-gray-600">
                Areas and move-in date affect system fit checks. Must-haves and deal-breakers are
                saved for communication context until each condition has its own evidence rule.
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-xs font-medium text-gray-700">
              Preferred districts
              <input
                value={districts}
                onChange={(event) => setDistricts(event.target.value)}
                placeholder="Wan Chai, Tai Po"
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal"
              />
              <span className="mt-1 block font-normal text-gray-500">Separate multiple areas with commas.</span>
            </label>
            <label className="text-xs font-medium text-gray-700">
              Target move-in date
              <input
                type="date"
                value={moveInTarget}
                onChange={(event) => setMoveInTarget(event.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal"
              />
              <span className="mt-1 block font-normal text-gray-500">Used for timing fit checks.</span>
            </label>
            <label className="text-xs font-medium text-gray-700">
              Must-have conditions
              <textarea
                value={mustHave}
                onChange={(event) => setMustHave(event.target.value)}
                placeholder={"Example:\nFurnished\nNatural light"}
                rows={4}
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal"
              />
              <span className="mt-1 block font-normal text-gray-500">One condition per line.</span>
            </label>
            <label className="text-xs font-medium text-gray-700">
              Deal-breakers
              <textarea
                value={dealBreakers}
                onChange={(event) => setDealBreakers(event.target.value)}
                placeholder={"Example:\nShared bathroom\nNo lift"}
                rows={4}
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal"
              />
              <span className="mt-1 block font-normal text-gray-500">One condition per line.</span>
            </label>
          </div>

          {error && (
            <p className="flex items-start gap-1 text-xs text-red-700">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                resetForm();
                setError("");
                setEditing(false);
              }}
              disabled={saving}
              className="rounded-md px-3 py-1.5 text-sm text-gray-700 hover:bg-white disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-violet-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-800 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save conditions"}
            </button>
          </div>
        </form>
      ) : (
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
              <SlidersHorizontal className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-wide text-violet-700">Personal conditions</p>
              <p className="mt-1 text-sm font-medium text-gray-900">
                {hasPreferences ? "Your conditions are saved." : "Set your conditions before reviewing candidates."}
              </p>
              <p className="mt-1 text-xs leading-5 text-gray-600">
                {project.preferred_districts.length > 0
                  ? "Preferred areas: " + project.preferred_districts.join(", ")
                  : "No preferred areas yet."}
                {project.move_in_target ? " Move in by " + project.move_in_target + "." : ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              resetForm();
              setError("");
              setEditing(true);
            }}
            className="inline-flex shrink-0 items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-violet-700 hover:bg-white"
          >
            <Pencil className="h-3.5 w-3.5" /> {hasPreferences ? "Edit" : "Set up"}
          </button>
        </div>
      )}
    </section>
  );
}
