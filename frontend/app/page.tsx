import Link from "next/link";
import { ArrowRight, Bot, ClipboardList, Compass, FileSearch } from "lucide-react";
import { Logo } from "@/components/brand/logo";

const FEATURES = [
  {
    icon: FileSearch,
    title: "Import from any listing source",
    body: "Paste a listing URL, 28hse / Squarefoot / Spacious link, or screenshot. RentWise pulls out the key facts and flags what's missing.",
  },
  {
    icon: ClipboardList,
    title: "AI-assessed candidate pool",
    body: "Each listing is scored against your criteria — budget, area, MTR access, pet policy — so you can focus on the top contenders.",
  },
  {
    icon: Compass,
    title: "Commute evidence for Hong Kong",
    body: "Set a destination once. We geocode via HK Gov ALS and route through Amap to show realistic door-to-door travel times.",
  },
  {
    icon: Bot,
    title: "What to verify next",
    body: "Not sure whether to schedule a viewing or ask for utility bills first? RentWise suggests the next investigative action per candidate.",
  },
];

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-gray-50">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[560px] bg-gradient-to-br from-violet-100 via-blue-50 to-emerald-50"
      />
      <div className="relative mx-auto w-full max-w-5xl px-4 py-10">
        <header className="flex items-center justify-between">
          <Logo
            size={36}
            eyebrow="RentWise"
            tagline="Hong Kong rental research agent"
            href="/"
          />
          <nav className="flex items-center">
            <Link
              href="/login"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-gray-900 px-3.5 text-sm font-medium text-white transition hover:bg-black"
            >
              Sign in
              <ArrowRight className="h-4 w-4" />
            </Link>
          </nav>
        </header>

        <section className="mt-20 text-center">
          <h1 className="text-balance text-4xl font-semibold tracking-tight text-gray-900 sm:text-5xl">
            Organize rental candidates the way a research analyst would.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-balance text-base text-gray-600 sm:text-lg">
            RentWise helps Hong Kong renters collect listings, surface missing facts,
            and decide what to verify next — with AI-powered assessment and real
            door-to-door commute evidence.
          </p>
          <div className="mt-8 flex items-center justify-center">
            <Link
              href="/login"
              className="inline-flex h-11 items-center gap-1.5 rounded-lg bg-gray-900 px-5 text-sm font-medium text-white shadow-sm transition hover:bg-black"
            >
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>

        <section className="mt-20 grid gap-4 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:border-gray-300 hover:shadow-md"
            >
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-gray-400" />
                <h3 className="text-base font-semibold text-gray-900">{title}</h3>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-gray-600">{body}</p>
            </div>
          ))}
        </section>

        <footer className="mt-16 border-t border-gray-200 pt-8 text-center">
          <p className="text-xs text-gray-500">
            Hong Kong rental research · powered by Claude, Amap, and HK Gov ALS
          </p>
        </footer>
      </div>
    </main>
  );
}
