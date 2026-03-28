# Product Hunt & Hacker News Launch Plan

## Product Hunt Submission

### Timing
- **Day**: Tuesday or Wednesday
- **Time**: 12:01 AM PST (to maximize the full 24-hour cycle)
- **Ideal window**: During Week 4 of the GTM plan, after the Dev.to article has been published and Reddit engagement has started

### Listing Details

**Product Name**: CollabMark

**Tagline** (60 chars max):
> Stop re-teaching your AI agent the same rules

**Description** (260 chars max):
> Your team's AI agents keep learning the same conventions from scratch. CollabMark syncs coding standards, architecture decisions, and project context across Cursor, Claude, and Copilot — so every session starts informed.

**Longer Description**:
> Every AI agent session starts at zero. Developer A teaches Cursor your conventions. Developer B's Claude has no idea. New hires spend days discovering rules the team solved months ago.
>
> CollabMark fixes this with two simple pieces:
>
> **A collaborative web editor** where your team writes and maintains coding conventions, architecture decisions, and project context — with real-time editing, version history, and inline comments.
>
> **A CLI daemon** (`pip install collabmark`) that runs in the background and syncs your team's documents to local agent context files. Changes propagate to `.cursor/rules/`, `CLAUDE.md`, and `AGENTS.md` within seconds.
>
> The result: when anyone updates a convention, every team member's AI agent knows about it immediately. No copy-pasting files. No stale CLAUDE.md. No re-teaching the same lessons.
>
> Open source, free forever for individuals, powered by CRDTs for conflict-free real-time sync.

**Topics/Categories**:
- Developer Tools
- Artificial Intelligence
- Open Source
- Productivity
- Collaboration

**Links**:
- Website: https://web-production-5e1bc.up.railway.app (or collabmark.is-a.dev when approved)
- GitHub: https://github.com/KRHero03/collabmark
- PyPI: https://pypi.org/project/collabmark/

**Maker Comment** (post immediately after launch):
> Hey everyone! I'm the maker of CollabMark.
>
> I built this because my team kept running into the same problem: every AI agent session starts from scratch. We'd spend 15-20 minutes at the start of each session re-teaching Cursor our coding conventions, only to realize other team members were doing the exact same thing independently.
>
> CLAUDE.md files help for solo use, but they don't scale to teams. Someone updates conventions, and within a day everyone has a different version. New hires have no idea what the team has learned.
>
> CollabMark makes AI agent context a shared, synced, living document:
> - Write conventions collaboratively on the web
> - CLI syncs to local agent files automatically
> - Works with Cursor, Claude Code, Copilot, and any tool that reads markdown context files
>
> It's completely open source (MIT). Would love feedback from teams using AI agents daily!
>
> Happy to answer any questions about the architecture (CRDTs for sync, FastAPI + React, MongoDB) or the product direction.

### Pre-Launch Checklist

- [ ] Have 5+ people ready to leave genuine comments/upvotes on launch day
- [ ] Dev.to article is published and has some traction
- [ ] Reddit engagement has been active for 2+ weeks
- [ ] Landing page is live with the new positioning
- [ ] README is updated with problem-first messaging
- [ ] GitHub repo has a proper description, topics, and social preview image
- [ ] All links in the Product Hunt listing work
- [ ] CLI is installable and working on PyPI
- [ ] Web app is stable and fast

### Launch Day Protocol

1. **12:01 AM PST**: Submit to Product Hunt
2. **Immediately after**: Post maker comment
3. **Morning**: Share on Twitter/X with personal story
4. **Mid-day**: Post in relevant Discord servers (if member)
5. **Afternoon**: Respond to every comment on Product Hunt
6. **Evening**: Share update/thank you tweet if getting traction

---

## Hacker News "Show HN" Submission

### Timing
- Same week as Product Hunt, but different day (Thursday or Friday)
- HN audience is different from PH — more technical, more skeptical

### Title
> Show HN: CollabMark – Sync AI agent context (cursor rules, CLAUDE.md) across your team

### Submission Text

> I built CollabMark because my team kept re-teaching our AI agents the same conventions.
>
> Developer A's Cursor learns we use Pydantic v2 validators. Developer B opens Claude the next day and gets v1 generated. A new hire joins and spends a week discovering conventions we figured out months ago.
>
> CLAUDE.md and .cursor/rules/ files help for individual use, but they don't sync across a team. Someone updates conventions locally; everyone else has a stale copy.
>
> CollabMark is a collaborative editor + CLI daemon that solves this:
>
> 1. Write team conventions on the web (real-time collaboration, version history, comments)
> 2. `pip install collabmark && collabmark login && collabmark start`
> 3. CLI syncs to .cursor/rules/, CLAUDE.md, AGENTS.md automatically
>
> When anyone updates a convention, every developer's agent knows within seconds.
>
> Tech: FastAPI + React + CRDTs (Yjs/pycrdt) for conflict-free sync. MongoDB for storage, Redis for pub/sub. CLI uses pycrdt for bidirectional CRDT sync (same protocol as the web editor).
>
> Open source (MIT): https://github.com/KRHero03/collabmark
> PyPI: pip install collabmark
> Live: https://web-production-5e1bc.up.railway.app

### HN-Specific Notes

- HN values technical depth. Be ready to explain CRDT implementation, sync protocol, and architecture decisions
- Don't use marketing language ("revolutionary", "game-changing") — HN audience dislikes this
- Be honest about limitations (early stage, small team, free tier hosting)
- Respond to every comment, especially critical ones, with humility and technical detail

### Prepared Responses for Common HN Questions

**"Why not just commit CLAUDE.md to the repo?"**
> You can, and many teams do. The differences: (1) real-time sync vs commit-push-pull cadence, (2) collaborative editing with presence and comments, (3) conventions that span multiple repos, (4) automatic output to multiple formats (.cursor/rules/, CLAUDE.md, AGENTS.md) from a single source.

**"What's the CRDT implementation?"**
> We use Yjs on the frontend (via y-codemirror.next for the editor binding) and pycrdt on the backend and CLI. The WebSocket server uses pycrdt-websocket with a custom MongoDB store. The CLI syncs using the same pycrdt binary updates over HTTP, so edits from the web and CLI merge with zero conflicts.

**"Isn't this just Google Docs for markdown?"**
> The collaborative editing is one component, but the core value is the CLI sync. Google Docs can't write to your `.cursor/rules/` directory automatically. The editing is the input; the agent context sync is the output.

**"How does this handle authentication/security?"**
> Google OAuth, SAML 2.0, OIDC for enterprise SSO, and API keys for programmatic access. Conventions are scoped to teams with fine-grained permissions (view/edit per document and folder). Credentials stored in OS keychain via the keyring library.

---

## Twitter/X Launch Thread

### Thread (post on Product Hunt launch day)

**Tweet 1:**
> Your team's AI agents are learning the same lessons from scratch. Every day.
>
> Developer A teaches Cursor your conventions. Developer B's Claude has no idea. New hire's Copilot makes every solved mistake again.
>
> I built something to fix this. 🧵

**Tweet 2:**
> The problem: AI agent context (CLAUDE.md, .cursor/rules/, AGENTS.md) is inherently local. But coding conventions are inherently team-level.
>
> Someone updates conventions. Within a day, every dev has a different version. Within a week, agents are making the same mistakes across the team.

**Tweet 3:**
> CollabMark makes AI agent context a shared, living document.
>
> 1. Write conventions on the web (real-time collab, version history)
> 2. pip install collabmark && collabmark start
> 3. CLI syncs to .cursor/rules/, CLAUDE.md, AGENTS.md automatically
>
> When anyone updates a rule, every agent knows in seconds.

**Tweet 4:**
> The CLI runs as a background daemon. Zero friction after setup.
>
> Developer A adds "Use Pydantic v2 validators" to team standards.
>
> Developer B's Cursor, Developer C's Claude, and the new hire's Copilot all know about it within seconds. No one copy-pasted a file.

**Tweet 5:**
> It's completely open source (MIT) and free.
>
> - GitHub: github.com/KRHero03/collabmark
> - PyPI: pip install collabmark
> - Live: [link]
>
> If your team uses AI agents daily and you've felt this pain, give it a try. Setup takes 60 seconds.
>
> Feedback welcome — especially from teams of 3-15 devs.

---

## IndieHackers Post

**Title**: "Building an open-source tool that syncs AI agent context across teams"

**Post**: Use a "build in public" format. Share:
- The origin story (team frustration with re-teaching agents)
- Technical decisions (why CRDTs, why CLI-first)
- Current traction (GitHub stars, CLI installs, active users)
- What's next (MCP server, agent decision log, drift detection)
- Honest challenges (zero budget, competing with VC-funded tools)

---

## Success Metrics for Launch Week

| Metric | Target |
|--------|--------|
| Product Hunt upvotes | 50+ |
| HN points | 20+ |
| GitHub stars gained | 30+ |
| CLI installs (pip) | 50+ |
| New user signups | 20+ |
| Twitter impressions | 5,000+ |
| Dev.to article views | 500+ |
