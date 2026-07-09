"""
Employee Onboarding playbook SKU — template + KB links + auto-start rule.

Shipped as P1-7; see docs/PLAYBOOK_EMPLOYEE_ONBOARDING.md for sales/demo script.
"""

from __future__ import annotations

SKU_ID = "employee-onboarding"
SKU_NAME = "Employee Onboarding Pack"
SKU_TAGLINE = "Day-one ready — accounts, hardware, HR sign-off, and SLA alerts."

ONBOARDING_TEMPLATE_NAME = "Employee onboarding"

ONBOARDING_KB_ARTICLE_TITLES = [
    "New Employee - IT Onboarding Checklist",
]

# Category auto-start is the v1 "rule" until Phase 2 Rules engine ships.
ONBOARDING_AUTOMATION_RULE = {
    "id": "onboarding-auto-start",
    "name": "Auto-start onboarding workflow",
    "description": "When a ticket is created with category onboarding, start the Employee onboarding playbook.",
    "trigger": "ticket.created",
    "condition": {"ticket_field": "category", "equals": "onboarding"},
    "action": "start_workflow",
    "template_trigger_category": "onboarding",
    "status": "active",
    "implemented_via": "workflows.services.maybe_start_workflow_for_ticket",
}

ONBOARDING_TEMPLATE_STEPS = [
    {
        "title": "Provision accounts",
        "description": "Create email, SSO, and core system accounts. See the IT onboarding checklist for the full account list.",
        "assignee_team": "IT Support",
        "assignee_role": "it",
        "step_type": "manual",
        "due_days": 1,
        "kb_links": ["New Employee - IT Onboarding Checklist"],
    },
    {
        "title": "Assign hardware",
        "description": "Prepare laptop, monitor, and peripherals. Confirm shipping or desk delivery before day one.",
        "assignee_team": "IT Support",
        "assignee_role": "it",
        "step_type": "manual",
        "due_days": 2,
        "kb_links": ["New Employee - IT Onboarding Checklist"],
    },
    {
        "title": "Desk & building access",
        "description": "Reserve desk, badge, and building access for in-office hires.",
        "assignee_team": "Facilities",
        "assignee_role": "facilities",
        "step_type": "manual",
        "due_days": 2,
        "skip_when": {"ticket_field": "category", "equals": "remote_onboarding"},
    },
    {
        "title": "Manager sign-off",
        "description": "Confirm start date, role, and equipment list with the hiring manager.",
        "assignee_team": "HR",
        "assignee_role": "hr",
        "step_type": "approval",
        "due_days": 2,
    },
    {
        "title": "Schedule orientation",
        "description": "Book HR orientation and share the week-one plan with the new hire.",
        "assignee_team": "HR",
        "assignee_role": "hr",
        "step_type": "manual",
        "due_days": 3,
    },
    {
        "title": "Day-one check-in",
        "description": "Verify accounts, VPN, MFA, and hardware work. Escalate blockers same day.",
        "assignee_team": "IT Support",
        "assignee_role": "it",
        "step_type": "manual",
        "due_days": 1,
        "kb_links": ["New Employee - IT Onboarding Checklist"],
    },
]
