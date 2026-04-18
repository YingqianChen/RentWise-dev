"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  Coins,
  FolderPlus,
  LogOut,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";

import { createProject, deleteProject, getCurrentUser, getProjects } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import type { Project } from "@/lib/types";

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

type ButtonVariant = "default" | "outline" | "ghost" | "danger";
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
        : variant === "danger"
          ? "bg-red-600 text-white hover:bg-red-700"
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

function statusTone(status: Project["status"]) {
  switch (status) {
    case "active":
      return "emerald" as const;
    case "completed":
      return "violet" as const;
    case "archived":
      return "neutral" as const;
    default:
      return "neutral" as const;
  }
}

function statusLabel(status: Project["status"]) {
  switch (status) {
    case "active":
      return "Active";
    case "archived":
      return "Archived";
    case "completed":
      return "Completed";
    default:
      return status;
  }
}

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showDelete, setShowDelete] = useState<Project | null>(null);
  const [title, setTitle] = useState("");
  const [maxBudget, setMaxBudget] = useState("");
  const [user, setUser] = useState<{ email: string } | null>(null);
  const [formError, setFormError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }

    void loadData(token);
  }, [router]);

  const loadData = async (token: string) => {
    try {
      const [userData, projectsData] = await Promise.all([getCurrentUser(token), getProjects(token)]);
      setUser(userData);
      setProjects(projectsData.projects);
    } catch (err) {
      console.error("Failed to load data:", err);
      clearToken();
      router.push("/login");
    } finally {
      setLoading(false);
    }
  };

  const stats = useMemo(() => {
    const active = projects.filter((p) => p.status === "active").length;
    const archived = projects.filter((p) => p.status === "archived").length;
    const completed = projects.filter((p) => p.status === "completed").length;
    return { total: projects.length, active, archived, completed };
  }, [projects]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getToken();
    if (!token) return;

    setCreating(true);
    try {
      setFormError("");
      const newProject = await createProject(token, {
        title,
        max_budget: maxBudget ? parseInt(maxBudget, 10) : undefined,
      });
      setProjects((current) => [newProject, ...current]);
      setShowCreate(false);
      setTitle("");
      setMaxBudget("");
    } catch (err) {
      console.error("Failed to create project:", err);
      setFormError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    const token = getToken();
    if (!token || !showDelete) return;

    setDeletingProjectId(showDelete.id);
    setDeleteError("");
    try {
      await deleteProject(token, showDelete.id);
      setProjects((current) => current.filter((project) => project.id !== showDelete.id));
      setShowDelete(null);
    } catch (err) {
      console.error("Failed to delete project:", err);
      setDeleteError(err instanceof Error ? err.message : "Failed to delete project.");
    } finally {
      setDeletingProjectId(null);
    }
  };

  const handleLogout = () => {
    clearToken();
    router.push("/");
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="flex min-h-screen items-center justify-center text-sm text-gray-500">
          Loading projects...
        </div>
      </main>
    );
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-gray-50">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[360px] bg-gradient-to-br from-violet-100 via-blue-50 to-emerald-50"
      />
      <div className="relative mx-auto w-full max-w-5xl px-4 py-10">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gray-900 text-white shadow-sm">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">
                RentWise
              </p>
              <h1 className="text-2xl font-semibold text-gray-900">Search projects</h1>
              {user && <p className="mt-0.5 text-sm text-gray-500">{user.email}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              New project
            </Button>
            <Button variant="ghost" onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </Button>
          </div>
        </header>

        {projects.length > 0 && (
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Total" value={stats.total} tone="neutral" />
            <StatCard label="Active" value={stats.active} tone="emerald" />
            <StatCard label="Completed" value={stats.completed} tone="violet" />
            <StatCard label="Archived" value={stats.archived} tone="neutral" />
          </div>
        )}

        {projects.length === 0 ? (
          <Card className="mt-8 border-dashed">
            <div className="flex flex-col items-center px-6 py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-50 text-violet-700">
                <FolderPlus className="h-6 w-6" />
              </div>
              <h2 className="mt-4 text-lg font-semibold text-gray-900">No projects yet</h2>
              <p className="mt-1 max-w-sm text-sm text-gray-500">
                Create your first search workspace and start organizing rental candidates with
                AI-powered assessment.
              </p>
              <Button className="mt-6" onClick={() => setShowCreate(true)}>
                <Plus className="h-4 w-4" />
                Create project
              </Button>
            </div>
          </Card>
        ) : (
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Card
                key={project.id}
                className="group relative overflow-hidden transition hover:border-gray-300 hover:shadow-md"
              >
                <Link href={`/projects/${project.id}`} className="block p-5">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="line-clamp-2 text-base font-semibold text-gray-900">
                      {project.title}
                    </h3>
                    <ArrowRight className="h-4 w-4 shrink-0 text-gray-400 transition group-hover:translate-x-0.5 group-hover:text-gray-700" />
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <Badge tone={statusTone(project.status)}>{statusLabel(project.status)}</Badge>
                    {project.max_budget ? (
                      <Badge tone="blue">
                        <Coins className="h-3 w-3" />
                        HKD {project.max_budget.toLocaleString()}
                      </Badge>
                    ) : (
                      <Badge tone="neutral">No budget cap</Badge>
                    )}
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setDeleteError("");
                    setShowDelete(project);
                  }}
                  aria-label={`Delete ${project.title}`}
                  className="absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </Card>
            ))}
          </div>
        )}
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-md rounded-xl border border-gray-200 bg-white shadow-xl">
            <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50 text-violet-700">
                <FolderPlus className="h-4 w-4" />
              </div>
              <h2 className="text-base font-semibold text-gray-900">Create project</h2>
            </div>
            <form onSubmit={handleCreate} className="space-y-4 px-5 py-5">
              <div>
                <label
                  htmlFor="project-title"
                  className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-600"
                >
                  Project title
                </label>
                <div className="relative">
                  <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    id="project-title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                    autoFocus
                    className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
                    placeholder="Spring 2026 search"
                  />
                </div>
              </div>
              <div>
                <label
                  htmlFor="project-budget"
                  className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-600"
                >
                  Budget cap in HKD (optional)
                </label>
                <div className="relative">
                  <Coins className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    id="project-budget"
                    type="number"
                    value={maxBudget}
                    onChange={(e) => setMaxBudget(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
                    placeholder="22000"
                  />
                </div>
              </div>
              {formError && (
                <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}
              <div className="flex justify-end gap-2 pt-1">
                <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={creating}>
                  {creating ? "Creating..." : "Create project"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-md rounded-xl border border-gray-200 bg-white shadow-xl">
            <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-50 text-red-600">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <h2 className="text-base font-semibold text-gray-900">Delete project</h2>
            </div>
            <div className="space-y-4 px-5 py-5">
              <p className="text-sm text-gray-700">
                Delete <span className="font-medium text-gray-900">{showDelete.title}</span> and
                all of its candidates, assessments, and investigation items?
              </p>
              <p className="text-xs text-red-600">This action cannot be undone.</p>
              {deleteError && (
                <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{deleteError}</span>
                </div>
              )}
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowDelete(null)}
                  disabled={deletingProjectId === showDelete.id}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => void handleDelete()}
                  disabled={deletingProjectId === showDelete.id}
                >
                  <Trash2 className="h-4 w-4" />
                  {deletingProjectId === showDelete.id ? "Deleting..." : "Delete project"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "neutral" | "emerald" | "violet";
}) {
  const accent =
    tone === "emerald"
      ? "text-emerald-700"
      : tone === "violet"
        ? "text-violet-700"
        : "text-gray-900";
  return (
    <Card className="px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold", accent)}>{value}</p>
    </Card>
  );
}
