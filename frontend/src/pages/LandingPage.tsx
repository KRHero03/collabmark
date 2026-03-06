import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  Users,
  GitBranch,
  MessageSquare,
  FolderTree,
  Code,
  Share2,
  ChevronLeft,
  ChevronRight,
  Zap,
  Shield,
  Globe,
} from "lucide-react";
import { SSOLoginFlow } from "../components/Auth/SSOLoginFlow";

const FEATURES = [
  {
    icon: Users,
    title: "Real-time Collaboration",
    description:
      "Edit simultaneously with your team. Zero conflicts -- every keystroke merges automatically, no matter how many people are editing.",
    color: "from-blue-500 to-cyan-400",
  },
  {
    icon: GitBranch,
    title: "Version History & Diff",
    description:
      "Every change is auto-versioned. Browse history, see line-by-line diffs, and restore any version with one click.",
    color: "from-violet-500 to-purple-400",
  },
  {
    icon: MessageSquare,
    title: "Inline Comments",
    description:
      "Select text and leave comments exactly where they matter. Threaded replies, resolution, and anchor tracking.",
    color: "from-amber-500 to-orange-400",
  },
  {
    icon: FolderTree,
    title: "Spaces & Folders",
    description:
      "Organize documents in a hierarchical folder structure. Share entire folders with granular access control.",
    color: "from-emerald-500 to-green-400",
  },
  {
    icon: Code,
    title: "Markdown & Mermaid",
    description:
      "Full GitHub-flavored Markdown with live preview. Embed Mermaid diagrams, syntax-highlighted code blocks, and math.",
    color: "from-rose-500 to-pink-400",
  },
  {
    icon: Share2,
    title: "Seamless Sharing",
    description:
      "Share by email, set view or edit permissions, or open access to anyone with the link. You control who sees what.",
    color: "from-sky-500 to-indigo-400",
  },
];

const STATS = [
  { value: "Real-time", label: "Collaboration", icon: Zap },
  { value: "Auto", label: "Versioning", icon: Shield },
  { value: "Granular", label: "Access Control", icon: Globe },
];

const SLIDE_INTERVAL = 5000;

export function LandingPage() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [paused, setPaused] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const touchStartX = useRef(0);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    document.title = "CollabMark -- Collaborative Markdown Editor";
    return () => {
      document.title = "CollabMark";
    };
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const nextSlide = useCallback(() => setCurrentSlide((p) => (p + 1) % FEATURES.length), []);
  const prevSlide = useCallback(() => setCurrentSlide((p) => (p - 1 + FEATURES.length) % FEATURES.length), []);

  useEffect(() => {
    if (paused) return;
    intervalRef.current = setInterval(nextSlide, SLIDE_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [paused, nextSlide]);

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) > 50) {
      if (dx > 0) {
        prevSlide();
      } else {
        nextSlide();
      }
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* --- Sticky Top Bar --- */}
      <nav
        className={`fixed inset-x-0 top-0 z-50 flex h-16 items-center justify-between px-4 transition-all duration-300 md:px-8 ${
          scrolled
            ? "border-b border-[var(--color-border)] bg-gradient-to-r from-white via-white to-blue-50/60 shadow-sm backdrop-blur-lg dark:from-[#0f172a]/90 dark:via-[#0f172a]/90 dark:to-indigo-950/40"
            : "bg-white/5 backdrop-blur-sm"
        }`}
      >
        <div className="flex items-center gap-2 text-lg font-bold">
          <FileText className="h-6 w-6 text-[var(--color-primary)]" />
          <span>CollabMark</span>
        </div>
        <a
          href="#get-started"
          className="rounded-lg bg-[var(--color-primary)] px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        >
          Sign In
        </a>
      </nav>

      {/* --- Hero Section --- */}
      <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 pt-16">
        <div className="animate-gradient absolute inset-0 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 opacity-[0.07] dark:opacity-[0.15]" />

        <div className="animate-float absolute left-[10%] top-[20%] h-64 w-64 rounded-full bg-blue-400/10 blur-3xl dark:bg-blue-400/5" />
        <div
          className="animate-float absolute bottom-[15%] right-[10%] h-80 w-80 rounded-full bg-purple-400/10 blur-3xl dark:bg-purple-400/5"
          style={{ animationDelay: "2s" }}
        />
        <div
          className="animate-float absolute right-[30%] top-[60%] h-48 w-48 rounded-full bg-cyan-400/10 blur-3xl dark:bg-cyan-400/5"
          style={{ animationDelay: "4s" }}
        />

        <div className="relative z-10 mx-auto max-w-4xl text-center">
          <h1
            className="animate-fade-in-up mb-6 text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl"
            style={{ animationDelay: "0.1s" }}
          >
            Collaborative Markdown,{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
              Supercharged
            </span>
          </h1>
          <p
            className="animate-fade-in-up mx-auto mb-10 max-w-2xl text-lg text-[var(--color-text-muted)] sm:text-xl"
            style={{ animationDelay: "0.3s" }}
          >
            Real-time editing, version history with diffs, inline comments, folder organization, and seamless sharing --
            all in a beautiful Markdown editor.
          </p>
          <div
            id="get-started"
            className="animate-fade-in-up flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
            style={{ animationDelay: "0.5s" }}
          >
            <SSOLoginFlow />
            <a
              href="/api-docs"
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border)] px-8 py-4 text-base font-semibold transition hover:bg-[var(--color-hover)]"
            >
              View API Docs
            </a>
          </div>

          {/* Abstract editor illustration */}
          <div className="animate-fade-in-up mx-auto mt-16 max-w-3xl" style={{ animationDelay: "0.7s" }}>
            <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white shadow-2xl shadow-black/10 dark:bg-[var(--color-surface)]">
              <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-3">
                <div className="h-3 w-3 rounded-full bg-red-400" />
                <div className="h-3 w-3 rounded-full bg-yellow-400" />
                <div className="h-3 w-3 rounded-full bg-green-400" />
                <span className="ml-3 text-xs text-[var(--color-text-muted)]">README.md</span>
              </div>
              <div className="flex">
                <div className="flex-1 border-r border-[var(--color-border)] p-4 font-mono text-xs leading-6 text-[var(--color-text-muted)] sm:text-sm">
                  <div>
                    <span className="text-purple-500"># </span>
                    <span className="font-bold text-[var(--color-text)]">Project Overview</span>
                  </div>
                  <div className="mt-2">Welcome to our collaborative docs.</div>
                  <div className="mt-2">
                    <span className="text-purple-500">## </span>
                    <span className="font-bold text-[var(--color-text)]">Features</span>
                  </div>
                  <div>
                    <span className="text-blue-500">- </span>Real-time sync
                  </div>
                  <div>
                    <span className="text-blue-500">- </span>Version history
                  </div>
                  <div>
                    <span className="text-blue-500">- </span>Inline comments
                  </div>
                  <div className="mt-2 inline-block rounded bg-blue-100 px-1.5 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                    <span className="animate-pulse">|</span> Sarah is typing...
                  </div>
                </div>
                <div className="hidden flex-1 p-4 text-xs leading-6 sm:block sm:text-sm">
                  <h3 className="text-base font-bold">Project Overview</h3>
                  <p className="mt-2 text-[var(--color-text-muted)]">Welcome to our collaborative docs.</p>
                  <h4 className="mt-3 text-sm font-bold">Features</h4>
                  <ul className="mt-1 list-inside list-disc text-[var(--color-text-muted)]">
                    <li>Real-time sync</li>
                    <li>Version history</li>
                    <li>Inline comments</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- Feature Carousel --- */}
      <section className="py-20 md:py-28">
        <div className="mx-auto max-w-5xl px-4 md:px-8">
          <h2 className="mb-4 text-center text-3xl font-bold md:text-4xl">Everything you need</h2>
          <p className="mx-auto mb-12 max-w-xl text-center text-[var(--color-text-muted)]">
            A complete toolkit for teams that think in Markdown.
          </p>

          <div
            className="group/carousel relative overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white p-6 shadow-lg dark:bg-[var(--color-surface)] sm:p-10"
            onMouseEnter={() => setPaused(true)}
            onMouseLeave={() => setPaused(false)}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          >
            <div
              className="flex transition-transform duration-500 ease-in-out"
              style={{ transform: `translateX(-${currentSlide * 100}%)` }}
            >
              {FEATURES.map((feat) => (
                <div
                  key={feat.title}
                  className="flex w-full flex-shrink-0 flex-col items-center text-center sm:flex-row sm:text-left"
                >
                  <div
                    className={`mb-6 flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${feat.color} sm:mb-0 sm:mr-10`}
                  >
                    <feat.icon className="h-10 w-10 text-white" />
                  </div>
                  <div>
                    <h3 className="mb-2 text-xl font-bold sm:text-2xl">{feat.title}</h3>
                    <p className="max-w-md text-[var(--color-text-muted)]">{feat.description}</p>
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={prevSlide}
              className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-[var(--color-bg)]/60 p-2 opacity-0 backdrop-blur-sm transition-opacity duration-200 hover:bg-[var(--color-bg)]/90 group-hover/carousel:opacity-100 sm:left-4"
              aria-label="Previous slide"
            >
              <ChevronLeft className="h-5 w-5 text-[var(--color-text-muted)]" />
            </button>
            <button
              onClick={nextSlide}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-[var(--color-bg)]/60 p-2 opacity-0 backdrop-blur-sm transition-opacity duration-200 hover:bg-[var(--color-bg)]/90 group-hover/carousel:opacity-100 sm:right-4"
              aria-label="Next slide"
            >
              <ChevronRight className="h-5 w-5 text-[var(--color-text-muted)]" />
            </button>
          </div>

          {/* Dot indicators */}
          <div className="mt-6 flex justify-center gap-2">
            {FEATURES.map((feat, i) => (
              <button
                key={feat.title}
                onClick={() => setCurrentSlide(i)}
                className={`h-2.5 rounded-full transition-all ${
                  i === currentSlide
                    ? "w-8 bg-[var(--color-primary)]"
                    : "w-2.5 bg-[var(--color-border)] hover:bg-[var(--color-text-muted)]"
                }`}
                aria-label={`Go to slide ${i + 1}`}
              />
            ))}
          </div>
        </div>
      </section>

      {/* --- Feature Grid --- */}
      <section className="border-y border-[var(--color-border)] bg-[var(--color-bg-secondary)] py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-4 md:px-8">
          <h2 className="mb-12 text-center text-3xl font-bold md:text-4xl">Built for modern teams</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feat) => (
              <div
                key={feat.title}
                className="group rounded-xl border border-[var(--color-border)] bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg dark:bg-[var(--color-surface)]"
              >
                <div
                  className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br ${feat.color}`}
                >
                  <feat.icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">{feat.title}</h3>
                <p className="text-sm text-[var(--color-text-muted)]">{feat.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- Stats --- */}
      <section className="py-20 md:py-28">
        <div className="mx-auto max-w-4xl px-4 md:px-8">
          <div className="grid gap-8 sm:grid-cols-3">
            {STATS.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-primary)]/10">
                  <stat.icon className="h-7 w-7 text-[var(--color-primary)]" />
                </div>
                <p className="text-2xl font-bold">{stat.value}</p>
                <p className="text-sm text-[var(--color-text-muted)]">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- Final CTA --- */}
      <section className="relative overflow-hidden py-24 md:py-32">
        <div className="animate-gradient absolute inset-0 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-700 opacity-[0.06] dark:opacity-[0.12]" />
        <div className="relative z-10 mx-auto max-w-2xl px-4 text-center md:px-8">
          <h2 className="mb-4 text-3xl font-bold md:text-4xl">Start collaborating now</h2>
          <p className="mb-8 text-[var(--color-text-muted)]">
            Free to use. No credit card required. Sign in and create your first document in seconds.
          </p>
          <div className="flex justify-center">
            <SSOLoginFlow />
          </div>
        </div>
      </section>

      {/* --- Footer --- */}
      <footer className="border-t border-[var(--color-border)] py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 text-sm text-[var(--color-text-muted)] sm:flex-row md:px-8">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-[var(--color-primary)]" />
            <span>CollabMark</span>
          </div>
          <div className="flex gap-6">
            <a href="/api-docs" className="transition hover:text-[var(--color-text)]">
              API Docs
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
