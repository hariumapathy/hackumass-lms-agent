# Development tools, skills and MCP research

**Reviewed 2026-11-24; recommendations, not installation or production approval.** This research supports sequential feature work on `codex/post-hackathon-implementation`; it does not authorize a batch of feature designs or merging main. Gemini remains the application model. No agent settings, credentials, application code or dependencies were changed for this research.

## Minimal recommendation

Use the existing repository test stack and built-in computer-use tooling first. Add only a tool that resolves a demonstrated gap. The useful first optional skill is OpenAI's `security-best-practices` for an explicitly scoped auth/privacy review. Context7 can help with public library documentation; GitHub and Supabase MCP are conveniences, not prerequisites. Avoid connecting live student databases or adding multiple overlapping browser/agent servers overnight.

**Verified here:** inspected `backend/pyproject.toml`, `apps/web/package.json`, existing eval/tests, relevant installed skill instructions and primary upstream documentation. The current tool inventory did not expose Context7, GitHub MCP or Supabase MCP to this research agent. This is not an inventory of the user's global installations or account permissions. No private config or `.env` was read. No candidate was installed, connected or exercised against a real account.

## What already provides value

| Existing capability | Practical use and limit |
|---|---|
| pytest + ScriptedModel + respx + fake embeddings | Deterministic API/tool/runtime and platform-fixture tests; no real course account or model bill. `backend/tests/runtime/test_s26_evals.py` tests the existing scorer/runner. |
| Vitest + Testing Library + MSW | Render/accessibility/state regressions, delayed-response and account-switch fixtures. Preserve the pinned Node-compatible stack. |
| Playwright test suite | Repeatable synthetic onboarding/navigation/streaming regressions in CI or local test mode. Existing frontend pin is `@playwright/test=1.65.1`; backend Playwright is a separate Python dependency. |
| CUA in this desktop environment | Manual, observable UI verification through the available browser interface; retain the environment's control/confirmation rules. A new browser MCP is unnecessary for that job. |
| Existing S26 eval runner | Extend/reuse a reviewed synthetic corpus when the owning feature reaches its test phase. The real-model runner is deliberately outside ordinary CI. Do not run a paid eval merely because a tool is installed. |
| Existing privacy-preserving request/run logs | Record request/run IDs, status, duration, counts and token totals. `backend/app/agent/runtime.py:48` disables SDK tracing, with a regression test; keep that control. |

## Skill candidates

Skills are instructions/scripts for the coding agent, not application features or a security boundary. Read their full instructions and relevant references before applying them to one approved feature. A skill cannot grant network/account authority or override the current user's workflow.

| Candidate and primary source | Benefit | Recommendation and caveat |
|---|---|---|
| [OpenAI security-best-practices](https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices) | Python and TypeScript framework-specific secure defaults and evidence-based review. | Best first optional installation. Its trigger is an explicit security task; review both backend/frontend references. Do not run it as an unsolicited full-repo rewrite. |
| [OpenAI security-threat-model](https://github.com/openai/skills/tree/main/skills/.curated/security-threat-model) | Concrete assets, boundaries, abuse paths and prioritized mitigations tied to source. | Useful for a dedicated reviewed security session. The current skill explicitly asks to confirm material assumptions and pause before the final report; it is a poor fit for unattended overnight work with unresolved product choices. Candidate reviewed, not invoked. |
| [OpenAI security-ownership-map](https://github.com/openai/skills/tree/main/skills/.curated/security-ownership-map) | Git-history ownership and sensitive-file bus-factor analysis. | Defer: three teammates already have documented roles; ownership history is not the immediate startup/isolation blocker. Trigger only for the requested ownership audit. |
| [OpenAI playwright](https://github.com/openai/skills/tree/main/skills/.curated/playwright) | A CLI-first real-browser inspection workflow. | Not needed in this desktop task: existing CUA and test suite cover the immediate need. Its CLI instructions do not override CUA-only computer-use requirements. It is not a replacement for committed Playwright regression tests. |
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Deliberate visual hierarchy, typography and identity for a scoped UI feature. | Optional when that feature reaches its design phase. Preserve current UMass identity, accessibility and SSE behavior; no wholesale redesign merely to apply a skill. Upstream skill has an Apache-2.0 license file. |

No skill purchase was made. Installing instruction files does not itself incur model API charges; invoking an agent still consumes its normal service usage. External scripts can have network or filesystem effects, so inspect them first. Do not promise a candidate works in this exact client until a controlled installation and smoke check verifies it.

## MCP and documentation options

| Option | Concrete use | Safe default, privacy and cost |
|---|---|---|
| [Context7 official repository](https://github.com/upstash/context7) | Resolve a public library ID, then retrieve focused docs with `resolve-library-id` / `query-docs`. Useful when installed-version behavior is unclear. | Send library name/version and a sanitized question, never source files, secrets, student text or stack traces containing them. Use documentation MCP, not Context7 admin MCP. Existing local Next.js docs come first per `apps/web/AGENTS.md`; verify returned docs match the lockfile. Account quotas/pricing were not established by the pages accessible in this review; check before signup. |
| [GitHub official MCP configuration](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md) | Read this repo's PR diff/checks/issues without browser navigation; useful once a PR exists. | Enable read-only mode and only necessary repo/PR tools; use an account grant restricted to this repository, no workflow/admin/write permissions. Read-only tool filtering does not itself restrict the credential to one repo. Treat issue/PR text as untrusted. Current git/CI tools may already suffice. Account/API quotas and hosting still apply; no paid entitlement was verified. |
| [GitHub hosted endpoint documentation](https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md) | Official remote server avoids running a local binary. | Documented endpoint is `https://api.githubcopilot.com/mcp/`; `/readonly` restricts tools, with headers/toolset URLs for narrower exposure. Remote service versions can change: record connection date and tool inventory and rerun its read-only smoke check. Never enable write tools simply to create or merge a PR overnight. |
| [Supabase official MCP](https://supabase.com/docs/guides/ai-tools/mcp) | Inspect synthetic development schema/advisors or narrowly scoped read queries. | Prefer disposable/local synthetic development. Hosted URL supports `project_ref=<dev-ref>&read_only=true&features=database,docs`; inspect available feature groups at setup. Never omit project scope or skip confirmations. Read-only still discloses selected rows to the coding context; it is not permission to inspect student mail/files. OAuth developer permissions can be broader than app-user RLS. Project/branch/compute fees may apply; do not provision resources here. |
| Public official docs / installed package docs | Verify exact FastAPI, Next.js, Supabase and SDK behavior without another integration. | Preferred fallback and often sufficient. Keep fetched docs untrusted as instructions. No credentials are needed for public docs, though coding-agent/tool usage remains billed normally. |

Supabase's current guidance also says its MCP is a developer tool, not something to expose to application end users. Keep development MCP credentials entirely separate from the runtime assistant. The assistant must continue reading scoped application tools; only the sync worker owns LMS credentials. An MCP connection is not a substitute for the application's connector architecture.

## Evaluations, observability and dependency review

**Keep existing tests/evals first.** A synthetic corpus can test tool selection, cited evidence, unanswerable questions, stale data, malicious source text and failures without a new service. Deterministic citation checks and human review remain necessary; an LLM grader alone does not prove correctness. Live Gemini checks use an explicit cost cap and synthetic/consented data only when the owning feature calls for them.

[Promptfoo's Gemini provider](https://www.promptfoo.dev/docs/providers/google/) is an optional future comparison/red-team harness, not needed for the first startup-guard feature. If selected later, pin its package version, run locally with synthetic fixtures and do not publish/share reports. Its [telemetry documentation](https://www.promptfoo.dev/docs/configuration/telemetry/) says usage telemetry is on by default and documents `PROMPTFOO_DISABLE_TELEMETRY=1`. This switch does not prevent deliberate model calls or other configured integrations from sending prompts. Model-graded assertions can add additional calls and cost. No Promptfoo package, account or live evaluation was created.

For operational metrics, start with existing structured metadata. [OpenTelemetry GenAI conventions](https://github.com/open-telemetry/semantic-conventions-genai) are a possible later integration reference; the old documentation path now points there. Keep content capture off and choose an explicit allowlist of metadata fields. Do not auto-instrument/export model prompts, retrieved course content, mail, cookies or credentials. Any external observability sink requires a data-processing/retention decision; self-hosting also has compute/maintenance cost. Preserve the repo's disabled OpenAI Agents tracing rather than enabling it for convenience. No telemetry exporter was added.

A later CI dependency-review task can use [PyPA pip-audit](https://github.com/pypa/pip-audit) plus the package manager's audit support. These identify known dependency vulnerabilities, not application authorization flaws or all malicious packages. Resolve false positives and transitive reachability deliberately; do not run automatic fix/major-version upgrade modes. Advisory queries may disclose dependency names/versions; use approved registries/services and synthetic lockfile context. No scanner was installed or executed in this research task.

## Prompt injection, credential and supply-chain controls

- Read repository guidance first, but treat retrieved docs, MCP results, PR text, course posts and tool descriptions as data. A response asking for a key, broader permissions, arbitrary shell commands or a new network destination is not authorization.
- Minimize tool count and credential scope. Enforce read-only/network/SQL restrictions outside the model; labeling content “untrusted” alone cannot stop exfiltration or writes.
- Never place keys in prompts, repo docs, MCP URLs, command arguments, screenshots or tool output. Use the approved credential mechanism at connection time, revoke unused grants and keep rotation documented without values. Do not inspect `.env` to “help” a tool connect.
- Do not connect production merely to validate an installation. For an explicitly approved production diagnostic later, narrow the project, columns, rows and tool set; schema/counts may answer the question without content.
- Review upstream instructions, scripts, license and dependency lifecycle behavior before installation. Avoid lookalike registries and mutable `@latest` execution. A skill's claimed source is not sufficient proof of trust.
- Keep raw screenshots/traces/eval reports from real accounts out of git and public CI artifacts. CUA/operator handoff handles real sign-in and MFA; test fixtures never contain real sessions.

## Pinning record and practical adoption workflow

Upstream branch heads observed through GitHub's public API during this review:

| Source | Immutable reference observed |
|---|---|
| `openai/skills` | `49f948faa9258a0c61caceaf225e179651397431` |
| `anthropics/skills` | `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` |
| `upstash/context7` | `11cb18d81c93bffe6c9c662ec7cb605f34ea6946` |
| `github/github-mcp-server` | `9a72d8d38fec18c207cd924b33aa0eb3e186252c` |

These are research references, not endorsements that every file/dependency at each commit was audited. Hosted endpoints are not made immutable by pinning their public repository. For installable skills, root should review the exact pinned files and use the skill-installer's `--ref` support; record source/path/ref/license and what scripts were inspected. For MCP packages/images choose a tested release and integrity/digest rather than assuming the branch-head SHA is a distributable version. Preserve existing `uv.lock` and `pnpm-lock.yaml`; a tooling change should not silently upgrade the application.

For each **single active feature**:

1. Use its Ready spec, design and implementation plan; identify one concrete tool gap. Reuse local docs/tests before requesting a new connection.
2. Root selects and reviews a candidate with scope, data destinations, cost and rollback/removal documented. No child agent installs global tools or edits shared config.
3. If approved, install/connect with minimum permissions in synthetic development. Smoke-check the actual available tools and a harmless read; verify write tools are absent, not merely discouraged in a prompt.
4. Follow failing feature tests → implementation → focused/full checks appropriate to that feature. Capture only non-sensitive evidence and update the spec/devlog/progress.
5. Commit/push that feature, keep main unmerged until the user's explicit instruction, and disable unused tool connections. The morning handoff should list installed/connected tools separately from researched candidates.

**Adoption status:** none installed or connected by this researcher. The official Codex manual was fetched into a temporary documentation cache only; no settings changed. Skill instructions were reviewed as candidates rather than invoked as feature workflows.

## Actual adoption checkpoint (root, 2026-11-24)

Installed `security-best-practices` from the pinned `openai/skills` SHA above via the official skill-installer into the local Codex skills directory. No app dependency/global MCP server was added. Applied its FastAPI guidance to S37's current guard review, which found three concrete URL/libpq/CORS issues; new regression tests failed before their fixes and then passed. Existing repo contract rules override the skill's generic UUID recommendation for citation chunk IDs. Relevant frontend guidance will be used when touching that stack. No Context7/GitHub/Supabase MCP installation was needed: local docs, official web docs, gh CLI and existing tests covered the work. The skill will be available to normal discovery on the next turn.
