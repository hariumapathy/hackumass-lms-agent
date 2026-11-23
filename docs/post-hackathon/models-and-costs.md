# Model strategy and operating costs

Draft recommendation for team review, researched 2026-11-23. Prices are USD, subject to change, and must be rechecked before purchasing. No subscriptions, paid experiments, provider migrations or account changes are authorized by this document.

## Recommendation

Keep one production chat provider for the first pilot, plus a separately pinned embedding configuration. Benchmark a paid Gemini Flash-Lite candidate against an inexpensive OpenAI candidate and DeepSeek on synthetic course fixtures before choosing. Retaining the existing Gemini adapter minimizes migration work; that is an engineering convenience, not evidence it is the cheapest or best answerer. Do not automatically route private student data to a new provider when the primary is unavailable.

OpenRouter is a reasonable alternative when one chat invoice and several models are a firm requirement. It adds another data processor and routing policy to manage; it is not itself a cheaper model. Restrict routing to named, approved providers/regions, require no-training settings and applicable retention controls, disable prompt logging, and fail closed if no approved route is available. Its [FAQ](https://openrouter.ai/docs/faq) currently lists a 5.5% credit-purchase fee with a $0.80 minimum. [Provider logging policies](https://openrouter.ai/docs/guides/privacy/provider-logging), [data collection exceptions](https://openrouter.ai/docs/guides/privacy/data-collection) and [ZDR routing](https://openrouter.ai/docs/guides/features/zdr) require review; “OpenAI-compatible” and “ZDR eligible” are not blanket institutional approval.

Chinese-developed models are eligible evaluation candidates. Evaluate the actual serving company, hosting region, retention/training terms, reliability and contract alongside answer quality; model origin alone does not determine those properties. DeepSeek direct and a DeepSeek/Qwen model hosted by a different company are different deployment choices. No private course/mail data goes to an unreviewed endpoint. Qwen is a later candidate; no unverified SKU/price is included here.

## Current implementation

`backend/app/agent/runtime.py:68–85` chooses only Gemini or OpenAI clients using global configured model names. It does not implement OpenRouter, DeepSeek, arbitrary models or a functioning Anthropic adapter. `agent_available` checks only the Gemini key. Model picker labels must not be mistaken for independent working adapters. `gemini.py` contains a streaming tool-call compatibility patch; each new provider needs equivalent contract tests, not merely a changed base URL.

The runtime counts tokens, but `DbChatStore.finish_run` does not persist them to the database. We cannot reliably attribute monthly spend to students today. `core/embeddings.py` supports Gemini and fake vectors; the advertised OpenAI embedding option currently raises a configuration error. Keep chat-provider selection separate from any embedding migration; equal vector dimensions do not make different embedding spaces compatible.

## Price snapshot and illustrative inference cost

Standard online text pricing, per million uncached input/output tokens. No caching, discounts or free-tier credits assumed.

| Candidate | Input | Output | Cost per example answer | Status |
|---|---:|---:|---:|---|
| Gemini 3.5 Flash-Lite | $0.30 | $2.50 | $0.0086 | Proposed cheaper Gemini candidate; not evaluated in this repo |
| GPT-6 Luna | $0.10 | $0.50 | $0.0022 | Proposed inexpensive challenger; adapter capability check required |
| DeepSeek Flash (current V4.1 Flash alias), peak | $0.30 | $1.20 | $0.0060 | Proposed challenger; privacy/hosting review and adapter tests required |
| Same DeepSeek, off-peak | $0.15 | $0.60 | $0.0030 | Sensitivity only; never rely on off-peak pricing for interactive budgets |

Sources: [Google pricing](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite), [OpenAI Luna model pricing](https://developers.openai.com/api/docs/models/gpt-6-luna), [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/). Use Luna's explicit standard model-page rates; discounted pricing tables are not standard rates. Its documentation also says Chat Completions function calling requires reasoning effort `none`; Responses is the alternative. Neither integration has been tested here. Output figures include any billable reasoning tokens, not just displayed words.

Example answer = **12,000 aggregate input tokens + 2,000 aggregate output tokens across every model/tool turn in the run**. This is a planning assumption, not a measurement. At 40 answers/student/month:

| Active students | Luna | Gemini Flash-Lite | DeepSeek peak |
|---:|---:|---:|---:|
| 25 | $2.20 | $8.60 | $6.00 |
| 100 | $8.80 | $34.40 | $24.00 |
| 1,000 | $88.00 | $344.00 | $240.00 |

Formula: students × answers × ((input tokens × input rate + output tokens × output rate) / 1,000,000). A heavy student at 200 answers/month and five times the tokens per answer costs **25 times** the base scenario. Add retries, fallback runs, study-set output and provider fees separately. These scenarios do not prove the models deliver equivalent results.

Google lists the existing `gemini-embedding-001` at $0.15/million standard input tokens. One million initial embedding tokens per student would add $3.75/$15/$150 for 25/100/1,000 students, before repeated changes/query embeddings. Estimate actual semester sizes first. Google distinguishes free-tier product-improvement use from paid-tier handling; use reviewed paid-service terms for private pilot data, not hackathon free-tier assumptions. [Pricing and data-use table](https://aistudio.google.com/docs/pricing#gemini-embedding).

## Whole-service budget

Token prices are only part of the bill. Illustrative monthly **allowances**, not vendor quotes or capacity claims:

| Component | 25-student pilot allowance | Notes |
|---|---:|---|
| Managed Supabase | $25+ | [Pro starts at $25](https://supabase.com/pricing); verify storage/egress/backup needs |
| Always-on API + worker | $20–50 | Measure both services. [Railway Pro](https://railway.com/pricing) has $20 minimum usage including credits, not a $20 unlimited fixed bill |
| Frontend | $0–20+ | Verify current eligibility/team/usage; could use same container host instead of a separate frontend vendor |
| Domain, mail, monitoring/object recovery | $5–15+ | Estimates; operational responsibilities still need owners |
| Hosted login browsers, if enabled | Additional $10–50+ reserve | Unmeasured; may exceed this with concurrent logins/retention; vendor quote/spike required |
| Models and embeddings | Tables above | Include query embedding and initial imports, not just chat |

A $50/month total target is tight even before hosted login or mail-verification work. Plan roughly $60–110 for a small Canvas-first pilot, with contingency and explicit caps; no fixed all-platform price is established. At larger scales, remeasure files, queue/database load and egress instead of extrapolating only tokens. Gmail verification/security assessment can add external costs not estimated here. Server cost often matters more than saving a fraction of a cent per answer at 25 users.

Price and throughput limits are separate: benchmark sustained/concurrent requests, timeout/429 handling and provider account tiers. A lower token rate does not guarantee more usable capacity. DeepSeek documents [account-level concurrency limits](https://api-docs.deepseek.com/quick_start/rate_limit/); other providers also have tier-specific limits.

## Evaluation and spending gates before selection

1. Use the shared frozen 120-question retrieval corpus in [the RAG audit](audit-rag-sync.md#first-benchmark-and-release-gates), preserving its 30 syllabus/policy, 30 lecture, 20 discussion, 20 ambiguous cross-course and 20 unanswerable/adversarial cases. Add metadata tags for overlapping concerns. Maintain separate workflow contract cases for exact deterministic deadlines, quiz validity, study approvals, tool arguments, timezone ambiguity and provider outage; do not change the retrieval denominator. Never use real inbox content for exploratory provider comparison.
2. Record retrieval separately from generation: evidence recall@8, claim support, tool/schema success, wrong-user/stale-source retrieval, p50/p95 first useful text and completion, total input/output/thinking tokens and retries per complete answer.
3. Proposed release gates: zero cross-user disclosure and unauthorized writes, zero unsupported deadline assertions in the deterministic set, at least 95% supported answers on answerable questions, at least 95% correct refusal on unanswerable questions, at least 99% valid tool/structured outputs after bounded retry. Compare quality to the current Gemini baseline; no model has passed this new gate yet.
4. Use the cheapest candidate that passes. Keep one explicit quality fallback only if its own data policy is approved; do not hide a costlier model behind a cheap label. Log exact model version/provider/price version and fail visibly on unsupported configuration.
5. Add durable usage/reservation ledger, per-user daily/semester budgets, organization monthly cap, bounded input/output/turn/retry limits, shared concurrency and outage circuit breakers. Reserve worst-case cost before admitting work; settle actual usage afterward. Unknown usage retains a conservative charge until reconciliation. Canceled requests may still incur provider charges.
6. Alerts at proposed 50/80/100% spend, hard application admission stop at cap; provider billing alerts alone are not guaranteed hard stops. Keep deterministic Today/deadlines usable when AI allocation is exhausted. No billing plan is selected until scale, budget and provider data terms are approved.
