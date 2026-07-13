# ResolveMeQ Business Adoption Test Plan

**Purpose:** Simulate a real company evaluating and piloting ResolveMeQ. Work through every section as if you are the buyer — IT director, HR lead, support manager, and end employee — and record where the product breaks, confuses, or disappoints.

**How to use this doc**
1. Pick an environment (see [Environments](#environments)).
2. Create test accounts for each [persona](#test-personas).
3. Run phases in order; later phases depend on earlier setup.
4. For every step, mark **Pass / Fail / Blocked** and write a one-line note in the failure log.
5. Treat “works but feels bad” as a **Fail (UX)** — adoption dies on friction, not only on 500 errors.

---

## Environments

| Environment | App | API | When to use |
|-------------|-----|-----|-------------|
| **Production pilot** | https://app.resolvemeq.net | https://api.resolvemeq.net | Real OAuth (Slack, Okta, M365), billing, sales demos |
| **Local full stack** | http://localhost:5173 | http://localhost:8000 | Permission matrix, destructive tests, rule edits |
| **Marketing / docs** | https://resolvemeq.net | — | SEO, product manual, pricing page accuracy |

**Local prerequisites**
```bash
# Terminal 1 — API (+ Postgres/Redis via Docker)
cd ResolveMeQ && docker compose --profile local-db up -d
python manage.py migrate && python manage.py runserver

# Terminal 2 — Agent (required for AI)
cd resolvemeq-agent && docker compose up -d   # or uvicorn per repo README

# Terminal 3 — Web app
cd resolvemeqwebapp && npm run dev
# .env: VITE_API_URL=http://localhost:8000
```

**Production pilot workspace setup**
- Use a dedicated workspace (not your live company data).
- Seed the onboarding playbook if missing:
  ```bash
  docker compose exec web python manage.py install_playbook_bundle employee-onboarding
  ```
- Confirm API health: `curl -s https://api.resolvemeq.net/health/`

---

## Test personas

Create four accounts (or use four browsers / incognito profiles).

| Persona | Email pattern | Role in product | What they should *not* be able to do |
|---------|---------------|-----------------|--------------------------------------|
| **Alex — Owner** | `alex-owner@yourpilot.com` | Workspace creator, billing, full admin | — |
| **Jordan — IT delegate** | `jordan-it@yourpilot.com` | Delegated admin: `manage_playbooks` + `manage_members` only | Connect Slack, view audit log, change billing |
| **Sam — Employee** | `sam-employee@yourpilot.com` | Member, ops role **General** | Edit playbooks, see escalation queue, invite users |
| **Riley — IT ops** | `riley-it@yourpilot.com` | Member, ops role **IT Support** | Same as Sam except can claim IT workflow steps |

**Optional fifth persona**
| **Pat — Platform agent** | Staff account with `is_platform_agent` | Cross-tenant escalation queue | Only if you have a test staff account |

---

## Failure log template

Copy this table at the start of your pilot and append rows as you go.

| # | Phase | Step | Result | Severity | What happened | Screenshot / URL |
|---|-------|------|--------|----------|---------------|------------------|
| 1 | | | Pass/Fail/Blocked | P0–P3 | | |

**Severity guide**
- **P0** — Cannot complete core journey (signup, create ticket, pay, security leak)
- **P1** — Core journey completes but wrong data, wrong tenant, or silent failure
- **P2** — Feature missing or broken but workaround exists
- **P3** — Cosmetic, doc drift, “coming soon” placeholder

---

## Phase 0 — First impression (30 min)

*Simulate a buyer landing from marketing before anyone creates an account.*

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 0.1 | Open https://resolvemeq.net | Site loads, pricing/features visible | | |
| 0.2 | Click primary CTA “Get started” / signup link | Lands on **https://app.resolvemeq.net/signup** (not `/register`) | | **Known risk:** some marketing links use `/register` which does not exist |
| 0.3 | Read https://resolvemeq.net/docs/getting-started | Steps match what you can actually do in the app | | |
| 0.4 | Open https://app.resolvemeq.net/knowledge-base **without logging in** | Public KB loads, search works | | |
| 0.5 | Open a deep link `/knowledge-base/article/test-slug/123` | Redirects to article view | | |
| 0.6 | Open a nonsense URL `/this-does-not-exist` while logged out | **Watch:** app redirects to KB, not 404 — confusing for bookmarks | | |

---

## Phase 1 — Account & workspace bootstrap (45 min)

*Alex (owner) signs up and stands up the org.*

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 1.1 | Sign up at `/signup` with company name + strong password | Account created; redirected to login or verify | | |
| 1.2 | Complete email verification at `/verify` if enabled | Can log in afterward | | |
| 1.3 | Log in at `/login` | Dashboard loads; default workspace exists | | |
| 1.4 | Product tour auto-starts (or replay via Settings → General → “Replay product tour”) | Tour highlights tickets, search, account menu | | |
| 1.5 | Settings → General: update name, timezone, phone | Saves and persists after refresh | | |
| 1.6 | Settings → Appearance: switch light/dark; refresh | Theme sticks (no flash back to wrong mode) | | |
| 1.7 | Header workspace switcher: only one workspace initially | Correct name shown | | |
| 1.8 | Users → Invite **Jordan**, **Sam**, **Riley** | Invitation emails sent (or invite links work) | | **Watch:** member limit on trial — may block invites |
| 1.9 | Accept invites in three separate browsers | Each lands in the same workspace | | |
| 1.10 | Teams → set Riley ops role **IT Support**, Sam **General** | Roles saved | | |
| 1.11 | Teams → Jordan → Delegated permissions: enable **Playbooks** + **Members** only | Jordan cannot connect integrations later | | |
| 1.12 | Billing → view current plan, usage meters | Trial/Starter shown; AI quota visible | | |
| 1.13 | Log out; Forgot password flow | Reset email arrives; new password works | | |

**Delegation checks (do immediately after 1.11)**

| # | As Jordan | Expected | Pass? |
|---|-----------|----------|-------|
| 1.14 | Open `/workflows/templates` | Can view/edit templates | |
| 1.15 | Open `/settings/automation` | Can create/edit rules | |
| 1.16 | Open `/settings/integrations` | View-only banner; Connect buttons disabled | |
| 1.17 | Open `/billing` | Can view or blocked? (record actual behavior) | |
| 1.18 | Open `/escalation-queue` | **Should not** appear in nav or returns forbidden | |

---

## Phase 2 — Knowledge base & deflection (45 min)

*Test self-service before paid support load.*

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 2.1 | As Alex, create KB article: “VPN won’t connect from home” with tags `vpn`, `wifi` | Article published | | |
| 2.2 | Log out; search KB for “VPN home” | Article appears in results | | |
| 2.3 | Mark article helpful / not helpful | Vote counts update | | |
| 2.4 | Community tab `?view=community` → post a question | Question visible | | |
| 2.5 | As Sam, answer the question | Answer appears; author notified if configured | | |
| 2.6 | SEO URL `/community/q/slug/id` | Opens correct question | | |

---

## Phase 3 — Ticket + AI agent (60 min)

*The core “employee asks for help” loop.*

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 3.1 | As Sam, Tickets → New: category **Network**, issue “VPN won’t connect from home” | Ticket created | | |
| 3.2 | Wait for AI processing (spinner / status) | Agent analyzes ticket; confidence score shown | | **Blocked if agent service down** |
| 3.3 | Open AI chat panel; ask follow-up “I already restarted my laptop” | Multi-turn reply; cites KB article from Phase 2 | | |
| 3.4 | Click “Yes, it’s fixed” (or equivalent resolution feedback) | Ticket moves toward resolved / deflected | | |
| 3.5 | Create ticket with screenshot attachment | Image uploads and displays | | |
| 3.6 | Create ticket on mobile-width viewport (375px) | Form usable; chat panel accessible | | |
| 3.7 | Exhaust or mock AI quota (Billing limits) | Clear upgrade message, not silent failure | | |
| 3.8 | Stop agent container; create new ticket | Graceful fallback message, not infinite spinner | | |
| 3.9 | Deep link `/tickets/12345` (real id) | Opens ticket detail | | |
| 3.10 | `/tickets/99999999` invalid id | Sensible error, not blank screen | | |

**VPN deflection journey (sales demo script)**

| Step | Action | Success criteria |
|------|--------|------------------|
| A | Employee describes VPN issue | AI responds < 60s |
| B | AI cites internal KB | At least one citation link |
| C | Employee confirms fix | Ticket resolved without human |
| D | Dashboard deflection metric | Count increases |

---

## Phase 4 — Escalation & human handoff (45 min)

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 4.1 | As Sam, escalate ticket with reason + summary | Status → escalated; toast confirms | | |
| 4.2 | As Sam, check sidebar | **No** Escalation Queue link | | |
| 4.3 | As Alex, open `/escalation-queue` | Escalated ticket listed with priority | | |
| 4.4 | Claim ticket from queue | Assigned to Alex; status updates | | |
| 4.5 | Reply as agent; change status | Sam sees update on their ticket | | |
| 4.6 | Resolve ticket | Both parties see resolved state | | |
| 4.7 | If Jira configured: escalate triggers Jira issue | Issue created in project | | Phase 6 |

---

## Phase 5 — Workflows & playbooks (90 min)

*IT ops runbook — the “we’re not just a chatbot” proof.*

**Setup (Alex or Jordan)**

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 5.1 | Run `install_playbook_bundle employee-onboarding` on server | Bundle installed | |
| 5.2 | `/workflows/templates` → Employee onboarding pack visible | 9 steps, KB links, auto-check steps | |
| 5.3 | `/settings/automation` → rule exists: `ticket.created` + category=onboarding → start workflow | Rule active | |

**Happy path**

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 5.4 | Sam creates ticket: category **Onboarding**, “New hire Jane Doe starts Monday” | Workflow auto-starts on ticket | | |
| 5.5 | Ticket detail shows workflow checklist | First step active | | |
| 5.6 | Riley (IT Support) claims first IT step | Step assigned to Riley | | |
| 5.7 | Riley completes step | Next step activates | | |
| 5.8 | `/workflows` → active workflow listed | SLA / overdue badges sane | | |
| 5.9 | Complete all steps | Workflow completed; ticket resolved | | |
| 5.10 | Dashboard onboarding metrics | Started/completed counts updated | | |

**Variants & edge cases**

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 5.11 | Ticket category **remote_onboarding** | Facilities step skipped | |
| 5.12 | Sam tries to claim IT-only step | Blocked or hidden | |
| 5.13 | Step assistant on active step | KB hints / LLM guidance appears | |
| 5.14 | Let step go past due date | Shows overdue on `/workflows` | |
| 5.15 | Jordan edits template name in `/workflows/templates` | Saves; new tickets use updated template | |
| 5.16 | Alex creates second workspace; switch header | Workflows/templates isolated per workspace | |

---

## Phase 6 — Integrations (120 min)

*Connect the stack a mid-market IT team actually uses. Do on **production pilot** with real credentials.*

### 6A — Slack

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 6A.1 | Alex: Settings → Integrations → Connect Slack | OAuth completes; `?slack=connected` | | Needs `SLACK_CLIENT_ID` etc. on API |
| 6A.2 | In Slack: `/resolvemeq` or app shortcut | Modal opens to create ticket | | |
| 6A.3 | Create ticket from Slack | Appears in ResolveMeQ | | |
| 6A.4 | Escalate ticket | Message in ops/escalation channel | | |
| 6A.5 | Jordan (no integration perm) | Cannot disconnect Slack | | |
| 6A.6 | Disconnect + reconnect | Clean state | | |

### 6B — Microsoft Teams

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 6B.1 | Connect Teams → copy link code | Code displayed | |
| 6B.2 | Install bot in Teams; enter code | Linked successfully | |
| 6B.3 | Workflow step becomes active | Teams notification to assignees | |
| 6B.4 | Escalate ticket | Teams ops notification | |

### 6C — Okta / Google Workspace / Microsoft 365

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 6C.1 | Connect Okta (domain + OAuth) | Status: connected | | Redirect: `https://api.resolvemeq.net/api/integrations/okta/oauth/redirect/` |
| 6C.2 | Connect Google Workspace | Status: connected | | |
| 6C.3 | Connect Microsoft 365 | Status: connected | | **Watch:** 503 if `MICROSOFT365_CLIENT_ID` missing in container env |
| 6C.4 | Onboarding workflow: Okta auto_check step | Auto-completes when user exists in Okta | | |
| 6C.5 | Same for Google / M365 steps | At least one connector auto-completes | | Pilot acceptance: ≥2 connectors |
| 6C.6 | Disconnect each | Status cleared; auto_check stops passing | | |

**OAuth env verification (ops)**
```bash
docker compose exec web printenv MICROSOFT365_CLIENT_ID
docker compose exec web printenv OKTA_CLIENT_ID
# Empty = integration button will fail no matter what UI shows
```

### 6D — Jira Cloud

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 6D.1 | Settings → Jira: site URL, email, API token, project key | Saves without error | |
| 6D.2 | Escalate ticket | Jira issue created | |
| 6D.3 | Resolve ticket | Jira transition applied | |

### 6E — Outbound webhooks

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 6E.1 | Create webhook pointing to https://webhook.site or RequestBin | Secret shown once | |
| 6E.2 | Subscribe to `ticket.created`, `ticket.escalated`, `ticket.resolved`, `workflow.step.completed` | All fire on actions | |
| 6E.3 | Verify `X-ResolveMeq-Signature` HMAC | Signature validates | |
| 6E.4 | Jordan without `manage_webhooks` | Cannot create webhooks | |

### 6F — Partner REST API

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 6F.1 | Alex creates Partner API key (`rmq_pk_…`) | Key shown once | |
| 6F.2 | `POST /api/public/v1/tickets/create/` with key | Ticket created in workspace | |
| 6F.3 | `GET /api/public/v1/workflows/?ticket_id=` | Workflow status returned | |
| 6F.4 | Revoke key; retry request | 401/403 | |

---

## Phase 7 — Automation rules (60 min)

*Alex/Jordan configure “when X happens, do Y” without engineering.*

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 7.1 | Create rule: `ticket.escalated` → `notify_teams` | Rule saved | | |
| 7.2 | Edit rule (pencil icon): change to `notify_slack` + channel id | PATCH succeeds | | |
| 7.3 | Dry run rule | Log entry with “Would post…” | | |
| 7.4 | Trigger for real (escalate ticket) | Slack/Teams message received | | |
| 7.5 | Rule: `workflow.step.completed` → `notify_slack` | Fires when step completed | | |
| 7.6 | Rule: `ticket.created` + category=wifi → `start_workflow` | Non-matching category skipped | | |
| 7.7 | Rule: `call_webhook` action | HTTP POST received at your endpoint | | |
| 7.8 | Rule: `assign_ticket` with user id | Ticket assigned | | **UX gap:** raw user ID, no people picker |
| 7.9 | Pause rule (toggle) | Stops firing | | |
| 7.10 | Sam opens `/settings/automation` | View-only banner | | |
| 7.11 | Execution log section | Recent runs with success/failed | | |

**Backend-only features (API or seed — expect UI gaps)**

| Feature | How to test | Expected UI gap |
|---------|-------------|-----------------|
| `run_agent` action | PATCH via API | No form fields in UI |
| `schedule.cron` trigger | Create via API | No cron builder in UI |

---

## Phase 8 — Analytics, audit & compliance (30 min)

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 8.1 | `/analytics` — deflection by category | Chart renders with data from Phase 3 | | |
| 8.2 | Confidence calibration card | Data or empty state | | |
| 8.3 | Workflow bottlenecks | Shows slow steps if any | | |
| 8.4 | “Performance tracking” / “Trend analysis” cards | **Likely “Coming soon”** — record as UX gap | | |
| 8.5 | Alex: Settings → Security → Audit log | Events from rule create, integration connect | | |
| 8.6 | Export audit log | CSV/JSON downloads | | |
| 8.7 | Jordan without `view_audit_log` | Audit section hidden or read-only blocked | | |
| 8.8 | Dashboard `/` metrics | Ticket volume, deflection, recent tickets align with actions | | |

---

## Phase 9 — Billing & limits (45 min)

| # | Action | Expected | Pass? | Notes |
|---|--------|----------|-------|-------|
| 9.1 | View plan limits: members, AI operations, teams | Matches subscription | | |
| 9.2 | Invite users beyond member limit | Clear error mentioning upgrade | | |
| 9.3 | Upgrade plan (Dodo checkout) | Redirect `?checkout=success`; plan updates | | Use test mode if available |
| 9.4 | Download invoice | PDF/link works | | |
| 9.5 | Jordan tries to change plan | Should fail or hide controls | | |

---

## Phase 10 — MSP mode (optional, 45 min)

*Only if you sell through MSPs.*

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 10.1 | Teams → Enable MSP mode | Hub workspace flagged | |
| 10.2 | Add client workspace “Acme Corp” | Client appears in list | |
| 10.3 | Switch active workspace to client | Isolated tickets/templates | |
| 10.4 | Return to hub; view client stats | Metrics per client | |

---

## Phase 11 — Security & tenant isolation (60 min)

*Pretend you are a hostile or careless user.*

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 11.1 | Sam pastes another workspace’s ticket UUID in API/browser | 404 or forbidden | |
| 11.2 | Sam PATCHes another user’s ticket via DevTools | Rejected | |
| 11.3 | Jordan edits rule in workspace A while workspace B active | Rule not visible or not editable | |
| 11.4 | Expired JWT / cleared localStorage | Redirect to login, no data leak | |
| 11.5 | XSS in ticket description | Escaped in UI | |
| 11.6 | Webhook signature with tampered body | Receiver rejects | |
| 11.7 | Partner API key from workspace A on workspace B ticket | Rejected | |

---

## Phase 12 — Mobile & accessibility spot check (30 min)

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 12.1 | iPhone/Android: login + create ticket | Usable without horizontal scroll | |
| 12.2 | Keyboard-only: open ticket, send chat message | Focus order sane | |
| 12.3 | Screen reader: escalation button | Has accessible label | |
| 12.4 | Dark mode contrast on warning banners | Readable | |

---

## Five flagship demo journeys (run before any customer call)

These are the minimum “business adoption” proofs. Each should complete in **≤15 minutes** with a crisp narrative.

### Journey 1 — VPN deflection (employee self-service)
1. Publish VPN KB article.
2. Employee creates Network ticket.
3. AI cites KB and resolves without human.
4. Dashboard shows deflection.

### Journey 2 — Escalation to human
1. Employee escalates with phone + summary.
2. Owner claims from escalation queue.
3. Agent resolves; employee sees closure.

### Journey 3 — Employee onboarding playbook
1. Install `employee-onboarding` bundle.
2. Connect ≥1 IdP (Okta/Google/M365).
3. Create onboarding ticket → workflow auto-starts.
4. IT claims steps; connector auto-check completes.
5. Workflow completes end-to-end.

### Journey 4 — Automation rule
1. Create `ticket.escalated` → notify Slack/Teams.
2. Edit rule to add webhook.
3. Escalate → all channels fire.
4. Show execution log.

### Journey 5 — Delegated admin
1. Owner grants IT lead playbooks-only.
2. IT lead edits template + automation rule.
3. IT lead **cannot** connect Slack or view audit.
4. Employee still creates tickets normally.

---

## Known fragile areas (watch list)

Use this as a pre-brief — these fail often in pilots even when “the demo worked once.”

| Area | Symptom | Likely cause |
|------|---------|--------------|
| Microsoft OAuth | 503 on connect | `MICROSOFT365_CLIENT_ID` empty in container (compose `environment:` override vs `env_file`) |
| AI chat | Infinite spinner | Agent service down; Celery worker not running |
| AI citations | Generic answer, no KB links | New articles have no votes; agent not reachable; query mismatch |
| Automation notify | Rule “succeeds” but no message | Slack/Teams not connected; missing channel id |
| Member invite | 400 on invite | Trial plan member limit = 1 |
| Marketing signup link | 404 | URL uses `/register` instead of `/signup` |
| Unknown app routes | Lands on KB | Wildcard route redirects `*` → `/knowledge-base` |
| Analytics | Empty or “Coming soon” | Not enough ticket volume yet; some cards unimplemented |
| Escalation queue | Delegate expects access | Only owners + platform agents |
| Global automation rules | Cannot edit | Seeded global rules are staff-only |
| Assign ticket action | Hard to use | UI asks for numeric user id |
| Theme | Flash wrong mode on navigation | Server vs local theme race |
| Docs vs reality | Feature “missing” in old roadmap | Check app first — automation, Teams, Jira are shipped |

---

## Pilot exit criteria (business sign-off)

Mark the pilot **successful** only if all are true:

- [ ] **Journey 1–3** pass on production pilot workspace
- [ ] **Journey 4** passes with at least one real notification channel
- [ ] **Journey 5** passes without permission leaks
- [ ] No **P0** items open in failure log
- [ ] ≤3 **P1** items open, each with owner and workaround
- [ ] IT lead can run onboarding demo without engineering in the room (≤10 min)
- [ ] Security contact comfortable with audit log + webhook signing demo
- [ ] Billing path validated (upgrade or confirmed trial limits documented)

---

## Related docs

| Doc | Path |
|-----|------|
| Employee onboarding playbook | `docs/playbooks/PLAYBOOK_EMPLOYEE_ONBOARDING.md` |
| Integration env vars | `docs/misc/TODO.md` |
| Deployment | `docs/deployment/DEPLOYMENT_GUIDE.md` |
| Product manual (user-facing) | https://resolvemeq.net/docs |
| Partner API | `docs/api/PUBLIC_API.md` |
| Engineering roadmap (may be stale) | `docs/architecture/COMPETITIVE_ENGINEERING_ROADMAP.md` |

---

*Last updated: July 2026 — align with app at `app.resolvemeq.net` and API at `api.resolvemeq.net`.*
