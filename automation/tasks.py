from celery import shared_task


@shared_task(name="automation.tasks.run_due_cron_rules_task")
def run_due_cron_rules_task():
    from automation.engine import run_due_cron_rules

    run_due_cron_rules()
