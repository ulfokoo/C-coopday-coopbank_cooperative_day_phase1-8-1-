from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.activity import Activity, ActivityParticipant, ACTIVITY_STATUSES
from app.models.event import CooperativeDay
from app.models.team import Team
from app.models.user import User
from app.activities.forms import ActivityForm, ActivityParticipantForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action
from app.utils.team_scope import restrict_query, can_access, team_choices

activities_bp = Blueprint("activities", __name__)


@activities_bp.route("/")
@login_required
@permission_required("view_activities")
def activities_list():
    event_id = request.args.get("event_id", type=int)
    team_id = request.args.get("team_id", type=int)
    status = request.args.get("status", "")

    query = restrict_query(Activity.query, Activity)
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if team_id:
        query = query.filter_by(team_id=team_id)
    if status:
        query = query.filter_by(status=status)

    # order_by(is_(None)) puts rows with a date (False==0) ahead of undated
    # ones (True==1) — portable across SQLite and PostgreSQL, unlike NULLS LAST.
    activities = query.order_by(Activity.activity_date.is_(None), Activity.activity_date.asc(), Activity.name).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    teams = Team.query.order_by(Team.name).all()

    return render_template(
        "activities/list.html", activities=activities, events=events, teams=teams,
        statuses=ACTIVITY_STATUSES, selected_event_id=event_id, selected_team_id=team_id, selected_status=status,
    )


@activities_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_activities")
def activity_new():
    form = ActivityForm()
    _populate_choices(form)
    if form.validate_on_submit():
        activity = Activity(
            name=form.name.data,
            activity_type=form.activity_type.data,
            cooperative_day_id=form.cooperative_day_id.data,
            team_id=form.team_id.data or None,
            responsible_user_id=form.responsible_user_id.data or None,
            activity_date=form.activity_date.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            location=form.location.data,
            description=form.description.data,
            requirements=form.requirements.data,
            budget_reference=form.budget_reference.data,
            status=form.status.data,
            created_by_id=current_user.id,
        )
        db.session.add(activity)
        db.session.flush()
        log_action("create", "Activity", activity.id, f"Scheduled activity '{activity.name}'")
        db.session.commit()
        flash(f"Activity '{activity.name}' created.", "success")
        return redirect(url_for("activities.activity_detail", activity_id=activity.id))
    return render_template("activities/form.html", form=form, is_new=True)


@activities_bp.route("/<int:activity_id>")
@login_required
@permission_required("view_activities")
def activity_detail(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    if not can_access(activity):
        abort(403)
    participant_form = ActivityParticipantForm()
    _populate_participant_choices(participant_form, activity)
    return render_template("activities/detail.html", activity=activity, participant_form=participant_form)


@activities_bp.route("/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_activities")
def activity_edit(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    if not can_access(activity):
        abort(403)
    form = ActivityForm(obj=activity)
    _populate_choices(form)
    if request.method == "GET":
        form.team_id.data = activity.team_id or 0
        form.responsible_user_id.data = activity.responsible_user_id or 0

    if form.validate_on_submit():
        activity.name = form.name.data
        activity.activity_type = form.activity_type.data
        activity.cooperative_day_id = form.cooperative_day_id.data
        activity.team_id = form.team_id.data or None
        activity.responsible_user_id = form.responsible_user_id.data or None
        activity.activity_date = form.activity_date.data
        activity.start_time = form.start_time.data
        activity.end_time = form.end_time.data
        activity.location = form.location.data
        activity.description = form.description.data
        activity.requirements = form.requirements.data
        activity.budget_reference = form.budget_reference.data
        activity.status = form.status.data
        log_action("update", "Activity", activity.id, f"Updated activity '{activity.name}'")
        db.session.commit()
        flash("Activity updated.", "success")
        return redirect(url_for("activities.activity_detail", activity_id=activity.id))
    return render_template("activities/form.html", form=form, is_new=False, activity=activity)


@activities_bp.route("/<int:activity_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("manage_activities")
def activity_status(activity_id, new_status):
    activity = Activity.query.get_or_404(activity_id)
    if not can_access(activity):
        abort(403)
    if new_status not in ACTIVITY_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("activities.activity_detail", activity_id=activity.id))
    activity.status = new_status
    log_action("update", "Activity", activity.id, f"Status changed to {new_status}")
    db.session.commit()
    flash(f"Activity status set to {new_status}.", "success")
    return redirect(url_for("activities.activity_detail", activity_id=activity.id))


@activities_bp.route("/<int:activity_id>/participants/add", methods=["POST"])
@login_required
@permission_required("manage_activities")
def participant_add(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    if not can_access(activity):
        abort(403)
    form = ActivityParticipantForm()
    _populate_participant_choices(form, activity)
    if form.validate_on_submit():
        exists = ActivityParticipant.query.filter_by(activity_id=activity.id, user_id=form.user_id.data).first()
        if exists:
            flash("That person is already listed as a participant.", "warning")
        else:
            p = ActivityParticipant(activity_id=activity.id, user_id=form.user_id.data)
            db.session.add(p)
            db.session.commit()
            flash("Participant added.", "success")
    return redirect(url_for("activities.activity_detail", activity_id=activity.id))


@activities_bp.route("/<int:activity_id>/participants/<int:participant_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_activities")
def participant_toggle_attended(activity_id, participant_id):
    p = ActivityParticipant.query.filter_by(id=participant_id, activity_id=activity_id).first_or_404()
    p.attended = not p.attended
    db.session.commit()
    return redirect(url_for("activities.activity_detail", activity_id=activity_id))


@activities_bp.route("/<int:activity_id>/participants/<int:participant_id>/remove", methods=["POST"])
@login_required
@permission_required("manage_activities")
def participant_remove(activity_id, participant_id):
    p = ActivityParticipant.query.filter_by(id=participant_id, activity_id=activity_id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    flash("Participant removed.", "info")
    return redirect(url_for("activities.activity_detail", activity_id=activity_id))


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.team_id.choices = team_choices()
    form.responsible_user_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]


def _populate_participant_choices(form, activity):
    existing_ids = [p.user_id for p in activity.participants]
    form.user_id.choices = [
        (u.id, u.full_name)
        for u in User.query.filter_by(status="Active").order_by(User.full_name)
        if u.id not in existing_ids
    ]
