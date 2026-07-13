"""Knowledge base article authoring permissions."""

from __future__ import annotations

from base.team_permissions import user_can_manage_playbooks
from tickets.scoping import active_team_id_for_user


def user_can_manage_kb_articles(user, team=None) -> bool:
    """
    Workspace owners and delegated admins with playbooks permission can author KB articles.
    Playbooks and runbooks are managed by the same IT ops role.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False):
        return True
    if team is None:
        tid = active_team_id_for_user(user)
        if not tid:
            return False
        from base.models import Team

        team = Team.objects.filter(pk=tid).first()
    if not team:
        return False
    if getattr(team, "owner_id", None) == user.id:
        return True
    return user_can_manage_playbooks(user, team)


def user_can_edit_kb_article(user, article) -> bool:
    if getattr(user, "is_staff", False):
        return True
    if article.team_id is None:
        return False
    if not user_can_manage_kb_articles(user, article.team):
        return False
    tid = active_team_id_for_user(user)
    return bool(tid and str(article.team_id) == str(tid))
