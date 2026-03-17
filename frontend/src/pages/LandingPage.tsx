import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  Users,
  GitBranch,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Shield,
  Moon,
  Sun,
  Terminal,
  Bot,
  ArrowRight,
  RefreshCw,
  AlertTriangle,
  Copy,
  CheckCircle2,
  Workflow,
  Github,
} from "lucide-react";
import { SSOLoginFlow } from "../components/Auth/SSOLoginFlow";

const PAIN_POINTS = [
  {
    icon: Copy,
    title: "Context isn't shared",
    description:
      "Developer A teaches Cursor your conventions. Developer B's agent has no idea. Every session starts from scratch.",
    color: "from-red-500 to-orange-400",
  },
  {
    icon: RefreshCw,
    title: "Manual sync doesn't work",
    description: "You update CLAUDE.md. Your teammate's copy is already stale. Copy-paste isn't a strategy.",
    color: "from-amber-500 to-yellow-400",
  },
  {
    icon: AlertTriangle,
    title: "No institutional memory",
    description: "A new team member joins. Their AI makes every mistake your team already solved months ago.",
    color: "from-rose-500 to-pink-400",
  },
];

const FEATURES = [
  {
    icon: Users,
    title: "Team Context Sync",
    description:
      "Write your conventions once. Every team member's AI agent reads the latest version automatically — no manual copying, no stale files.",
    color: "from-blue-500 to-cyan-400",
  },
  {
    icon: Bot,
    title: "Works With Any AI Agent",
    description:
      "Cursor, Claude Code, Copilot, Windsurf — CollabMark syncs to .cursor/rules/, AGENTS.md, and CLAUDE.md. Your agents read context natively.",
    color: "from-violet-500 to-purple-400",
  },
  {
    icon: MessageSquare,
    title: "Real-time Collaboration",
    description:
      "Your whole team edits conventions at the same time. Changes appear instantly — no version conflicts, no lost decisions.",
    color: "from-emerald-500 to-green-400",
  },
  {
    icon: GitBranch,
    title: "Full Version History",
    description:
      "Every convention change is tracked. See who added what rule, compare versions, and roll back if something breaks.",
    color: "from-amber-500 to-orange-400",
  },
  {
    icon: Terminal,
    title: "CLI-First Workflow",
    description:
      "A background daemon that syncs silently. Install, login, start — your agent context stays fresh without lifting a finger.",
    color: "from-rose-500 to-pink-400",
  },
  {
    icon: Shield,
    title: "Enterprise-Ready Auth",
    description:
      "Google SSO, SAML 2.0, API keys — your team's conventions stay behind the authentication you already trust.",
    color: "from-sky-500 to-indigo-400",
  },
];

const STATS = [
  { value: "Instant", label: "Sync across agents", icon: RefreshCw },
  { value: "Team-wide", label: "Shared conventions", icon: Users },
  { value: "Secure", label: "Enterprise-grade auth", icon: Shield },
  { value: "Open Source", label: "Free forever", icon: Github },
];

const CLI_LINES: { text: string; color: string; delay: number }[] = [
  { text: "$ pip install collabmark", color: "text-green-400", delay: 0 },
  { text: "  ✓ Installed collabmark v1.2.0", color: "text-gray-400", delay: 800 },
  { text: "", color: "", delay: 1200 },
  { text: "$ collabmark login", color: "text-green-400", delay: 1500 },
  { text: "  ✓ Logged in as alex@acme.dev", color: "text-gray-400", delay: 2200 },
  { text: "", color: "", delay: 2600 },
  { text: "$ collabmark start", color: "text-green-400", delay: 3000 },
  { text: "  Syncing team conventions...", color: "text-gray-500", delay: 3600 },
  { text: "", color: "", delay: 4000 },
  { text: "  ↓ Synced    coding-standards.md  →  .cursor/rules/", color: "text-cyan-400", delay: 4400 },
  { text: "  ↓ Synced    api-conventions.md   →  CLAUDE.md", color: "text-cyan-400", delay: 5000 },
  { text: "  ↓ Synced    arch-decisions.md    →  AGENTS.md", color: "text-cyan-400", delay: 5600 },
  { text: "  ✓ 3 convention docs synced to local agent context", color: "text-emerald-400", delay: 6200 },
  { text: "", color: "", delay: 6600 },
  { text: "  Watching for team updates...", color: "text-gray-600", delay: 7000 },
  { text: "  ↓ Updated   coding-standards.md", color: "text-cyan-400", delay: 7800 },
  { text: "    Sarah added: 'Use Pydantic v2 validators'", color: "text-amber-400", delay: 8200 },
];

function CliTerminalAnimation() {
  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    CLI_LINES.forEach((line, i) => {
      timers.push(setTimeout(() => setVisibleLines(i + 1), line.delay));
    });
    const loopTimer = setTimeout(() => setVisibleLines(0), CLI_LINES[CLI_LINES.length - 1].delay + 3000);
    timers.push(loopTimer);
    const restartTimer = setTimeout(
      () => {
        setVisibleLines(0);
        CLI_LINES.forEach((line, i) => {
          timers.push(setTimeout(() => setVisibleLines(i + 1), line.delay));
        });
      },
      CLI_LINES[CLI_LINES.length - 1].delay + 3500,
    );
    timers.push(restartTimer);
    return () => timers.forEach(clearTimeout);
  }, []);

  useEffect(() => {
    if (visibleLines === 0) {
      const timers: ReturnType<typeof setTimeout>[] = [];
      CLI_LINES.forEach((line, i) => {
        timers.push(setTimeout(() => setVisibleLines(i + 1), line.delay));
      });
      return () => timers.forEach(clearTimeout);
    }
  }, [visibleLines]);

  return (
    <div className="h-[360px] overflow-hidden px-3 py-3 font-mono text-[11px] leading-relaxed sm:h-[400px] sm:px-4 sm:py-4 sm:text-[13px]">
      {CLI_LINES.slice(0, visibleLines).map((line, i) => (
        <div
          key={i}
          className={`animate-slide-in-right truncate ${line.color}`}
          style={{ animationDelay: `${i * 30}ms` }}
        >
          {line.text || "\u00A0"}
        </div>
      ))}
      {visibleLines > 0 && visibleLines < CLI_LINES.length && (
        <span className="inline-block h-4 w-2 animate-pulse bg-green-400/70" />
      )}
    </div>
  );
}

const SLIDE_INTERVAL = 5000;

export function LandingPage() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [paused, setPaused] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const touchStartX = useRef(0);
  const [scrolled, setScrolled] = useState(false);
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  const toggleDark = useCallback(() => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark" && !dark) {
      document.documentElement.classList.add("dark");
      setDark(true);
    }
  }, []);

  useEffect(() => {
    document.title = "CollabMark — Stop Re-Teaching Your AI Agent the Same Rules";
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
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/KRHero03/collabmark"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)] sm:inline-flex"
          >
            <Github className="h-4 w-4" />
            GitHub
          </a>
          <button
            onClick={toggleDark}
            className="rounded-lg p-2 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            title={dark ? "Light mode" : "Dark mode"}
            aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      {/* --- Hero Section --- */}
      <section className="relative flex min-h-[85vh] items-center justify-center overflow-hidden px-4 pt-20 md:min-h-screen md:pt-16">
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
          <div
            className="animate-fade-in-up mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-white/60 px-4 py-1.5 text-sm font-medium backdrop-blur-sm dark:bg-[var(--color-surface)]/60"
            style={{ animationDelay: "0.05s" }}
          >
            <Bot className="h-4 w-4 text-[var(--color-primary)]" />
            <span>Open source AI context sync</span>
          </div>
          <h1
            className="animate-fade-in-up mb-6 text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl"
            style={{ animationDelay: "0.1s" }}
          >
            Stop re-teaching your AI agent{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
              the same rules
            </span>
          </h1>
          <p
            className="animate-fade-in-up mx-auto mb-10 max-w-2xl text-lg text-[var(--color-text-muted)] sm:text-xl"
            style={{ animationDelay: "0.3s" }}
          >
            CollabMark syncs your team's coding conventions, architecture decisions, and project context so every AI
            agent session starts informed — not from scratch.
          </p>
          <div
            id="get-started"
            className="animate-fade-in-up flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
            style={{ animationDelay: "0.5s" }}
          >
            <SSOLoginFlow />
            <a
              href="https://pypi.org/project/collabmark/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border)] px-8 py-4 text-base font-semibold transition hover:bg-[var(--color-hover)]"
            >
              <Terminal className="h-5 w-5" />
              Install CLI
            </a>
          </div>

          {/* Sync flow diagram */}
          <div className="animate-fade-in-up mx-auto mt-16 max-w-3xl" style={{ animationDelay: "0.7s" }}>
            <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-white shadow-2xl shadow-black/10 dark:bg-[var(--color-surface)]">
              <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-3">
                <div className="h-3 w-3 rounded-full bg-red-400" />
                <div className="h-3 w-3 rounded-full bg-yellow-400" />
                <div className="h-3 w-3 rounded-full bg-green-400" />
                <span className="ml-3 text-xs text-[var(--color-text-muted)]">
                  coding-standards.md — shared with team
                </span>
              </div>
              <div className="flex">
                <div className="flex-1 border-r border-[var(--color-border)] p-3 font-mono text-[11px] leading-6 text-[var(--color-text-muted)] sm:p-4 sm:text-sm">
                  <div>
                    <span className="text-purple-500"># </span>
                    <span className="font-bold text-[var(--color-text)]">Team Coding Standards</span>
                  </div>
                  <div className="mt-2">
                    <span className="text-purple-500">## </span>
                    <span className="font-bold text-[var(--color-text)]">Python Conventions</span>
                  </div>
                  <div>
                    <span className="text-blue-500">- </span>Use Pydantic v2 validators
                  </div>
                  <div>
                    <span className="text-blue-500">- </span>snake_case for all API responses
                  </div>
                  <div>
                    <span className="text-blue-500">- </span>Beanie ODM for MongoDB models
                  </div>
                  <div className="mt-2">
                    <span className="text-purple-500">## </span>
                    <span className="font-bold text-[var(--color-text)]">Architecture Decisions</span>
                  </div>
                  <div>
                    <span className="text-blue-500">- </span>Redis for message bus, not Kafka
                  </div>
                  <div className="mt-2 inline-block rounded bg-blue-100 px-1.5 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                    <span className="animate-pulse">|</span> Sarah is adding a new convention...
                  </div>
                </div>
                <div className="hidden flex-1 p-4 text-xs leading-6 sm:block sm:text-sm">
                  <div className="mb-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                    <span className="text-xs font-medium">Synced to all team agents</span>
                  </div>
                  <div className="space-y-2 text-[var(--color-text-muted)]">
                    <div className="flex items-center gap-2">
                      <Workflow className="h-3.5 w-3.5 flex-shrink-0 text-blue-500" />
                      <span className="text-xs">.cursor/rules/coding-standards.mdc</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Workflow className="h-3.5 w-3.5 flex-shrink-0 text-purple-500" />
                      <span className="text-xs">CLAUDE.md</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Workflow className="h-3.5 w-3.5 flex-shrink-0 text-amber-500" />
                      <span className="text-xs">AGENTS.md</span>
                    </div>
                  </div>
                  <div className="mt-4 rounded-lg border border-[var(--color-border)] p-3">
                    <p className="mb-1 text-xs font-semibold text-[var(--color-text)]">Every agent knows:</p>
                    <ul className="list-inside list-disc space-y-1 text-xs text-[var(--color-text-muted)]">
                      <li>Pydantic v2, not v1</li>
                      <li>snake_case responses</li>
                      <li>Redis over Kafka</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- The Problem Section --- */}
      <section className="border-y border-[var(--color-border)] bg-[var(--color-bg-secondary)] py-16 md:py-28">
        <div className="mx-auto max-w-6xl px-4 md:px-8">
          <h2 className="mb-4 text-center text-2xl font-bold sm:text-3xl md:text-4xl">
            Your team&apos;s AI agents keep{" "}
            <span className="bg-gradient-to-r from-red-500 to-orange-500 bg-clip-text text-transparent dark:from-red-400 dark:to-orange-400">
              learning the same lessons
            </span>
          </h2>
          <p className="mx-auto mb-10 max-w-2xl text-center text-sm text-[var(--color-text-muted)] sm:text-base md:mb-14">
            Every AI agent session starts at zero. Conventions, architecture decisions, and project context all get
            re-taught, re-explained, and re-discovered by every developer on every session.
          </p>
          <div className="grid gap-6 sm:grid-cols-3">
            {PAIN_POINTS.map((point) => (
              <div
                key={point.title}
                className="group rounded-xl border border-[var(--color-border)] bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg dark:bg-[var(--color-surface)]"
              >
                <div
                  className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br ${point.color}`}
                >
                  <point.icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">{point.title}</h3>
                <p className="text-sm text-[var(--color-text-muted)]">{point.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- Feature Carousel --- */}
      <section className="py-16 md:py-28">
        <div className="mx-auto max-w-5xl px-4 md:px-8">
          <h2 className="mb-4 text-center text-2xl font-bold sm:text-3xl md:text-4xl">Built for AI-first teams</h2>
          <p className="mx-auto mb-8 max-w-xl text-center text-sm text-[var(--color-text-muted)] sm:text-base md:mb-12">
            Everything you need to keep your team's AI agents informed and consistent.
          </p>

          <div
            className="group/carousel relative overflow-hidden rounded-xl border border-[var(--color-border)] bg-white p-5 shadow-lg dark:bg-[var(--color-surface)] sm:rounded-2xl sm:p-10"
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
                  className="flex w-full flex-shrink-0 flex-col items-center overflow-hidden px-2 text-center sm:flex-row sm:px-0 sm:text-left"
                >
                  <div
                    className={`mb-4 flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${feat.color} sm:mb-0 sm:mr-10 sm:h-20 sm:w-20`}
                  >
                    <feat.icon className="h-8 w-8 text-white sm:h-10 sm:w-10" />
                  </div>
                  <div className="min-w-0 max-w-full">
                    <h3 className="mb-1 text-lg font-bold sm:mb-2 sm:text-2xl">{feat.title}</h3>
                    <p className="text-sm text-[var(--color-text-muted)] sm:text-base">{feat.description}</p>
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

      {/* --- CLI Demo + How It Works --- */}
      <section className="border-y border-[var(--color-border)] bg-[var(--color-bg-secondary)] py-16 md:py-28">
        <div className="mx-auto max-w-6xl px-4 md:px-8">
          <div className="mb-4 flex justify-center">
            <div className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-500/10 to-purple-500/10 px-4 py-1.5 text-sm font-semibold text-[var(--color-primary)] dark:from-blue-500/20 dark:to-purple-500/20">
              <Terminal className="h-4 w-4" />
              Up and running in 60 seconds
            </div>
          </div>
          <h2 className="mb-4 text-center text-2xl font-bold sm:text-3xl md:text-4xl">
            Three commands.{" "}
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-purple-400">
              Every agent stays in sync.
            </span>
          </h2>
          <p className="mx-auto mb-10 max-w-2xl text-center text-sm text-[var(--color-text-muted)] sm:text-base md:mb-14">
            Write your team&apos;s conventions in CollabMark. The CLI syncs them to every developer&apos;s local agent
            context files — automatically, in the background.
          </p>

          <div className="grid items-center gap-8 lg:grid-cols-2 lg:gap-12">
            {/* Animated CLI Terminal */}
            <div className="relative order-2 lg:order-1">
              <div className="absolute -inset-4 rounded-3xl bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-cyan-500/10 blur-2xl dark:from-blue-500/5 dark:via-purple-500/5 dark:to-cyan-500/5" />
              <div className="relative overflow-hidden rounded-xl border border-[var(--color-border)] bg-[#0d1117] shadow-2xl">
                <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
                  <div className="h-3 w-3 rounded-full bg-red-400" />
                  <div className="h-3 w-3 rounded-full bg-yellow-400" />
                  <div className="h-3 w-3 rounded-full bg-green-400" />
                  <span className="ml-3 font-mono text-xs text-gray-500">~/my-project</span>
                </div>
                <CliTerminalAnimation />
              </div>
            </div>

            {/* Get Started Steps */}
            <div className="order-1 space-y-5 sm:space-y-6 lg:order-2">
              <h3 className="text-lg font-bold sm:text-xl">How it works</h3>
              <div className="flex gap-3 sm:gap-4">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 text-sm font-bold text-white shadow-lg shadow-blue-500/20 sm:h-10 sm:w-10">
                  1
                </div>
                <div className="min-w-0">
                  <h4 className="mb-1 font-semibold">Install & sign in</h4>
                  <p className="text-sm text-[var(--color-text-muted)]">
                    <code className="rounded bg-[var(--color-bg)] px-1.5 py-0.5 text-xs">pip install collabmark</code>{" "}
                    then <code className="rounded bg-[var(--color-bg)] px-1.5 py-0.5 text-xs">collabmark login</code>.
                    Uses the same Google or SSO login your team already has.
                  </p>
                </div>
              </div>
              <div className="flex gap-3 sm:gap-4">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 text-sm font-bold text-white shadow-lg shadow-purple-500/20 sm:h-10 sm:w-10">
                  2
                </div>
                <div className="min-w-0">
                  <h4 className="mb-1 font-semibold">Write your team&apos;s conventions</h4>
                  <p className="text-sm text-[var(--color-text-muted)]">
                    Add coding standards, architecture decisions, and project context on the web. Your team collaborates
                    on these living documents in real time.
                  </p>
                </div>
              </div>
              <div className="flex gap-3 sm:gap-4">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-cyan-600 text-sm font-bold text-white shadow-lg shadow-cyan-500/20 sm:h-10 sm:w-10">
                  3
                </div>
                <div className="min-w-0">
                  <h4 className="mb-1 font-semibold">Start syncing</h4>
                  <p className="text-sm text-[var(--color-text-muted)]">
                    Run <code className="rounded bg-[var(--color-bg)] px-1.5 py-0.5 text-xs">collabmark start</code>.
                    The CLI syncs your team&apos;s conventions to local agent context files. When anyone updates a
                    convention, every agent knows immediately.
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-[var(--color-border)] bg-gradient-to-r from-blue-50 to-purple-50 p-4 dark:from-blue-950/30 dark:to-purple-950/30 sm:p-5">
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <ArrowRight className="h-4 w-4 text-[var(--color-primary)]" />
                  The result
                </div>
                <p className="text-sm text-[var(--color-text-muted)]">
                  Developer A adds &ldquo;Use Pydantic v2 validators&rdquo; to your team&apos;s coding standards.
                  Developer B&apos;s Cursor, Developer C&apos;s Claude, and the new hire&apos;s Copilot all know about
                  it within seconds — without anyone copy-pasting a file.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- Feature Grid --- */}
      <section className="py-16 md:py-28">
        <div className="mx-auto max-w-6xl px-4 md:px-8">
          <h2 className="mb-4 text-center text-2xl font-bold sm:text-3xl md:text-4xl">Everything your team needs</h2>
          <p className="mx-auto mb-8 max-w-xl text-center text-sm text-[var(--color-text-muted)] sm:text-base md:mb-12">
            Sync AI agent context across your entire team with collaborative documents, CLI tools, and enterprise auth.
          </p>
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
      <section className="border-y border-[var(--color-border)] bg-[var(--color-bg-secondary)] py-12 md:py-20">
        <div className="mx-auto max-w-4xl px-4 md:px-8">
          <div className="grid grid-cols-2 gap-6 sm:gap-8 lg:grid-cols-4">
            {STATS.map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="mx-auto mb-2 flex h-11 w-11 items-center justify-center rounded-full bg-[var(--color-primary)]/10 sm:mb-3 sm:h-14 sm:w-14">
                  <stat.icon className="h-5 w-5 text-[var(--color-primary)] sm:h-7 sm:w-7" />
                </div>
                <p className="text-lg font-bold sm:text-2xl">{stat.value}</p>
                <p className="text-xs text-[var(--color-text-muted)] sm:text-sm">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- Final CTA --- */}
      <section className="relative overflow-hidden py-16 md:py-32">
        <div className="animate-gradient absolute inset-0 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-700 opacity-[0.06] dark:opacity-[0.12]" />
        <div className="relative z-10 mx-auto max-w-2xl px-4 text-center md:px-8">
          <h2 className="mb-4 text-2xl font-bold sm:text-3xl md:text-4xl">Your AI agents deserve shared context</h2>
          <p className="mb-8 text-sm text-[var(--color-text-muted)] sm:text-base">
            Open source. Free forever for individual use. Get your team&apos;s AI agents on the same page in under a
            minute.
          </p>
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-4">
            <SSOLoginFlow />
            <a
              href="https://pypi.org/project/collabmark/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border)] px-6 py-3 text-sm font-semibold transition hover:bg-[var(--color-hover)] sm:px-8 sm:py-4 sm:text-base"
            >
              <Terminal className="h-4 w-4 sm:h-5 sm:w-5" />
              Install CLI
            </a>
          </div>
        </div>
      </section>

      {/* --- Footer --- */}
      <footer className="border-t border-[var(--color-border)] py-6 sm:py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 text-xs text-[var(--color-text-muted)] sm:flex-row sm:gap-4 sm:text-sm md:px-8">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-[var(--color-primary)]" />
            <span>CollabMark</span>
          </div>
          <div className="flex gap-6">
            <a href="/api-docs" className="transition hover:text-[var(--color-text)]">
              API Docs
            </a>
            <a
              href="https://pypi.org/project/collabmark/"
              target="_blank"
              rel="noopener noreferrer"
              className="transition hover:text-[var(--color-text)]"
            >
              PyPI
            </a>
            <a
              href="https://github.com/KRHero03/collabmark"
              target="_blank"
              rel="noopener noreferrer"
              className="transition hover:text-[var(--color-text)]"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
