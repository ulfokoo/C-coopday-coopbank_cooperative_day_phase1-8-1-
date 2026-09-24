from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required

from app.extensions import db
from app.models.event import CooperativeDay
from app.models.user import User
from app.models.team import Team
from app.models.task import Task
from app.models.activity import Activity
from app.models.communication import Communication
from app.models.document import Document
from app.events.forms import CooperativeDayForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action

events_bp = Blueprint("events", __name__)


@events_bp.route("/")
@login_required
@permission_required("view_event")
def events_list():
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template("events/list.html", events=events)


@events_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("create_event")
def event_new():
    form = CooperativeDayForm()
    _populate_coordinator_choices(form)
    if form.validate_on_submit():
        if CooperativeDay.query.filter_by(year=form.year.data).first():
            flash(f"A Cooperative Day for {form.year.data} already exists.", "danger")
            return render_template("events/form.html", form=form, is_new=True)

        event = CooperativeDay(
            year=form.year.data,
            name=form.name.data,
            theme=form.theme.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            location=form.location.data,
            description=form.description.data,
            status=form.status.data,
            coordinator_id=form.coordinator_id.data or None,
        )
        db.session.add(event)
        db.session.flush()
        log_action("create", "CooperativeDay", event.id, f"Created {event.name}")
        db.session.commit()
        flash(f"'{event.name}' created. Previous years remain fully accessible.", "success")
        return redirect(url_for("events.event_detail", event_id=event.id))
    return render_template("events/form.html", form=form, is_new=True)


@events_bp.route("/<int:event_id>")
@login_required
@permission_required("view_event")
def event_detail(event_id):
    event = CooperativeDay.query.get_or_404(event_id)
    teams = event.teams.order_by(Team.name).all()

    # Event-management overview: a single hub summarising everything that
    # hangs off this Cooperative Day year, per spec section 3/28.
    upcoming_activities = (
        event.activities.filter(Activity.status.notin_(["Completed", "Cancelled"]))
        .order_by(Activity.activity_date.is_(None), Activity.activity_date.asc())
        .limit(5)
        .all()
    )
    stats = {
        "team_count": len(teams),
        "task_count": Task.query.filter_by(cooperative_day_id=event.id).count(),
        "task_completed": Task.query.filter_by(cooperative_day_id=event.id, status="Completed").count(),
        "activity_count": event.activities.count(),
        "activity_completed": event.activities.filter_by(status="Completed").count(),
        "communication_count": event.communications.count(),
        "communication_published": event.communications.filter_by(status="Published").count(),
        "document_count": Document.query.filter_by(cooperative_day_id=event.id).count(),
    }
    return render_template(
        "events/detail.html", event=event, teams=teams, stats=stats, upcoming_activities=upcoming_activities
    )


@events_bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("edit_event")
def event_edit(event_id):
    event = CooperativeDay.query.get_or_404(event_id)
    form = CooperativeDayForm(obj=event)
    _populate_coordinator_choices(form)
    if request.method == "GET":
        form.coordinator_id.data = event.coordinator_id or 0

    if form.validate_on_submit():
        existing = CooperativeDay.query.filter(
            CooperativeDay.year == form.year.data, CooperativeDay.id != event.id
        ).first()
        if existing:
            flash(f"Another Cooperative Day already uses year {form.year.data}.", "danger")
            return render_template("events/form.html", form=form, is_new=False, event=event)

        event.year = form.year.data
        event.name = form.name.data
        event.theme = form.theme.data
        event.start_date = form.start_date.data
        event.end_date = form.end_date.data
        event.location = form.location.data
        event.description = form.description.data
        event.status = form.status.data
        event.coordinator_id = form.coordinator_id.data or None

        log_action("update", "CooperativeDay", event.id, f"Updated {event.name}")
        db.session.commit()
        flash(f"'{event.name}' updated.", "success")
        return redirect(url_for("events.event_detail", event_id=event.id))
    return render_template("events/form.html", form=form, is_new=False, event=event)


@events_bp.route("/<int:event_id>/archive", methods=["POST"])
@login_required
@permission_required("delete_event")
def event_archive(event_id):
    # Historical Cooperative Day records are never hard-deleted — only
    # marked Cancelled/archived — so past years stay permanently accessible.
    event = CooperativeDay.query.get_or_404(event_id)
    event.status = "Cancelled"
    log_action("archive", "CooperativeDay", event.id, f"Archived {event.name}")
    db.session.commit()
    flash(f"'{event.name}' marked as Cancelled (record preserved).", "info")
    return redirect(url_for("events.events_list"))


def _populate_coordinator_choices(form):
    form.coordinator_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
