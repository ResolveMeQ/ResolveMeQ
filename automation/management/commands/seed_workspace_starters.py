"""
Seed editable workspace automation rules for teams that have none.

Usage:
  python manage.py seed_workspace_starters
  python manage.py seed_workspace_starters --team-id <uuid>
"""
from django.core.management.base import BaseCommand

from automation.workspace_starter import seed_starter_rules_for_team
from base.models import Team


class Command(BaseCommand):
    help = "Install editable starter automation rules on workspaces that have no rules yet"

    def add_arguments(self, parser):
        parser.add_argument(
            "--team-id",
            type=str,
            default="",
            help="Only seed this team UUID (default: all teams missing rules)",
        )

    def handle(self, *args, **options):
        team_id = (options.get("team_id") or "").strip()
        if team_id:
            team = Team.objects.filter(pk=team_id).first()
            if not team:
                self.stderr.write(self.style.ERROR(f"Team not found: {team_id}"))
                return
            teams = [team]
        else:
            teams = Team.objects.all().order_by("name")

        total = 0
        for team in teams:
            n = seed_starter_rules_for_team(team)
            if n:
                total += n
                self.stdout.write(f"  {team.name}: {n} starter rule(s)")
        self.stdout.write(self.style.SUCCESS(f"Done. Created {total} workspace rule(s)."))
