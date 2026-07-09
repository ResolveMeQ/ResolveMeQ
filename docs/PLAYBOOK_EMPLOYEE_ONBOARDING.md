# Employee Onboarding Playbook (SKU)

**SKU ID:** `employee-onboarding`  
**Roadmap:** P1-7 — sellable IT ops playbook for new hires  
**Competitive pitch:** Onboarding with owners, SLAs, and Slack alerts — not tickets lost in a queue.

## What’s in the pack

| Component | Description |
|-----------|-------------|
| **Playbook template** | 6-step global workflow: IT provisioning, facilities (office only), HR approval, orientation, day-one check-in |
| **KB articles** | Links to *New Employee - IT Onboarding Checklist* on relevant steps |
| **Automation rule** | `ticket.created` + `category=onboarding` → auto-start playbook (via `maybe_start_workflow_for_ticket`) |
| **Metrics** | Completion rate, overdue count, workflows started/completed on dashboard |

## Install (VPS / fresh env)

```bash
python manage.py seed_kb                    # KB checklist article
python manage.py seed_onboarding_playbook   # Upgrade global onboarding template
# or: python manage.py populate_workflow_templates
```

## 10-minute demo script

1. **Show the SKU** (2 min) — Open **Playbooks** → Employee Onboarding pack card. Walk through steps, KB links, and the auto-start rule.
2. **Set ops roles** (1 min) — **Users** → assign IT / HR / Facilities roles to demo teammates.
3. **Trigger the playbook** (2 min) — Create ticket: category **Onboarding**, issue “New hire Jane Doe starts Monday.” Workflow starts automatically; first IT step is active with SLA due date.
4. **Claim & advance** (3 min) — IT claims step 1, marks done; HR approves manager sign-off; show Slack/in-app step notifications if integrated.
5. **Close the loop** (2 min) — Complete final step; ticket resolves; dashboard shows **Onboarding completion** metric.

**Remote hire variant:** Create ticket with category `remote_onboarding` — facilities desk step is skipped automatically.

## API

- `GET /api/workflows/playbooks/employee-onboarding/` — full SKU bundle (template, KB, rule, metrics)
- Outcome metrics include `onboarding_playbook` object from `GET /api/tickets/outcome-metrics/`

## Acceptance (pilot)

- [ ] End-to-end demo completes in ≤10 minutes
- [ ] ≥80% of pilot onboarding workflows reach `completed` within SLA window
- [ ] Sales can quote “Employee Onboarding Pack” without engineering in the room

## Out of scope (this SKU)

- Okta / M365 auto-check connectors (Phase 2)
- Visual rule builder (Phase 2)
- LLM-generated steps
