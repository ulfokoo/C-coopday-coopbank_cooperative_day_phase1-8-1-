"""Team-based visibility.

* VP / administrators (anyone with the 'manage_teams' permission) see everything.
* A Team Leader sees only the records of the team(s) they lead.
"""
from flask_login import current_user

from app.models.team import Team


def my_team_ids():
    """None  -> no restriction (VP / admin / everyone who is not a team leader).
    [ids] -> restricted to these team ids (may be empty)."""
    if current_user.has_permission("manage_teams"):
        return None
    ids = [t.id for t in Team.query.filter_by(leader_id=current_user.id).all()]
    if ids or current_user.has_role("TEAM LEADER"):
        return ids
    return None


def restrict_query(query, model):
    """Limit a query on a model that has a team_id column."""
    ids = my_team_ids()
    if ids is None:
        return query
    return query.filter(model.team_id.in_(ids)) if ids else query.filter(model.team_id == -1)


def can_access(obj):
    """True if the current user may open this record (it has a team_id)."""
    ids = my_team_ids()
    return ids is None or obj.team_id in ids


def team_choices():
    """Choices for a 'Team' dropdown. Leaders only get their own team(s)
    and cannot pick 'None'."""
    ids = my_team_ids()
    q = Team.query.order_by(Team.name)
    if ids is None:
        return [(0, "— None —")] + [(t.id, t.name) for t in q]
    return [(t.id, t.name) for t in q.filter(Team.id.in_(ids or [-1]))]