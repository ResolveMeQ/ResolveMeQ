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

ONBOARDING_RESOLUTION_TEMPLATE_NAME = "New Employee IT Provisioning"

ONBOARDING_RESOLUTION_TEMPLATE = {
    "name": ONBOARDING_RESOLUTION_TEMPLATE_NAME,
    "description": "Standard IT provisioning checklist for new hires — accounts, access, and day-one readiness.",
    "category": "onboarding",
    "issue_types": ["onboarding", "new hire", "new employee", "provisioning"],
    "tags": ["onboarding", "provisioning", "new_hire", "accounts"],
    "estimated_time": "45 minutes",
    "steps": [
        {
            "step_number": 1,
            "title": "Create core accounts",
            "description": "Provision email, SSO/Okta, and primary collaboration apps (Teams/Slack).",
            "estimated_minutes": 10,
        },
        {
            "step_number": 2,
            "title": "Assign licenses and groups",
            "description": "Add role-based groups, shared mailboxes, and required SaaS licenses.",
            "estimated_minutes": 10,
        },
        {
            "step_number": 3,
            "title": "Configure VPN and MFA",
            "description": "Enroll MFA, confirm VPN profile, and verify first login from a managed device.",
            "estimated_minutes": 10,
        },
        {
            "step_number": 4,
            "title": "Prepare hardware",
            "description": "Image laptop, install standard software bundle, and confirm peripherals.",
            "estimated_minutes": 10,
        },
        {
            "step_number": 5,
            "title": "Day-one verification",
            "description": "Walk through email, VPN, MFA, and ticket submission with the new hire.",
            "estimated_minutes": 5,
        },
    ],
}

ONBOARDING_AUTOMATION_RULE = {
    "id": "onboarding-auto-start",
    "name": "Auto-start onboarding workflow",
    "description": "When a ticket is created with category onboarding, start the Employee onboarding playbook.",
    "trigger": "ticket.created",
    "condition": {"ticket_field": "category", "equals": "onboarding"},
    "action": "start_workflow",
    "template_trigger_category": "onboarding",
    "status": "active",
    "implemented_via": "automation.engine (seed_automation_rules)",
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
        "title": "Verify Okta SSO account",
        "description": "Automatically confirms the new hire exists in your connected Okta org.",
        "assignee_team": "IT Support",
        "assignee_role": "it",
        "step_type": "auto_check",
        "due_days": 1,
        "auto_check": {
            "connector": "okta",
            "check": "user_exists",
            "email_from": "ticket_reporter",
        },
    },
    {
        "title": "Verify Google Workspace account",
        "description": "Automatically confirms the new hire has a Google Workspace user.",
        "assignee_team": "IT Support",
        "assignee_role": "it",
        "step_type": "auto_check",
        "due_days": 1,
        "auto_check": {
            "connector": "google_workspace",
            "check": "user_exists",
            "email_from": "ticket_reporter",
        },
    },
    {
        "title": "Verify Microsoft 365 account",
        "description": "Automatically confirms the new hire exists in Microsoft 365.",
        "assignee_team": "IT Support",
        "assignee_role": "it",
        "step_type": "auto_check",
        "due_days": 1,
        "auto_check": {
            "connector": "microsoft365",
            "check": "user_exists",
            "email_from": "ticket_reporter",
        },
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
