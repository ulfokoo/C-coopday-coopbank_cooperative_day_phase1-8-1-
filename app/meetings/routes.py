from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.meeting import Meeting, MeetingParticipant, ActionPoint, ACTION_POINT_STATUSES
from app.models.event import CooperativeDay
from app.models.team import Team
from app.models.user import User
from app.models.task import Task
from app.meetings.forms import MeetingForm, MinutesForm, ParticipantForm, ActionPointForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action
from app.utils.notifications import notify

meetings_bp = Blueprint("meetings", __name__)


@meetings_bp.route("/")
@login_required
@permission_required("manage_meetings")
def meetings_list():
    event_id = request.args.get("event_id", type=int)
    query = Meeting.query
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    meetings = query.order_by(Meeting.meeting_date.desc()).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template("meetings/list.html", meetings=meetings, events=events, selected_event_id=event_id)


@meetings_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_meetings")
def meeting_new():
    form = MeetingForm()
    _populate_choices(form)
    if form.validate_on_submit():
        meeting = Meeting(
            title=form.title.data,
            cooperative_day_id=form.cooperative_day_id.data,
            meeting_date=form.meeting_date.data,
            meeting_time=form.meeting_time.data,
            location=form.location.data,
            organizer_id=form.organizer_id.data or None,
            team_id=form.team_id.data or None,
            agenda=form.agenda.data,
            created_by_id=current_user.id,
        )
        db.session.add(meeting)
        db.session.flush()
        log_action("create", "Meeting", meeting.id, f"Scheduled meeting '{meeting.title}'")
        db.session.commit()
        flash(f"Meeting '{meeting.title}' scheduled.", "success")
        return redirect(url_for("meetings.meeting_detail", meeting_id=meeting.id))
    return render_template("meetings/form.html", form=form, is_new=True)


@meetings_bp.route("/<int:meeting_id>")
@login_required
@permission_required("manage_meetings")
def meeting_detail(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    minutes_form = MinutesForm(obj=meeting)
    participant_form = ParticipantForm()
    _populate_participant_choices(participant_form, meeting)
    action_form = ActionPointForm()
    action_form.responsible_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
    return render_template(
        "meetings/detail.html", meeting=meeting, minutes_form=minutes_form,
        participant_form=participant_form, action_form=action_form,
    )


@meetings_bp.route("/<int:meeting_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_meetings")
def meeting_edit(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    form = MeetingForm(obj=meeting)
    _populate_choices(form)
    if request.method == "GET":
        form.organizer_id.data = meeting.organizer_id or 0
        form.team_id.data = meeting.team_id or 0

    if form.validate_on_submit():
        meeting.title = form.title.data
        meeting.cooperative_day_id = form.cooperative_day_id.data
        meeting.meeting_date = form.meeting_date.data
        meeting.meeting_time = form.meeting_time.data
        meeting.location = form.location.data
        meeting.organizer_id = form.organizer_id.data or None
        meeting.team_id = form.team_id.data or None
        meeting.agenda = form.agenda.data
        log_action("update", "Meeting", meeting.id, f"Updated meeting '{meeting.title}'")
        db.session.commit()
        flash(f"Meeting '{meeting.title}' updated.", "success")
        return redirect(url_for("meetings.meeting_detail", meeting_id=meeting.id))
    return render_template("meetings/form.html", form=form, is_new=False, meeting=meeting)


@meetings_bp.route("/<int:meeting_id>/minutes", methods=["POST"])
@login_required
@permission_required("manage_meetings")
def meeting_minutes_save(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    form = MinutesForm()
    if form.validate_on_submit():
        meeting.minutes = form.minutes.data
        log_action("update", "Meeting", meeting.id, "Saved minutes")
        db.session.commit()
        flash("Minutes saved.", "success")
    return redirect(url_for("meetings.meeting_detail", meeting_id=meeting.id))


@meetings_bp.route("/<int:meeting_id>/participants/add", methods=["POST"])
@login_required
@permission_required("manage_meetings")
def participant_add(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    form = ParticipantForm()
    _populate_participant_choices(form, meeting)
    if form.validate_on_submit():
        exists = MeetingParticipant.query.filter_by(meeting_id=meeting.id, user_id=form.user_id.data).first()
        if exists:
            flash("That person is already listed as a participant.", "warning")
        else:
            p = MeetingParticipant(meeting_id=meeting.id, user_id=form.user_id.data)
            db.session.add(p)
            db.session.commit()
            flash("Participant added.", "success")
    return redirect(url_for("meetings.meeting_detail", meeting_id=meeting.id))


@meetings_bp.route("/<int:meeting_id>/participants/<int:participant_id>/toggle", methods=["POST"])
@login_required
@permission_required("manage_meetings")
def participant_toggle_attended(meeting_id, participant_id):
    p = MeetingParticipant.query.filter_by(id=participant_id, meeting_id=meeting_id).first_or_404()
    p.attended = not p.attended
    db.session.commit()
    return redirect(url_for("meetings.meeting_detail", meeting_id=meeting_id))


@meetings_bp.route("/<int:meeting_id>/action-points/add", methods=["POST"])
@login_required
@permission_required("manage_meetings")
def action_point_add(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    form = ActionPointForm()
    form.responsible_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
    if form.validate_on_submit():
        ap = ActionPoint(
            meeting_id=meeting.id,
            description=form.description.data,
            responsible_user_id=form.responsible_user_id.data or None,
            due_date=form.due_date.data,
        )
        db.session.add(ap)
        db.session.flush()
        log_action("create", "ActionPoint", ap.id, f"Added action point to meeting {meeting.id}")
        if ap.responsible_user_id and ap.responsible_user_id != current_user.id:
            notify(
                ap.responsible_user_id, f"Action point assigned: {meeting.title}",
                ap.description + (f" Due {ap.due_date.isoformat()}." if ap.due_date else ""),
                category="Meeting", link=f"/meetings/{meeting.id}",
                entity_type="ActionPoint", entity_id=ap.id,
            )
        db.session.commit()
        flash("Action point added.", "success")
    else:
        flash("Could not add action point.", "danger")
    return redirect(url_for("meetings.meeting_detail", meeting_id=meeting.id))


@meetings_bp.route("/action-points/<int:action_point_id>/promote", methods=["POST"])
@login_required
@permission_required("manage_tasks")
def action_point_promote(action_point_id):
    """Turn a meeting action point into a real, trackable Task — the
    spec requires action points to be 'automatically capable of becoming
    tasks' without losing the link back to the meeting they came from."""
    ap = ActionPoint.query.get_or_404(action_point_id)
    if ap.task_id:
        flash("This action point is already linked to a task.", "warning")
        return redirect(url_for("meetings.meeting_detail", meeting_id=ap.meeting_id))

    meeting = ap.meeting
    task = Task(
        title=ap.description[:200],
        description=f"Action point from meeting '{meeting.title}' ({meeting.meeting_date}).",
        cooperative_day_id=meeting.cooperative_day_id,
        team_id=meeting.team_id,
        assigned_user_id=ap.responsible_user_id,
        due_date=ap.due_date,
        status="Not Started",
        created_by_id=current_user.id,
    )
    db.session.add(task)
    db.session.flush()
    ap.task_id = task.id
    log_action("create", "Task", task.id, f"Promoted from action point {ap.id} (meeting {meeting.id})")
    db.session.commit()
    flash("Action point promoted to a task.", "success")
    return redirect(url_for("meetings.meeting_detail", meeting_id=meeting.id))


@meetings_bp.route("/action-points/<int:action_point_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("manage_meetings")
def action_point_status(action_point_id, new_status):
    ap = ActionPoint.query.get_or_404(action_point_id)
    if new_status not in ACTION_POINT_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("meetings.meeting_detail", meeting_id=ap.meeting_id))
    ap.status = new_status
    db.session.commit()
    return redirect(url_for("meetings.meeting_detail", meeting_id=ap.meeting_id))


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.organizer_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
    form.team_id.choices = [(0, "— None —")] + [(t.id, t.name) for t in Team.query.order_by(Team.name)]


def _populate_participant_choices(form, meeting):
    existing_ids = [p.user_id for p in meeting.participants]
    form.user_id.choices = [
        (u.id, u.full_name)
        for u in User.query.filter_by(status="Active").order_by(User.full_name)
        if u.id not in existing_ids
    ]
