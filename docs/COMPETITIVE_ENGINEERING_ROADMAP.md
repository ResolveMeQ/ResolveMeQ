# ResolveMeQ Competitive Engineering Roadmap

**Purpose:** Single reference for product, engineering, and sales until all phases are achieved.  
**Owner:** Product + Engineering (joint).  
**Created:** July 2026  
**Status:** Living document — update phase status and acceptance checks each release.

---

## How to use this document

1. **Pick work from the current phase only** unless a P0 production bug forces an exception.
2. **Do not mark a feature “complete”** until it passes the [Competitive Complete bar](#competitive-complete-bar) for that feature.
3. **Update the [Phase tracker](#phase-tracker)** at the end of each sprint or release.
4. **Verify marketing claims** against this doc before external use (`docs/MARKETING_PRODUCT_BRIEF.md` must stay aligned).

---

## North-star thesis

> **ResolveMeQ = AI resolves repeat IT tickets; workflows run multi-step IT processes; rules connect your stack.**

We win **mid-market IT teams and MSPs** by being faster to deploy and sharper on AI + IT ops playbooks than ServiceNow, and more IT-native than Zendesk/Intercom — not by pretending to be a full ITSM platform in year one.

### Three engines (build in order)

| Engine | What it does | Primary competitors |
|--------|----------------|---------------------|
| **AI Engine** | Analyze, chat, RAG, confidence, remediation scripts, autonomous actions | Moveworks, Aisera, Zendesk AI |
| **Operations Engine** | Workflows, rules, connectors, SLAs | Atomicwork, Freshservice, ServiceNow |
| **Proof Engine** | Deflection metrics, MTTR, audit, calibration | Required to *sell* the first two |

---

## Competitive Complete bar

**A feature is not complete when it ships.**  
It is complete only when a reasonable buyer would **prefer ResolveMeQ over a named competitor** for that capability in a demo or pilot.

### Definition of “Competitive Complete”

For every feature below, **all** of the following must be true:

| # | Criterion | Question to answer “yes” |
|---|-----------|---------------------------|
| 1 | **End-to-end** | Works in production path: create → use → outcome visible (not API-only or seed-data-only). |
| 2 | **Reliable** | No known P0/P1 bugs; happy path succeeds ≥99% in staging soak. |
| 3 | **Observable** | Metrics, logs, or admin visibility exist so support can debug failures. |
| 4 | **Documented** | Internal runbook + customer-facing help or release note (if user-facing). |
| 5 | **Differentiated** | Beats or matches competitor on at least **one** measurable axis (see per-feature table). |
| 6 | **Demo-ready** | Sales can show it in ≤5 minutes without “ignore that bug” or “coming soon.” |
| 7 | **Signed off** | Product owner explicitly marks ✅ in [Phase tracker](#phase-tracker). |

### What does *not* count as complete

- Merged PR with no UI or no notification path
- Backend only while competitor shows full UX
- Works for platform team only, not for a customer team admin
- “We have the code” but docs/marketing still say “planned”
- Feature exists but no metric proves it (for automation/deflection claims)

### Competitive comparison shorthand

When evaluating differentiation, compare against **primary** peer for that feature:

| Feature area | Primary peer | “Win” means |
|--------------|--------------|-------------|
| AI ticket resolution | Moveworks / Zendesk AI | Faster *correct* first answer with KB citations + scripts |
| Multi-turn chat | Intercom / Copilot | Context retained; escalation doesn’t reset thread |
| Workflows / playbooks | Atomicwork / Freshservice | Clear owners, SLAs, notifications; completes real onboarding |
| Rules / automation | Freshservice / Jira Automation | IT-specific triggers; less config than Zapier |
| Slack / Teams intake | Moveworks | Create ticket, status, notify — in channel they already use |
| Integrations (Okta, Jira) | ServiceNow / Okta Workflows | Read/write enough to automate *one* real provisioning check |
| Analytics / ROI | All enterprise AI vendors | Customer sees deflection % in-product, not a spreadsheet |

---

## Current baseline (July 2026)

Honest inventory — **built**, **partial**, **missing**:

| Capability | Status | Notes |
|------------|--------|-------|
| AI ticket analysis + RAG | Built | Safety gate, rollback, citations |
| Multi-turn ticket chat | Built | UX gap: chat before analysis finishes |
| Autonomous agent actions | Partial | Engine exists; most paths still human-in-loop |
| Escalation queue + SLA display | Built | Platform agents, claim, priority |
| Workflows v1 | Built | Sequential; templates; Slack/Teams notify; step due dates |
| Workflow template admin UI | Built | Team owner CRUD at `/workflows/templates` |
| Rules / trigger engine | Missing | `automation/` app is stub |
| Slack integration | Built | OAuth, slash, modals, DMs |
| Microsoft Teams | Partial | Backend + tests; Settings UI hidden |
| Okta / AD / Jira / ServiceNow | Missing | Roadmap only |
| Automation / deflection metrics | Missing | Cannot prove “30–50%” in product |
| Compliance audit log | Partial | TicketInteraction; not enterprise-grade |
| Blog / marketing SEO | Built | Dynamic sitemap, daily AI posts |

**Positioning today:** AI-first IT helpdesk with checklist workflows — not yet enterprise orchestration.

---

## Phase 0 — Foundation (weeks 1–4)

**Goal:** Make what exists **sellable and measurable**. No new engine yet.

### Deliverables

| ID | Feature | Competitive Complete = win vs | Engineering scope | Acceptance (Competitive Complete) |
|----|---------|------------------------------|-------------------|-----------------------------------|
| P0-1 | **Workflow step visibility** | Freshservice task lists | Due dates on steps; overdue badge; filter on `/workflows` | Buyer sees “what’s stuck” without asking IT |
| P0-2 | **Workflow Slack notifications** | Atomicwork step alerts | When step → `active`, DM assignee/team via `integrations/notify.py` | Assignee gets Slack ping within 60s; link opens workflow |
| P0-3 | **Microsoft Teams UI** | Moveworks channel parity | Expose Teams in Settings; link flow; test notify path | Teams user connects bot and receives escalation DM |
| P0-4 | **Automation metrics v1** | Any AI vendor ROI slide | Dashboard: AI-first resolved, escalated, reopened, workflow completed | Customer admin sees deflection % without export |
| P0-5 | **Chat UX: analysis before empty chat** | Zendesk AI polish | Don’t render empty chat until first analysis or skeleton | No “blank chat” in demo; first message ≤30s p95 |
| P0-6 | **Documentation truth pass** | Trust / enterprise eval | Update WORKFLOWS_SCOPE, MARKETING_PRODUCT_BRIEF, this doc | Sales deck matches live product |

### Phase 0 exit criteria (all required)

- [ ] Demo: onboarding workflow start → Slack notify → step complete → metrics update
- [ ] P0-4 live on Dashboard for all paid teams
- [ ] Teams connectable by customer admin (not manual DB)
- [ ] Product sign-off on Phase tracker

---

## Phase 1 — Workflow 2.0 (months 2–3)

**Goal:** Match **Atomicwork / Freshservice** on IT ops playbooks — curated, trustworthy, SLAs.

### Deliverables

| ID | Feature | Competitive Complete = win vs | Engineering scope | Acceptance (Competitive Complete) |
|----|---------|------------------------------|-------------------|-----------------------------------|
| P1-1 | **Template admin UI** | Freshservice workflow editor (simple) | CRUD `WorkflowTemplate`; reorder steps; team/global scope | Team admin creates “Contractor offboarding” without engineer |
| P1-2 | **Step types** | ServiceNow task types (minimal) | `manual`, `approval`, `auto_check` on `WorkflowStep` | Approval step blocks next until approved |
| P1-3 | **Simple branching** | Jira Automation conditions | One branch: if ticket field → skip step range | Template handles “remote vs office” onboarding |
| P1-4 | **Team-based assignee routing** | Atomicwork role routing | FK to Team (not string label); claim respects team | Wrong team cannot claim step |
| P1-5 | **Workflow SLA** | Freshservice SLA timers | `due_at` on workflow; breach → notify + dashboard | Overdue workflow visible; alert fires |
| P1-6 | **Workflow ↔ ticket sync** | ITSM ticket linkage | On workflow complete → ticket status resolved/closed | Ticket state reflects workflow outcome |
| P1-7 | **Playbook: Employee onboarding** | Atomicwork onboarding agent | Template + KB links + 1 rule + metrics | End-to-end demo in ≤10 min; 80% completion in pilot |

### Explicitly out of scope (Phase 1)

- Visual drag-and-drop DAG builder
- Parallel steps
- LLM-generated workflow steps
- CMDB

### Phase 1 exit criteria

- [ ] Customer admin authors and runs custom template (not seed-only)
- [x] Onboarding playbook documented as sellable SKU (`docs/PLAYBOOK_EMPLOYEE_ONBOARDING.md`)
- [ ] ≥3 pilot teams complete onboarding workflow with SLA alerts

---

## Phase 2 — Rules + Connectors (months 4–6)

**Goal:** **Freshservice / partial ServiceNow** — “when X happens, do Y across systems.”

### 2a. Rules engine

Replace `automation/` stub with **Rules** subsystem.

| ID | Feature | Competitive Complete = win vs | Engineering scope | Acceptance (Competitive Complete) |
|----|---------|------------------------------|-------------------|-----------------------------------|
| P2-1 | **Rules model + executor** | Jira Automation / Freshservice | Trigger → conditions (AND) → actions; `RuleExecutionLog` | Rule fires on ticket.escalated; log auditable |
| P2-2 | **Triggers (v1)** | — | `ticket.created`, `ticket.escalated`, `ticket.resolved`, `workflow.step.completed`, `schedule.cron` | 5 triggers documented and stable |
| P2-3 | **Actions (v1)** | — | `start_workflow`, `assign_ticket`, `notify_slack`, `notify_teams`, `set_field`, `call_webhook`, `run_agent` | 8 actions; failures retried or logged |
| P2-4 | **Rules admin UI** | Zapier (simpler) | List/create/test rules; dry-run | Admin tests rule without production side effect |
| P2-5 | **Migrate category→workflow** | Internal | Existing auto-start uses rules engine | Single code path for automation |

### 2b. Connector framework

| ID | Feature | Competitive Complete = win vs | Engineering scope | Acceptance (Competitive Complete) |
|----|---------|------------------------------|-------------------|-----------------------------------|
| P2-6 | **Outbound webhooks** | All ITSM | HMAC-signed POST on ticket/workflow events | Customer receives event in Make/n8n reliably |
| P2-7 | **Okta read connector** | Okta Workflows (read slice) | OAuth; list user, group membership | Workflow step auto_check: “user exists in Okta” |
| P2-8 | **Google Workspace / M365 read** | — | User exists, license SKU (read-only) | Provisioning checklist verifies account created |
| P2-9 | **Jira bi-directional (escalate)** | JSM | Create/update issue on escalate; link on ticket | Escalated ticket has Jira key; status sync one way |

Architecture:

```
integrations/connectors/base.py    # OAuth, refresh, rate limit, circuit breaker
integrations/connectors/{okta,jira,webhook}.py
tickets/models.py                  # ExternalReference (system, external_id, ticket)
automation/models.py               # Rule, RuleExecutionLog
automation/engine.py               # evaluate + execute
```

### Phase 2 exit criteria

- [ ] Rule: “On escalate → create Jira issue + start Offboarding workflow” in staging
- [ ] Okta auto_check completes at least one onboarding step automatically
- [ ] Connector failures visible in admin (not silent)

---

## Phase 3 — AI + Workflow fusion (months 7–9)

**Goal:** Beat **generic AI helpdesks** — AI and operations are one product, not bolted on.

| ID | Feature | Competitive Complete = win vs | Engineering scope | Acceptance (Competitive Complete) |
|----|---------|------------------------------|-------------------|-----------------------------------|
| P3-1 | **AI step assistant** | Moveworks (contextual) | On active step, suggest actions from KB only — no invented steps | Suggestions cite KB; user accepts in one click |
| P3-2 | **Playbook bundles** | Atomicwork packs | Template + KB articles + resolution templates + default rule | Sales sells “Onboarding pack” as one SKU |
| P3-3 | **Connector-driven auto_complete** | ServiceNow integration hub | Step completes when Okta/M365 confirms | 2+ steps auto-complete in onboarding demo |
| P3-4 | **Cross-ticket workflows** | Enterprise ITSM | Parent workflow spawns child tickets per step | Facilities + IT steps tracked separately |
| P3-5 | **MSP mode** | ConnectWise / Datto | Per-tenant templates, connectors, usage metering | MSP admin manages 3 clients isolated |

### Phase 3 exit criteria

- [ ] Onboarding playbook auto-completes ≥2 steps via connector
- [ ] AI assistant used in ≥50% of workflow steps in pilot (telemetry)
- [ ] MSP pilot with 2+ tenants

---

## Phase 4 — Enterprise & moat (months 10–12)

**Goal:** Remove blockers for **regulated / enterprise** deals and widen moat.

| ID | Feature | Competitive Complete = win vs | Engineering scope | Acceptance (Competitive Complete) |
|----|---------|------------------------------|-------------------|-----------------------------------|
| P4-1 | **Compliance audit log** | ServiceNow audit | Immutable append-only event stream; export | Security reviewer accepts export for SOC2 prep |
| P4-2 | **Agent SLO + circuit breaker** | Enterprise AI SLAs | Breaker on agent; fallback message; metric | Agent outage doesn’t hang tickets >30s |
| P4-3 | **Predictive routing** | Moveworks routing | Heuristic + history → assignee before LLM | Reduces reassignment rate vs baseline |
| P4-4 | **Public API + partner webhooks** | Freshservice API | Documented REST for tickets, workflows, rules | Partner builds intake without custom fork |
| P4-5 | **Advanced analytics** | All | Deflection by category, confidence calibration, workflow bottlenecks | Customer optimizes playbook from data |

### Phase 4 exit criteria

- [ ] Enterprise security questionnaire answered from built features (not “planned”)
- [ ] One partner integration on public API
- [ ] Published calibration report (internal) for AI confidence vs outcomes

---

## Architecture principles (do not violate)

1. **Curated beats generative** for multi-step processes — AI matches and assists; templates are human-authored.
2. **One notification bus** — all channels via `integrations/notify.py`.
3. **Every autonomous action reversible** where feasible — extend rollback to workflow completions.
4. **Connector isolation** — no vendor SDK in views; timeouts + circuit breakers mandatory.
5. **Measure before marketing** — no external % automation claim without P0-4 (or successor) live.
6. **Single doc truth** — this file + `MARKETING_PRODUCT_BRIEF.md` updated each release.

---

## Deprioritized (do not start until Phase 4 review)

| Item | Reason |
|------|--------|
| Full CMDB | 18+ month distraction |
| Visual DAG workflow builder | Phase 1 branching sufficient for mid-market |
| LLM-authored workflows | Trust and audit risk |
| Discord, voice, mobile native app | After Teams + metrics prove channel strategy |
| White-label / full MSP rebrand | Phase 3 MSP mode first |
| Replace ServiceNow positioning | Partner/sync only until Phase 2–3 done |

---

## Success metrics (12-month targets)

| Metric | Target | Source |
|--------|--------|--------|
| Tier-1 deflection rate | 25–35% | Automation metrics (P0-4) |
| Workflow completion rate (onboarding) | ≥80% | Workflow status |
| Mean time to first AI response | p95 ≤30s | Agent + Celery timing |
| Reopen after escalate | ≤10% | Ticket analytics |
| Paid teams with Slack or Teams connected | ≥40% | Integration models |
| Rule executions / week (post Phase 2) | Growth QoQ | RuleExecutionLog |

---

## Sales-ready win lines (use only when Competitive Complete ✅)

| Win line | Required features |
|----------|-------------------|
| “AI cites your KB and gives remediation scripts — not generic ChatGPT.” | RAG + citations + scripts (built); chat UX (P0-5) |
| “Onboarding with owners, SLAs, and Slack alerts — not tickets lost in a queue.” | P0-1, P0-2, P1-5, P1-7 |
| “Rules start workflows when confidence is low — without a six-month ITSM project.” | P2-1–P2-5 |
| “See deflection rate in your dashboard.” | P0-4 |
| “Okta-aware onboarding checks account creation automatically.” | P2-7, P3-3 |

---

## Phase tracker

Update at each release. Status: `Not started` | `In progress` | `Shipped` | **Competitive Complete ✅**

### Phase 0 — Foundation

| ID | Feature | Status | Competitive Complete | Product sign-off | Release |
|----|---------|--------|----------------------|------------------|---------|
| P0-1 | Workflow step visibility | Shipped | ☐ | ☐ | Jul 2026 |
| P0-2 | Workflow Slack notifications | Shipped | ☐ | ☐ | Jul 2026 |
| P0-3 | Microsoft Teams UI | Shipped | ☐ | ☐ | Jul 2026 |
| P0-4 | Automation metrics v1 | Shipped | ☐ | ☐ | Jul 2026 |
| P0-5 | Chat UX (analysis first) | Shipped | ☐ | ☐ | Jul 2026 |
| P0-6 | Documentation truth pass | In progress | ☐ | ☐ | Jul 2026 |

### Phase 1 — Workflow 2.0

| ID | Feature | Status | Competitive Complete | Product sign-off | Release |
|----|---------|--------|----------------------|------------------|---------|
| P1-1 | Template admin UI | Shipped | ☐ | ☐ | Jul 2026 |
| P1-2 | Step types | Shipped | ☐ | ☐ | Jul 2026 |
| P1-3 | Simple branching | Shipped | ☐ | ☐ | Jul 2026 |
| P1-4 | Team assignee routing | Shipped | ☐ | ☐ | Jul 2026 |
| P1-5 | Workflow SLA | Shipped | ☐ | ☐ | Jul 2026 |
| P1-6 | Workflow ↔ ticket sync | Shipped | ☐ | ☐ | Jul 2026 |
| P1-7 | Onboarding playbook SKU | Shipped | ☐ | ☐ | Jul 2026 |

### Phase 2 — Rules + Connectors

| ID | Feature | Status | Competitive Complete | Product sign-off | Release |
|----|---------|--------|----------------------|------------------|---------|
| P2-1 | Rules engine core | Shipped | ☐ | ☐ | Jul 2026 |
| P2-2 | Triggers v1 | Shipped | ☐ | ☐ | Jul 2026 |
| P2-3 | Actions v1 | Shipped | ☐ | ☐ | Jul 2026 |
| P2-4 | Rules admin UI | Shipped | ☐ | ☐ | Jul 2026 |
| P2-5 | Migrate category→workflow | Shipped | ☐ | ☐ | Jul 2026 |
| P2-6 | Outbound webhooks | Shipped | ☐ | ☐ | Jul 2026 |
| P2-7 | Okta read | Shipped | ☐ | ☐ | Jul 2026 |
| P2-8 | Google/M365 read | Shipped | ☐ | ☐ | Jul 2026 |
| P2-9 | Jira escalate sync | Not started | ☐ | ☐ | |

### Phase 3 — AI + Workflow fusion

| ID | Feature | Status | Competitive Complete | Product sign-off | Release |
|----|---------|--------|----------------------|------------------|---------|
| P3-1 | AI step assistant | Not started | ☐ | ☐ | |
| P3-2 | Playbook bundles | Not started | ☐ | ☐ | |
| P3-3 | Connector auto_complete | Not started | ☐ | ☐ | |
| P3-4 | Cross-ticket workflows | Not started | ☐ | ☐ | |
| P3-5 | MSP mode | Not started | ☐ | ☐ | |

### Phase 4 — Enterprise & moat

| ID | Feature | Status | Competitive Complete | Product sign-off | Release |
|----|---------|--------|----------------------|------------------|---------|
| P4-1 | Compliance audit log | Not started | ☐ | ☐ | |
| P4-2 | Agent circuit breaker | Not started | ☐ | ☐ | |
| P4-3 | Predictive routing | Not started | ☐ | ☐ | |
| P4-4 | Public API | Not started | ☐ | ☐ | |
| P4-5 | Advanced analytics | Not started | ☐ | ☐ | |

---

## Release checklist (every feature PR)

Copy into PR description or release ticket:

```
[ ] End-to-end path tested (not API-only)
[ ] No open P0/P1 for this feature
[ ] Metrics/logs/admin visibility added
[ ] Docs updated (this roadmap + user-facing if needed)
[ ] Differentiation vs [named competitor] written in PR
[ ] Demo script updated (≤5 min)
[ ] Product sign-off for Competitive Complete ☐
```

---

## Related documents

| Document | Path | Keep in sync when |
|----------|------|-----------------|
| Marketing product brief | `docs/MARKETING_PRODUCT_BRIEF.md` | Any user-facing capability changes |
| Workflows scope (historical) | `docs/WORKFLOWS_SCOPE.md` | Workflow model or semantics change |
| Platform assessment | `docs/PLATFORM_ASSESSMENT.md` | Security/reliability milestones |
| Agent improvement plan | `docs/AGENT_IMPROVEMENT_PLAN.md` | AI UX changes |

---

## Revision history

| Date | Author | Change |
|------|--------|--------|
| 2026-07-08 | Engineering | Initial roadmap; Competitive Complete bar; Phases 0–4 |

---

*This document is an engineering and product planning artifact. It is not a contractual commitment to customers or investors.*
