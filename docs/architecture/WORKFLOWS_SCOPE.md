# Workflows: scoping doc (v1 shipped — Phase 1+ in COMPETITIVE_ENGINEERING_ROADMAP.md)

## Shipped reality (July 2026)

The original v1 sketch below was implemented and extended through **Phases 1–3**. Current product includes:

| v1 sketch | Shipped state |
|-----------|---------------|
| Strictly sequential steps | **Sequential + simple branching** (`skip_when` on steps, P1-3) |
| No SLA on steps | **Workflow and step SLAs** with overdue badges (P1-5) |
| No template UI | **Template admin UI** (P1-1) |
| No external execution | **Connector auto_check / auto_complete** — Okta, Google, M365 (P2-7–P3-3) |
| Ticket-only workflows | **Standalone workflows** + **cross-ticket** child workflows (P3-4) |
| AI matches category only | **Step assistant** — LLM + KB hints per active step (P3-1) |
| Seed templates only | **Playbook bundles** — employee onboarding SKU + install command (P1-7, P3-2) |

**Live surfaces:** `/workflows` list with overdue filter, ticket detail checklist, escalation queue, Slack/Teams step notifications, outcome metrics (`onboarding_playbook` stats).

**Docs:** `docs/playbooks/PLAYBOOK_EMPLOYEE_ONBOARDING.md`, `docs/architecture/COMPETITIVE_ENGINEERING_ROADMAP.md`

The sections below retain the original v1 design rationale for historical context.

---

ServiceNow's "Now Platform," Aisera's cross-department orchestration, and Atomicwork's
"AI Coworkers own job roles, not tasks" all describe the same underlying thing: a **multi-step
process spanning multiple people/systems over time** — e.g. new-employee onboarding
(provision accounts + assign a laptop + schedule training + notify facilities), each step with
its own owner and a dependency on the step before it. That's different from what ResolveMeQ
does today.

ResolveMeQ's entire data model is shaped around **one ticket = one problem = one AI response
cycle**: `Ticket` (`ResolveMeQ/tickets/models.py`), the `AgentAction` decision enum
(`AUTO_RESOLVE`, `ESCALATE`, `REQUEST_CLARIFICATION`, `ASSIGN_TO_TEAM`, `SCHEDULE_FOLLOWUP`,
`tickets/autonomous_agent.py`), and the escalation/claim system (`tickets/rollback.py`,
`EscalationQueue.jsx`) all assume a single self-contained request. There's no concept of a
checklist with dependent sub-steps and different owners living inside one request.

This doc scopes a **minimal v1** — deliberately small, not the full ServiceNow-style workflow
engine — so it's ready to pick up later without re-deriving the shape from scratch.

## Core concept (v1, deliberately narrow)

A `Workflow` is a **strictly sequential**, ordered list of `WorkflowStep`s. No branching, no
parallel steps, no DAG. Step N+1 only becomes actionable once step N is marked done. This is
the same "minimal, not maximal" instinct as the remediation-script feature: ship the narrow
version that's actually useful before reaching for the general case.

Workflows are instantiated from **fixed, admin-authored templates** — not LLM-generated on the
fly. Freely letting an LLM invent a multi-step process with real assignments and real actions
is a bigger trust problem than a single AI-suggested ticket resolution (more people involved,
more steps that can silently go wrong, harder for a user to sanity-check the whole thing at a
glance). This mirrors the same reasoning that kept `security_incident` categories off
LLM-generated remediation scripts: **curated/templated beats free-form** wherever the blast
radius spans more than one person's own device. The AI's role in v1 is just matching a
ticket to the right template, not authoring the steps.

## Data model sketch

New Django app `workflows/` (sibling to `tickets/`, not folded into it — a workflow can exist
without a ticket, and conflating the two would make `Ticket` responsible for two different
shapes of thing).

```python
class WorkflowTemplate(models.Model):
    name = models.CharField(max_length=200)                # "New hire onboarding"
    trigger_category = models.CharField(max_length=30, blank=True)  # matches Ticket.category, optional
    team = models.ForeignKey("base.Team", null=True, blank=True, on_delete=models.CASCADE)
    # None = global/seeded template, same convention as KnowledgeBaseArticle.team
    steps = models.JSONField(default=list)
    # [{"title": "...", "description": "...", "assignee_team": "IT Support"}, ...]
    # A flat JSON list is enough for v1's strictly-sequential, no-DAG shape — a relational
    # step-definition table would be premature until templates need per-step editing UI.

class Workflow(models.Model):
    STATUS_CHOICES = [("in_progress", "In Progress"), ("completed", "Completed"), ("cancelled", "Cancelled")]
    ticket = models.ForeignKey("tickets.Ticket", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="workflows")   # nullable: standalone workflows allowed
    template = models.ForeignKey(WorkflowTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    team = models.ForeignKey("base.Team", null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    created_at = models.DateTimeField(auto_now_add=True)

class WorkflowStep(models.Model):
    STATUS_CHOICES = [("pending", "Pending"), ("active", "Active"), ("done", "Done"), ("skipped", "Skipped")]
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="steps")
    order_index = models.PositiveIntegerField()             # strictly sequential -- no explicit depends_on needed
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignee_team = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    claimed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    completed_at = models.DateTimeField(null=True, blank=True)
```

Only the first `pending` step (lowest `order_index` with no earlier incomplete step) is ever
`active`; completing it flips the next one from `pending` to `active`. That single rule is the
entire "dependency engine" for v1 — no need for a real DAG library or explicit edge table.

## What gets reused from existing code (don't reinvent)

- **Tenant scoping**: mirror `tickets/scoping.py`'s pattern (`user_can_access_ticket`,
  `tickets_queryset_for_user`) for a `user_can_access_workflow`/`workflow_queryset_for_user`.
  Platform-agent cross-tenant access (`User.is_platform_agent`, same file) should extend here
  too rather than forking a second entitlement system.
- **Claim mechanic**: reuse the exact race-safe pattern from `assign_ticket`
  (atomic conditional UPDATE on a null check) for "claim this step" — same shape as
  `Ticket.claimed_at` in the escalation-queue work.
- **Notifications**: reuse `integrations/notify.py`'s fan-out wrapper (Slack + email + in-app,
  already tolerant of Teams being dormant) to notify the next assignee-team when a step goes
  `active`.
- **Audit trail**: log step transitions via `TicketInteraction` when a workflow is
  ticket-linked (same reuse as the remediation-script audit logging), or a lightweight
  `WorkflowStepHistory` only if standalone (ticket-less) workflows turn out to need their own
  audit trail — don't build that until it's clear standalone workflows are actually used.
- **Global vs per-team templates**: mirror `KnowledgeBaseArticle.team` (`team=None` = global/
  seeded, visible to all) — ResolveMeQ can ship a small seed set of common IT templates
  (onboarding, offboarding, equipment provisioning) the same way KB articles are seeded via
  `populate_resolution_templates.py`.

## UI surface (v1)

A "Workflow" section on the ticket detail page, shown only when `ticket.workflows.exists()`:
a checklist, current-step highlighted, a Claim button on the active step (visually the same
pattern as `EscalationQueue.jsx`'s existing claim button), completed steps shown greyed out
with who completed them and when.

## AI's role in v1 (narrow, on purpose)

When a ticket's category matches a `WorkflowTemplate.trigger_category` for the reporter's
team (or a global template), instantiate the `Workflow` + its `WorkflowStep`s from the
template automatically — the AI's job is just categorization (which it already does), not
inventing steps. No LLM call is needed to create a workflow instance in v1.

## Explicit non-goals for v1

- **No branching/parallel steps** — strictly sequential only. A real DAG is a v2+ problem to
  reach for only once a real template needs it.
- **No LLM-generated ad hoc workflows** — templates are fixed/admin-authored (or seeded),
  never freely invented per-ticket.
- **No SLA/timers on steps** — `tickets/sla_settings.py`'s per-priority-hours pattern is a
  reasonable model to copy later, but v1 should ship without it.
- **No external system execution** — a step going "done" is a person checking a box, not an
  automated action. This is deliberately independent of the directory-integration idea that
  was scoped and set aside earlier (see the remediation-script plan) — the two could combine
  later (a step's completion triggering a real directory action), but neither depends on the
  other to ship.
- **No template-authoring UI** — templates ship as seed/fixture data initially, same as KB
  articles did before there was demand for a KB editor.

## Open questions to resolve before starting

1. Do workflows always originate from a ticket, or should standalone workflows (no ticket at
   all — e.g. HR-initiated onboarding) be in scope for v1, or deferred?
2. Does a workflow need its own category taxonomy, or is reusing `Ticket.CATEGORY_CHOICES` as
   the trigger key sufficient, given today's categories (`wifi`, `laptop`, `vpn`, ... `other`)
   don't include anything onboarding/offboarding-shaped yet?
3. Who's the first real template worth shipping — onboarding is the obvious industry example,
   but worth confirming it matches what ResolveMeQ's actual customers ask for before building
   the seed data.

## Rough phasing (once this is picked up)

1. Data model + migration, one hardcoded seed template (e.g. equipment provisioning, if that's
   confirmed as the real customer need), ticket-detail checklist UI, claim-per-step.
2. Notification fan-out on step transitions.
3. A second/third seed template once the first is validated with real usage.
4. Template-authoring UI and/or SLA-on-steps, only if usage shows they're actually needed.
