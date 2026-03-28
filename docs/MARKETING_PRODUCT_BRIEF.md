# ResolveMeQ — Product & Marketing Brief

**Purpose:** Single source of truth for marketing, sales, and partner conversations.  
**Audience:** Internal teams (not a public webpage).  
**Last updated:** March 2026 — align claims with live product before external use.

---

## 1. Product identity

| Item | Detail |
|------|--------|
| **Product name** | **Resolve Me, Quickly** (brand: **ResolveMeQ**) |
| **One-line pitch** | An **AI-powered IT helpdesk** that analyzes tickets, suggests step-by-step fixes, escalates when needed, and learns from your knowledge base — so employees get faster answers and IT teams spend less time on repeat work. |
| **Version** | Platform documented as **2.0** in engineering materials |
| **Positioning** | Autonomous **decision support** for IT support: confidence-scored recommendations, structured actions (resolve / clarify / escalate), not a black-box chatbot only |

**Authors / origin (internal):** Nyuydine Bill.

---

## 2. Problem we solve

- A large share of helpdesk tickets (**roughly 30–50%** in industry framing used internally) are **repetitive and low-value** (passwords, VPN, installs, basic connectivity).
- That load **consumes Tier-1 time** and **delays** harder incidents.
- Employees expect **24/7**, **consistent** first responses; static FAQs and generic portals often fail.

**ResolveMeQ’s promise:** automate the **safe, high-confidence** slice, **route** the rest with context, and **surface** organizational knowledge (KB) so answers stay relevant.

---

## 3. What the product is (solution)

ResolveMeQ is a **multi-component platform**:

1. **Web application (React)** — Dashboard, tickets, teams, analytics, billing/subscription UI, and **AI chat** on tickets (guided steps, confidence, quick replies, suggested actions).
2. **Backend API (Django)** — Tickets, users, workflows, knowledge base, **Celery** async jobs, integration with the AI agent, audit/logging.
3. **AI Agent service (FastAPI)** — Receives ticket payloads from Django, runs **LLM-based analysis** (OpenAI/Azure OpenAI configurable), optional **RAG** over the **KB + vector search**, returns structured **analysis + solution + reasoning + UI hints** (quick replies, suggested actions, KB citations).
4. **Marketing / public site** — Separate flows; public API for **newsletter** and **demo/contact** (`api.resolvemeq.net` in docs).

**Important nuance:** “Autonomous” in internal docs means **automation of decisions and workflows** (routing, suggested actions, follow-ups), **not** that every ticket is closed without humans. Human review and escalation remain part of the design for low confidence or sensitive cases.

---

## 4. Core capabilities (sellable features)

Use these as **feature bullets**; verify wording against the **current** demo before publishing.

### For employees / end users

- **Natural-language ticket help** with **step-by-step** guidance written in plain language.
- **Confidence** surfaced so users know how strongly the AI backs a suggestion.
- **Conversation continuity** — follow-ups (“that didn’t work”, “explain step 2”) without restarting from zero.
- **Quick replies & suggested actions** — e.g. mark resolved, get human help, send a templated follow-up (exact labels depend on the AI response).
- **Feedback** (helpful / not helpful) to improve follow-up behavior.

### For IT / operations

- **Ticket analysis** — category, severity, complexity, estimated time, skills, tags.
- **Recommended next action** — `auto_resolve` | `escalate` | `request_clarification` (engineering terms; marketing may soften to “fix now / get help / we need a bit more info”).
- **Knowledge base integration** — Retrieval **(RAG)** so answers can reference **internal articles**; **citations** (KB IDs) for traceability (“sources”).
- **Reranking** (retrieval + semantic fusion) to improve relevance of KB matches.
- **Caching** (Redis) on agent side for repeated similar requests — **faster** repeat analyses.
- **Auto-learning hooks** (e.g. learning from resolved tickets) — documented in agent materials; **position** as “continuous improvement” only if product confirms it’s enabled for a customer.

### For the business

- **Subscription / billing** UI (plans, usage) — present in the web app; **pricing and limits** must come from **commercial** team, not this doc.
- **Agent usage quotas** — operational lever for **Starter / Pro / Enterprise**-style packaging (engineering concept exists).

### Trust & safety (internal assessment)

- **Escalation** for security, critical, or unclear situations (per platform assessment docs).
- **Audit / conversation** concepts in backend — useful for **enterprise** stories (confirm current deployment).

---

## 5. Who it’s for (ICP sketch)

| Segment | Fit |
|---------|-----|
| **Mid-size or growing orgs** with internal IT or MSP-style support | High — repeat tickets + KB value |
| **IT teams** drowning in Tier-1 noise | Core story |
| **MSPs / outsourced helpdesks** (if you sell multi-tenant) | Validate multi-tenant story with product |
| **Highly regulated** (healthcare, finance) | Extra diligence: data residency, logging, human-in-the-loop — **not** all claims in this doc |

---

## 6. Architecture (one diagram for decks)

High-level:

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Web / Users │ ──▶ │  Django (API)   │ ──▶ │  FastAPI Agent   │
│  (React app) │     │  Tickets, KB,   │     │  LLM + RAG +     │
└──────────────┘     │  Celery, DB     │     │  embeddings      │
                     └────────┬────────┘     └────────┬─────────┘
                              │                      │
                              ▼                      ▼
                     ┌─────────────────┐     ┌──────────────────┐
                     │ PostgreSQL +    │     │ Knowledge +      │
                     │ Redis (queues)  │     │ vector search    │
                     └─────────────────┘     └──────────────────┘
```

**Integrations** (roadmap vs reality): Internal README mentions **Slack/Teams** and tools like **Okta, AD, Jira/ServiceNow** — treat as **vision/partner roadmap** unless sales confirms **live** connectors for a deal.

---

## 7. Technology & credibility (for technical buyers)

| Layer | Stack (from repos) |
|-------|---------------------|
| Frontend | React, Vite, Tailwind, Framer Motion |
| API | Django REST, Celery, Redis |
| AI service | FastAPI, OpenAI-compatible API (Azure OpenAI supported in env templates) |
| Data | PostgreSQL; vector / KB search in agent; Redis caching |
| Deploy | Docker / VPS-style docs; **GHCR** images referenced in CI workflows |

**Domains mentioned in docs (verify before print):** `resolvemeq.net`, `api.resolvemeq.net`, `agent.resolvemeq.com` — use **only** what legal and ops approve for public materials.

---

## 8. Differentiators (messaging angles)

1. **Structured IT outcomes** — Not only free text: **steps, time estimate, success probability, reasoning** — fits ITIL-style workflows.
2. **KB-grounded answers (RAG)** — Answers can **cite** internal articles, reducing “generic ChatGPT” risk.
3. **Confidence + actions** — Users and IT see **when** to trust vs **escalate**.
4. **Full product** — Web UX + backend + **dedicated agent service** — not a single monolith script.

---

## 9. Public marketing touchpoints (engineering)

- **Newsletter:** `POST /api/subscribe`  
- **Demo / contact:** documented under marketing API (`ResolveMeQ/docs/MARKETING_API.md`, `resolvemeqWeb/docs/MARKETING_API.md`)

Marketing should use **exact** URLs and copy from the live marketing site once deployed.

---

## 10. What marketing must verify externally

- **Pricing, SLAs, compliance** (SOC2, GDPR, HIPAA) — **not** specified in engineering docs.
- **Live feature list** vs roadmap (Slack, Teams, Jira, etc.).
- **“% automation”** — internal materials cite **30–50%** target automation; use as **directional** unless you have **customer-specific** metrics.
- **Platform assessment** — Internal doc lists **recommended improvements** before “full trust”; **do not** claim “complete audit” without product sign-off.

---

## 11. Glossary (for consistent copy)

| Term | Plain language |
|------|----------------|
| **RAG** | Retrieval-augmented generation — AI answers use **your** KB articles, not only generic training data. |
| **Confidence** | Model-estimated **0–1** score for the suggested answer; low scores pair with clarify or escalate. |
| **Recommended action** | Suggested workflow: try self-resolution, ask user for details, or escalate to a human. |
| **Quick replies** | Short chips that send a **next user message** to continue the thread. |
| **Suggested actions** | Buttons that trigger **intents** (e.g. mark resolved, escalate). |

---

## 12. Document maintenance

- **Owner:** Product + engineering (update when major features ship).  
- **Marketing:** Request a **short delta** after each release if positioning changes.

---

*This brief is derived from repository READMEs, `README.md` (ResolveMeQ), `resolvemeq-agent/README.md`, `resolvemeqwebapp/README.md`, `docs/MARKETING_API.md`, `docs/PLATFORM_ASSESSMENT.md`, and agent enhancement docs. It is not a legal or financial commitment.*
