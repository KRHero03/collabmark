# Reddit Engagement Playbook

## Strategy

Be genuinely helpful first. Link to CollabMark only when it naturally fits the conversation. The goal is 5-10 helpful comments per week across target subreddits.

## Target Subreddits

| Subreddit | Subscribers | Why |
|-----------|------------|-----|
| r/cursor | ~100k+ | Cursor users dealing with .cursor/rules/ management |
| r/ClaudeAI | ~200k+ | Claude users managing CLAUDE.md across teams |
| r/ClaudeCode | ~50k+ | Claude Code users sharing conventions |
| r/ChatGPTCoding | ~100k+ | AI coding users with context issues |
| r/ExperiencedDevs | ~200k+ | Senior devs who'd appreciate the architecture |
| r/SideProject | ~100k+ | For "Show" posts during soft launch |

## Trigger Keywords to Monitor

Search these phrases weekly in the target subreddits:

- "CLAUDE.md" + "team" or "share"
- ".cursor/rules" + "sync" or "team"
- "AGENTS.md" + "manage"
- "AI agent" + "context" or "conventions"
- "cursor keeps forgetting"
- "how do you share rules"
- "context between sessions"
- "AI coding conventions"
- "teaching AI the same thing"

## Response Templates

### Scenario 1: "How do you manage CLAUDE.md across a team?"

**Context**: Someone asks how to share Claude/Cursor rules with teammates.

> This is a real pain point. We've tried a few approaches:
>
> 1. **Git-committed files** — works but you're always one `git pull` behind. Convention changes propagate slowly.
> 2. **Shared folder with symlinks** — brittle, OS-dependent, breaks when paths differ.
> 3. **Copy-paste in Slack** — doesn't scale past 2 people.
>
> The core issue is that AI agent context files are inherently *local* to each developer's machine, but conventions are inherently *team-level* knowledge. You need something that bridges that gap automatically.
>
> I've been building an open-source tool called [CollabMark](https://github.com/KRHero03/collabmark) that does this — collaborative docs on the web that sync to local agent files via a CLI daemon. It writes to `.cursor/rules/`, `CLAUDE.md`, and `AGENTS.md` so every AI tool reads context natively.
>
> Happy to share more if helpful.

### Scenario 2: "My Cursor keeps forgetting my project conventions"

**Context**: Someone frustrated with context loss between sessions.

> This is one of the most common frustrations with AI agents. A few things that help:
>
> 1. **Use `.cursor/rules/` files** (not the old `.cursorrules`). Put separate `.mdc` files for different concerns — coding standards, architecture decisions, API patterns. Cursor reads them automatically.
>
> 2. **Keep each file focused** — under 2 screens of content. Shorter files get read more reliably by the agent.
>
> 3. **Use "Always Apply" mode** for critical conventions and "Apply Intelligently" for domain-specific rules.
>
> The bigger problem is keeping these files in sync across the team. If you're working with others, check out [CollabMark](https://github.com/KRHero03/collabmark) — it syncs team conventions to local agent context files automatically so everyone's agents stay up to date.

### Scenario 3: "AGENTS.md vs CLAUDE.md vs .cursorrules — which do I need?"

**Context**: Someone confused about the different formats.

> TL;DR: Use all three. They don't conflict — each tool reads only its own files.
>
> - **AGENTS.md** — Universal standard, read by Cursor, Claude Code, Copilot, Windsurf, and 15+ tools. Best bet for "write once, works everywhere."
> - **CLAUDE.md** — Claude Code-specific. Has a nice three-level hierarchy (global → project → local) for overrides.
> - **.cursor/rules/** — Cursor-specific. Supports activation modes (always, intelligent, file-specific). The most granular option.
>
> For a team, my recommendation: write your core conventions once and have them available in all formats. Maintaining 3 files manually is painful, but there are tools that can sync a single source of truth to all three.

### Scenario 4: "How do you onboard new devs with AI agents?"

**Context**: Discussion about onboarding and AI agent setup.

> The onboarding problem with AI agents is underrated. When a new dev joins:
>
> 1. They set up their AI tool from scratch
> 2. Their agent has zero knowledge of your team's conventions
> 3. They spend days discovering rules the team figured out months ago
> 4. They make the same mistakes everyone else already made
>
> What's worked for us: maintain a living document of team conventions (coding standards, architecture decisions, "don't do X because of Y") and auto-sync it to every developer's local agent context. New hires run one command and their AI agent immediately knows everything the team has learned.
>
> The key insight is that conventions shouldn't live in one person's setup — they should be collaborative, versioned, and automatically distributed.

### Scenario 5: r/SideProject Launch Post

**Title**: "I built an open-source tool that syncs AI agent context across team members"

> **The problem**: Every AI agent session starts at zero. Developer A's Cursor learns your project uses Pydantic v2 validators. Developer B's Claude has no idea. A new hire's Copilot makes every mistake your team already solved.
>
> **What I built**: [CollabMark](https://github.com/KRHero03/collabmark) — an open-source collaborative editor + CLI that syncs your team's coding conventions to every developer's local agent context files (`.cursor/rules/`, `CLAUDE.md`, `AGENTS.md`).
>
> **How it works**:
> 1. Write your team's conventions on CollabMark's web editor (real-time collaboration, version history)
> 2. Each developer runs `collabmark start` — a background daemon syncs conventions to local files
> 3. When anyone updates a convention, every agent knows within seconds
>
> **Tech stack**: FastAPI + React + CRDTs (Yjs/pycrdt) for conflict-free sync, MongoDB, Redis, deployed on Railway.
>
> It's free and open source. Looking for feedback from teams that use AI agents daily.
>
> GitHub: https://github.com/KRHero03/collabmark
> PyPI: `pip install collabmark`

## Rules of Engagement

1. **Be helpful first.** If someone's question can be answered without mentioning CollabMark, answer it fully without mentioning CollabMark.
2. **Don't self-promote in every comment.** Aim for 70% genuinely helpful answers, 30% naturally include a mention.
3. **Never be the first to comment on your own post.** Wait for organic engagement.
4. **Respond to every reply.** If someone asks a follow-up question, answer promptly and thoroughly.
5. **Upvote and engage with similar discussions.** Be a visible, helpful member of these communities.
6. **Don't bash competitors.** Frame CollabMark as a solution, not as "better than X."
7. **Link to the article when deeper explanation is needed.** The Dev.to article provides the full story.

## Weekly Cadence

| Day | Action |
|-----|--------|
| Monday | Search target subreddits for trigger keywords. Comment on 2-3 relevant threads. |
| Wednesday | Check for new discussions. Reply to any responses on previous comments. |
| Friday | Share something useful (tip, observation, short guide) without self-promotion. |

## Tracking

Track engagement in a simple spreadsheet:

| Date | Subreddit | Post Title | Comment Link | Self-promo? | Upvotes | Replies |
|------|-----------|-----------|--------------|-------------|---------|---------|
| | | | | Yes/No | | |
