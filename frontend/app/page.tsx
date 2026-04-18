import Link from "next/link";
import {
  ArrowRight,
  Bot,
  ClipboardList,
  Compass,
  FileSearch,
  MapPin,
  Sparkles,
} from "lucide-react";

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

const FEATURES = [
  {
    icon: FileSearch,
    title: "Import from any listing source",
    body: "Paste a listing URL, 28hse / Squarefoot / Spacious link, or screenshot. RentWise pulls out the key facts and flags what's missing.",
    tone: "violet" as const,
  },
  {
    icon: ClipboardList,
    title: "AI-assessed candidate pool",
    body: "Each listing is scored against your criteria — budget, area, MTR access, pet policy — so you can focus on the top contenders.",
    tone: "emerald" as const,
  },
  {
    icon: Compass,
    title: "Commute evidence for Hong Kong",
    body: "Set a destination once. We geocode via HK Gov ALS and route through Amap to show realistic door-to-door travel times.",
    tone: "blue" as const,
  },
  {
    icon: Bot,
    title: "What to verify next",
    body: "Not sure whether to schedule a viewing or ask for utility bills first? RentWise suggests the next investigative action per candidate.",
    tone: "amber" as const,
  },
];

const TONE_STYLES: Record<
  "violet" | "emerald" | "blue" | "amber",
  { bg: string; fg: string }
> = {
  violet: { bg: "bg-violet-50", fg: "text-violet-700" },
  emerald: { bg: "bg-emerald-50", fg: "text-emerald-700" },
  blue: { bg: "bg-blue-50", fg: "text-blue-700" },
  amber: { bg: "bg-amber-50", fg: "text-amber-700" },
};

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-gray-50">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[560px] bg-gradient-to-br from-violet-100 via-blue-50 to-emerald-50"
      />
      <div className="relative mx-auto w-full max-w-5xl px-4 py-10">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gray-900 text-white shadow-sm">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">
                RentWise
              </p>
              <p className="text-xs text-gray-500">Hong Kong rental research agent</p>
            </div>
          </div>
          <nav className="flex items-center gap-2">
            <Link
              href="/login"
              className="inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium text-gray-600 transition hover:bg-gray-100 hover:text-gray-900"
            >
              Sign in
            </Link>
            <Link
              href="/projects"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-gray-900 px-3.5 text-sm font-medium text-white transition hover:bg-black"
            >
              Open workspace
              <ArrowRight className="h-4 w-4" />
            </Link>
          </nav>
        </header>

        <section className="mt-16 text-center">
          <div className="mx-auto inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white/70 px-3 py-1 text-xs font-medium text-gray-600 shadow-sm backdrop-blur">
            <MapPin className="h-3.5 w-3.5 text-violet-600" />
            Built for Hong Kong renters
          </div>
          <h1 className="mt-5 text-balance text-4xl font-semibold tracking-tight text-gray-900 sm:text-5xl">
            Organize rental candidates the way a research analyst would.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-balance text-base text-gray-600 sm:text-lg">
            RentWise helps Hong Kong renters collect listings, surface missing facts,
            and decide what to verify next — with AI-powered assessment and real
            door-to-door commute evidence.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/login"
              className="inline-flex h-11 items-center gap-1.5 rounded-lg bg-gray-900 px-5 text-sm font-medium text-white shadow-sm transition hover:bg-black"
            >
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/projects"
              className="inline-flex h-11 items-center rounded-lg border border-gray-300 bg-white px-5 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
            >
              Open existing workspace
            </Link>
          </div>
        </section>

        <section className="mt-20 grid gap-4 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body, tone }) => {
            const style = TONE_STYLES[tone];
            return (
              <div
                key={title}
                className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-gray-300 hover:shadow-md"
              >
                <div
                  className={cn(
                    "inline-flex h-9 w-9 items-center justify-center rounded-lg",
                    style.bg,
                    style.fg
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-gray-900">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-gray-600">{body}</p>
              </div>
            );
          })}
        </section>

        <footer className="mt-16 flex flex-col items-center gap-2 border-t border-gray-200 pt-8 text-center">
          <p className="text-xs text-gray-500">
            Hong Kong rental research · powered by Claude, Amap, and HK Gov ALS
          </p>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <Link href="/login" className="hover:text-gray-800">
              Sign in
            </Link>
            <span aria-hidden>·</span>
            <Link href="/projects" className="hover:text-gray-800">
              Open workspace
            </Link>
          </div>
        </footer>
      </div>
    </main>
  );
}
