"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, Home, Lock, Mail, Sparkles } from "lucide-react";

import { login, register } from "@/lib/api";
import { setToken } from "@/lib/auth";

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = isRegister ? await register(email, password) : await login(email, password);
      setToken(result.access_token);
      router.push("/projects");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-gray-50">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[520px] bg-gradient-to-br from-violet-100 via-blue-50 to-emerald-50"
      />
      <div className="relative mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-4 py-12">
        <Link
          href="/"
          className="mb-6 inline-flex items-center gap-1 self-start text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to home
        </Link>

        <div className="mb-6 flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-900 text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">
              RentWise
            </p>
            <p className="text-xs text-gray-500">Hong Kong rental research agent</p>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h1 className="text-xl font-semibold text-gray-900">
            {isRegister ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {isRegister
              ? "Start organizing rental candidates with AI-powered assessment."
              : "Sign in to continue where you left off."}
          </p>

          {error && (
            <div className="mt-5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div>
              <label
                htmlFor="email"
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-600"
              >
                Email
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
                  placeholder="you@example.com"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-600"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="password"
                  type="password"
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30"
                  placeholder="At least 6 characters"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={cn(
                "inline-flex h-10 w-full items-center justify-center rounded-lg bg-gray-900 px-4 text-sm font-medium text-white transition hover:bg-black focus:outline-none focus:ring-2 focus:ring-primary-500/40",
                loading && "opacity-60"
              )}
            >
              {loading ? "Working..." : isRegister ? "Create account" : "Sign in"}
            </button>
          </form>

          <div className="mt-5 border-t border-gray-100 pt-4 text-center text-sm text-gray-600">
            {isRegister ? "Already have an account?" : "No account yet?"}
            <button
              type="button"
              onClick={() => setIsRegister(!isRegister)}
              className="ml-1 font-medium text-primary-600 hover:text-primary-700"
            >
              {isRegister ? "Sign in" : "Create one"}
            </button>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          <Home className="mr-1 inline h-3 w-3" />
          Hong Kong rental research · powered by Claude
        </p>
      </div>
    </main>
  );
}
