from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.team import Team, TeamMember
from app.models.document import Document
from app.models.event import CooperativeDay
from app.models.user import User
from app.teams.forms import TeamForm, TeamMemberForm, WindowForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action

teams_bp = Blueprint("teams", __name__)


def _is_team_manager(team):
    """Admin (manage_teams permission) OR the leader of this very team."""
    return current_user.has_permission("manage_teams") or team.leader_id == current_user.id


def _is_team_viewer(team):
    """Managers plus ordinary members of the team can open it."""
    if _is_team_manager(team):
        return True
    return TeamMember.query.filter_by(team_id=team.id, user_id=current_user.id).first() is not None


@teams_bp.route("/")
@login_required
def teams_list():
    event_id = request.args.get("event_id", type=int)
    query = Team.query
    # Admins see every team; everyone else sees only teams they lead or belong to.
    if not current_user.has_permission("manage_teams"):
        member_team_ids = db.session.query(TeamMember.team_id).filter_by(user_id=current_user.id)
        query = query.filter(
            db.or_(Team.leader_id == current_user.id, Team.id.in_(member_team_ids))
        )
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    teams = query.order_by(Team.cooperative_day_id.desc(), Team.name).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template("teams/list.html", teams=teams, events=events, selected_event_id=event_id)


@teams_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_teams")
def team_new():
    form = TeamForm()
    _populate_choices(form)
    if form.validate_on_submit():
        team = Team(
            name=form.name.data,
            description=form.description.data,
            cooperative_day_id=form.cooperative_day_id.data,
            leader_id=form.leader_id.data or None,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status=form.status.data,
        )
        db.session.add(team)
        db.session.flush()
        log_action("create", "Team", team.id, f"Created team {team.name}")
        db.session.commit()
        flash(f"Team '{team.name}' created.", "success")
        return redirect(url_for("teams.team_detail", team_id=team.id))
    return render_template("teams/form.html", form=form, is_new=True)


@teams_bp.route("/<int:team_id>")
@login_required
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_viewer(team):
        abort(403)
    member_form = TeamMemberForm()
    documents = Document.query.filter_by(team_id=team.id).order_by(Document.created_at.desc()).all()
    members = team.members.filter_by(parent_id=None).order_by(TeamMember.id).all()
    return render_template(
        "teams/detail.html",
        team=team,
        members=members,
        documents=documents,
        member_form=member_form,
        can_manage_members=_is_team_manager(team),
        can_edit_team=current_user.has_permission("manage_teams"),
    )


@teams_bp.route("/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_teams")
def team_edit(team_id):
    team = Team.query.get_or_404(team_id)
    form = TeamForm(obj=team)
    _populate_choices(form)
    if request.method == "GET":
        form.leader_id.data = team.leader_id or 0

    if form.validate_on_submit():
        team.name = form.name.data
        team.description = form.description.data
        team.cooperative_day_id = form.cooperative_day_id.data
        team.leader_id = form.leader_id.data or None
        team.start_date = form.start_date.data
        team.end_date = form.end_date.data
        team.status = form.status.data
        log_action("update", "Team", team.id, f"Updated team {team.name}")
        db.session.commit()
        flash(f"Team '{team.name}' updated.", "success")
        return redirect(url_for("teams.team_detail", team_id=team.id))
    return render_template("teams/form.html", form=form, is_new=False, team=team)


@teams_bp.route("/<int:team_id>/members/add", methods=["POST"])
@login_required
def team_member_add(team_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    form = TeamMemberForm()
    if form.validate_on_submit():
        existing = {(m.member_name or "").strip().lower() for m in team.members}
        added = 0
        for line in form.names.data.splitlines():
            name = line.strip()
            if not name or name.lower() in existing:
                continue
            db.session.add(TeamMember(team_id=team.id, member_name=name[:150], role_in_team="Member"))
            existing.add(name.lower())
            added += 1
        log_action("create", "TeamMember", team.id, f"Added {added} member(s) to team {team.name}")
        db.session.commit()
        flash(f"{added} member(s) added to the team.", "success")
    else:
        flash("Please write at least one name.", "danger")
    return redirect(url_for("teams.team_detail", team_id=team.id))


@teams_bp.route("/<int:team_id>/members/<int:member_id>/remove", methods=["POST"])
@login_required
def team_member_remove(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    log_action("delete", "TeamMember", member.id, f"Removed member {member.display_name} from team {team_id}")
    db.session.delete(member)
    db.session.commit()
    flash("Member removed from team.", "info")
    return redirect(url_for("teams.team_detail", team_id=team_id))

@teams_bp.route("/<int:team_id>/members/<int:member_id>/window", methods=["POST"])
@login_required
def team_member_window(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    member = TeamMember.query.filter_by(id=member_id, team_id=team_id).first_or_404()
    form = WindowForm()
    if form.validate_on_submit():
        member.window_label = (form.window_label.data or "").strip() or None
        log_action("update", "TeamMember", member.id, f"Set window for {member.display_name}")
        db.session.commit()
        flash("Window saved.", "success")
    return redirect(url_for("teams.team_detail", team_id=team_id))


@teams_bp.route("/<int:team_id>/members/<int:member_id>/staff/add", methods=["POST"])
@login_required
def team_staff_add(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    if not _is_team_manager(team):
        abort(403)
    leader = TeamMember.query.filter_by(id=member_id, team_id=team_id, parent_id=None).first_or_404()
    form = TeamMemberForm()
    if form.validate_on_submit():
        existing = {(m.member_name or "").strip().lower() for m in team.members}
        added = 0
        for line in form.names.data.splitlines():
            name = line.strip()
            if not name or name.lower() in existing:
                continue
            db.session.add(TeamMember(
                team_id=team.id, parent_id=leader.id,
                member_name=name[:150], role_in_team="Staff",
            ))
            existing.add(name.lower())
            added += 1
        log_action("create", "TeamMember", leader.id, f"Added {added} staff under {leader.display_name}")
        db.session.commit()
        flash(f"{added} staff added under {leader.display_name}.", "success")
    else:
        flash("Please write at least one name.", "danger")
    return redirect(url_for("teams.team_detail", team_id=team_id))

def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.leader_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]