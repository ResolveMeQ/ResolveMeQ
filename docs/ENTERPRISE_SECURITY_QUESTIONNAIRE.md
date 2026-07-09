# Enterprise Security Questionnaire — ResolveMeQ

**Purpose:** Pre-filled answers for security reviews, RFPs, and SOC2 prep conversations.  
**Audience:** Sales, solutions engineering, security reviewers.  
**Last updated:** July 2026 — answers reflect **shipped** product (Phase 4), not roadmap.

> **Disclaimer:** This document describes product capabilities. Formal certifications (SOC2 Type II, ISO 27001, HIPAA BAA) are **commercial/ops** decisions — confirm status with leadership before claiming certification.

---

## 1. Data isolation & multi-tenancy

| Question | Answer |
|----------|--------|
| How is customer data isolated? | Each **workspace** maps to a `Team`. Tickets, workflows, rules, KB articles, audit events, and partner API keys are scoped to the team. API queries enforce team membership via `tickets/scoping.py` and `workflows/scoping.py`. |
| MSP / multi-client support? | **MSP mode** (P3-5): parent MSP workspace can manage child client teams. Child data remains team-scoped; MSP operators see only clients they manage. |
| Cross-tenant access? | Platform agents (`User.is_platform_agent`) have explicit cross-tenant paths; standard users cannot access other teams' data. |

---

## 2. Authentication & authorization

| Question | Answer |
|----------|--------|
| User authentication | JWT (Django REST + frontend session). Standard Django user model with team membership. |
| API authentication (partners) | **Partner API keys** (`rmq_pk_*`) with per-key scopes: `tickets:read`, `tickets:write`, `workflows:read`, `rules:read`. Keys are team-scoped; only workspace owners create/revoke keys in Settings → Integrations → Partner API. |
| Role-based access | Workspace owner, team members, ops roles on workflow steps (`Profile.ops_role`: IT, HR, etc.). Escalation queue and workflow claim use atomic assign patterns. |
| Agent service auth | Separate agent token (`IsAuthenticatedOrAgent`) for AI callback endpoints; throttled. |

---

## 3. Audit logging & immutability

| Question | Answer |
|----------|--------|
| Compliance audit log? | **Yes (P4-1).** Append-only `ComplianceAuditEvent` model — records cannot be updated or deleted after insert. |
| What is logged? | Ticket lifecycle (created, escalated, resolved), workflow step completions, automation rule CRUD and executions, MSP mode events, audit export actions. |
| Who can view audit logs? | Authenticated workspace admins via **Settings → Security** and `GET /api/audit/events/`. |
| Export for auditors? | **Yes.** `GET /api/audit/export/?export_format=csv` (CSV download). Export itself is audited (`audit.exported`). |
| Ticket interaction history? | Per-ticket audit trail at `GET /api/tickets/<id>/audit-log/` (`TicketInteraction` — chat, feedback, agent responses). |

**Event types (current):** `ticket.created`, `ticket.escalated`, `ticket.resolved`, `workflow.step.completed`, `rule.executed`, `rule.created`, `rule.updated`, `rule.deleted`, `msp.enabled`, `msp.client_created`, `audit.exported`.

---

## 4. AI reliability & safety

| Question | Answer |
|----------|--------|
| Agent outage handling | **Circuit breaker (P4-2):** Redis-backed breaker opens after configurable consecutive failures (`AI_AGENT_CIRCUIT_MAX_FAILURES`, default 5). Open window: `AI_AGENT_CIRCUIT_OPEN_SECONDS` (default 300s). Tickets receive fallback messaging instead of hanging. |
| Agent HTTP timeout | Centralized `base/agent_client.py` — max **30s** (`AI_AGENT_HTTP_TIMEOUT`). All agent calls (ticket processing, chat, step assistant) route through this client. |
| Agent SLO visibility | `GET /api/monitoring/agent-slo/` — success rate, latency, circuit state. Included in admin health payload. |
| Confidence-based routing | Autonomous agent uses thresholds (HIGH/MEDIUM/LOW). Security, outage, and data-loss categories **never** auto-resolve. |
| Confidence calibration | **Advanced analytics (P4-5):** `GET /api/tickets/advanced-analytics/` buckets analyze confidence vs resolved/escalated/reopened outcomes. See `docs/CALIBRATION_REPORT.md`. |
| Human in the loop | Escalation queue, workflow step claims, solution verification, rollback of autonomous actions where supported. |

---

## 5. Integrations & outbound data

| Question | Answer |
|----------|--------|
| Notification channels | Slack, Microsoft Teams, email, in-app — unified via `integrations/notify.py`. |
| IdP / directory read | Okta, Google Workspace, Microsoft 365 **read** connectors for workflow auto-check steps (P2-7, P2-8). |
| Ticketing sync | Jira Cloud escalate sync (P2-9). |
| Outbound webhooks | Customer-configured webhooks on automation events (P2-6). |
| Partner intake API | Public Partner API v1 — documented in `docs/PUBLIC_API.md`. |
| Connector isolation | No vendor SDKs in Django views; timeouts and circuit breakers required per architecture principles. |

---

## 6. Encryption & infrastructure (deployment-dependent)

| Question | Answer |
|----------|--------|
| Data at rest | Depends on **hosting choice** (PostgreSQL, Redis on customer VPC or ResolveMeQ-managed VPS). Engineering does not mandate a specific cloud — document the deployment model per deal. |
| Data in transit | HTTPS for API and web app (TLS termination at reverse proxy). Agent service uses HTTPS to Django callbacks. |
| Secrets management | API keys, integration tokens, partner keys stored in DB; env vars for service secrets. **Recommend** secrets manager (Vault, AWS SM) for production — ops checklist item. |
| PII in logs | Audit summaries are truncated; avoid logging full ticket bodies in compliance events. Review log retention policy per deployment. |

---

## 7. Availability, backup, and incident response

| Question | Answer |
|----------|--------|
| Async processing | Celery + Redis for ticket agent processing, notifications, connector checks. |
| Retry policy | Celery exponential backoff on agent tasks (60s / 120s / 240s, max 3 retries). |
| Health monitoring | Admin health endpoints; agent circuit breaker metrics. |
| Backup / DR | **Deployment-specific** — not enforced in application code. Reference `docs/DEPLOYMENT_GUIDE.md` and ops runbooks. |

---

## 8. Compliance posture (honest framing)

| Claim | Status |
|-------|--------|
| SOC2 Type II | **Not claimed** in product — audit log and export support **preparation** |
| GDPR | Data processing terms are **legal/commercial** — product supports team isolation and export |
| HIPAA | **Not positioned** for healthcare without BAA and deployment review |
| AI governance | Confidence calibration, escalation rules, immutable audit for autonomous actions |

---

## 9. Evidence pointers (for reviewers)

| Capability | Where to verify |
|------------|-----------------|
| Audit log API | `monitoring/audit_views.py`, `GET /api/audit/events/` |
| Immutable model | `monitoring/models.py` — `ComplianceAuditEvent.save/delete` |
| Circuit breaker | `base/agent_circuit.py`, `base/agent_client.py` |
| Partner API scopes | `public_api/permissions.py`, `docs/PUBLIC_API.md` |
| Advanced analytics | `tickets/advanced_analytics.py`, Analytics page in web app |
| Roadmap status | `docs/COMPETITIVE_ENGINEERING_ROADMAP.md` |

---

## 10. Open items (do not claim as complete)

- [ ] Formal SOC2 audit engagement
- [ ] Customer-specific data residency contract
- [ ] Partner pilot reference on public API (Phase 4 exit criterion)
- [ ] Penetration test report (schedule with security vendor)

---

*Update this document when audit event types, scopes, or enterprise controls change. Owner: Engineering + Product.*
