# Employee Onboarding Playbook (SKU)

**SKU ID:** `employee-onboarding`  
**Roadmap:** P1-7 / P3-2 — sellable IT ops playbook for new hires  
**Competitive pitch:** Onboarding with owners, SLAs, connector verification, and Slack alerts — not tickets lost in a queue.

## What’s in the pack

| Component | Description |
|-----------|-------------|
| **Playbook template** | 9-step global workflow: IT provisioning, Okta/Google/M365 auto-checks, facilities (office only), HR approval, orientation, day-one check-in |
| **KB articles** | Links to *New Employee - IT Onboarding Checklist* on relevant steps |
| **Resolution template** | *New Employee IT Provisioning* — apply to linked tickets |
| **Automation rule** | `ticket.created` + `category=onboarding` → auto-start playbook (via rules engine) |
| **Connector auto-complete** | 3 `auto_check` steps verify Okta, Google Workspace, and Microsoft 365 when integrations are connected |
| **Metrics** | Completion rate, overdue count, workflows started/completed on dashboard |

## Install (VPS / fresh env)

```bash
python manage.py install_playbook_bundle employee-onboarding
# or individually:
python manage.py seed_kb
python manage.py seed_onboarding_playbook
python manage.py seed_automation_rules
```

## 10-minute demo script

1. **Show the SKU** (2 min) — Open **Playbooks** → Employee Onboarding pack. Walk through steps, KB links, resolution template, and 3 connector auto-checks.
2. **Connect integrations** (1 min) — Settings → Okta / Google / M365 (at least one for demo).
3. **Trigger the playbook** (2 min) — Create ticket: category **Onboarding**, reporter email matches a user in your IdP. Workflow starts automatically.
4. **Manual + auto steps** (3 min) — IT completes “Provision accounts”; Okta/Google/M365 steps auto-verify and mark done when checks pass.
5. **Close the loop** (2 min) — Complete HR approval and remaining steps; ticket resolves; dashboard shows onboarding metrics.

**Remote hire variant:** Create ticket with category `remote_onboarding` — facilities desk step is skipped automatically.

## API

- `GET /api/workflows/playbooks/employee-onboarding/` — full SKU bundle (template, KB, rule, resolution template, metrics)
- Outcome metrics include `onboarding_playbook` from `GET /api/tickets/outcome-metrics/`

## Acceptance (pilot)

- [ ] End-to-end demo completes in ≤10 minutes
- [ ] ≥2 connector steps auto-complete when integrations connected (P3-3)
- [ ] ≥80% of pilot onboarding workflows reach `completed` within SLA window
- [ ] Sales can quote “Employee Onboarding Pack” without engineering in the room

## Out of scope (this SKU)

- Visual rule builder beyond automation rules admin
- LLM-generated workflow steps
