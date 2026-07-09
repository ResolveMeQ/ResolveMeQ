# AI Confidence Calibration Report (Internal)

**Purpose:** Runbook for publishing the Phase 4 exit-criterion calibration report — comparing agent confidence scores to real ticket outcomes.  
**Audience:** Product, engineering, customer success.  
**Last updated:** July 2026

---

## What this measures

ResolveMeQ logs agent confidence on analyze passes (`AgentConfidenceLog`, source `analyze`). The **advanced analytics** endpoint groups tickets by confidence bucket and compares:

| Outcome | Definition |
|---------|------------|
| Resolved without escalation | `status=resolved` and `escalated_at` is null |
| Escalated | `escalated_at` is set |
| Reopened | `TicketResolution.reopened=True` |

**Goal:** Validate that high-confidence buckets correlate with successful deflection and low-confidence buckets correlate with escalation — so sales and CS can tune thresholds and playbooks with data.

---

## Data source

```
GET /api/tickets/advanced-analytics/
```

Requires authenticated user with access to workspace tickets/workflows. Response includes:

```json
{
  "generated_at": "2026-07-09T...",
  "deflection_by_category": [...],
  "confidence_calibration": [
    {
      "confidence_bucket": "0.8-1.0",
      "samples": 42,
      "resolved_without_escalation_rate_percent": 78.6,
      "escalation_rate_percent": 14.3,
      "reopen_rate_percent": 4.8
    }
  ],
  "workflow_bottlenecks": [...],
  "predictive_routing": {...}
}
```

**Buckets:** `0.8-1.0`, `0.6-0.8`, `0.3-0.6`, `0.0-0.3`, `unknown`

Implementation: `tickets/advanced_analytics.py` → `compute_confidence_calibration()`

---

## How to generate a report (monthly)

### Option A — Web UI

1. Log in as workspace admin.
2. Open **Analytics** — review **Confidence calibration** card.
3. Export CSV (includes deflection-by-category; extend export if full calibration rows needed).

### Option B — API + script

```bash
# Replace TOKEN and API_BASE for your environment
curl -s -H "Authorization: Bearer $TOKEN" \
  "$API_BASE/api/tickets/advanced-analytics/" \
  | jq '.confidence_calibration, .deflection_by_category'
```

### Option C — Django shell (all teams, internal only)

```python
from tickets.models import Ticket
from tickets.advanced_analytics import compute_advanced_analytics
from workflows.models import Workflow
from workflows.scoping import workflows_queryset_for_user

# Example: single team
from base.models import Team
team = Team.objects.get(name="Your Pilot Customer")
ticket_qs = Ticket.objects.filter(team=team)
wf_qs = Workflow.objects.filter(team=team)
print(compute_advanced_analytics(ticket_qs=ticket_qs, workflow_qs=wf_qs)["confidence_calibration"])
```

---

## Report template (copy for Confluence / Notion)

```markdown
# ResolveMeQ Calibration Report — [Month YYYY]

**Workspace:** [Customer or internal pilot name]  
**Period:** [start] – [end]  
**Generated:** [date]

## Summary

- Total agent-processed tickets: [from outcome-metrics deflection_rate denominator]
- Overall deflection rate: [%] (`GET /api/tickets/outcome-metrics/`)
- Samples in calibration: [sum of bucket samples]

## Confidence vs outcomes

| Bucket | Samples | Resolved w/o escalation | Escalation | Reopen |
|--------|---------|-------------------------|------------|--------|
| 0.8-1.0 | | | | |
| 0.6-0.8 | | | | |
| 0.3-0.6 | | | | |
| 0.0-0.3 | | | | |

## Deflection by category

| Category | Processed | Deflected | Rate % |
|----------|-----------|-----------|--------|
| ... | | | |

## Workflow bottlenecks (top 3)

1. [step title] — [overdue_now] overdue, median [X]h from start
2. ...

## Actions

- [ ] Raise escalate threshold if 0.6-0.8 bucket reopen rate > 10%
- [ ] Add KB articles for categories with deflection < 20%
- [ ] Adjust playbook SLAs for bottleneck steps

## Agent SLO (same period)

`GET /api/monitoring/agent-slo/` — success rate, p95 latency, circuit opens.
```

---

## Minimum sample sizes

| Bucket samples | Interpretation |
|----------------|----------------|
| < 10 | Directional only — do not change thresholds |
| 10–50 | Review trends; pilot decisions OK |
| 50+ | Suitable for customer-facing ROI conversations |

Pair with **outcome metrics** (`GET /api/tickets/outcome-metrics/`) for deflection rate, workflow completion, and onboarding playbook stats.

---

## Related endpoints

| Endpoint | Use |
|----------|-----|
| `GET /api/tickets/outcome-metrics/` | Headline deflection %, escalated count, workflow counts |
| `GET /api/tickets/advanced-analytics/` | Calibration buckets, category deflection, bottlenecks |
| `GET /api/monitoring/agent-slo/` | Agent reliability during the period |
| `GET /api/tickets/routing/metrics/` | Predictive routing reassignment rate |

---

*Phase 4 exit criterion: publish this report internally after first pilot month with ≥50 analyze confidence logs.*
