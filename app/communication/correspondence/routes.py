from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.correspondence import Correspondence, CORRESPONDENCE_CATEGORIES, CORRESPONDENCE_STATUSES
from app.models.event import CooperativeDay
from app.models.department import Department
from app.models.team import Team
from app.models.user import User
from app.correspondence.forms import CorrespondenceForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action

correspondence_bp = Blueprint("correspondence", __name__)


@correspondence_bp.route("/")
@login_required
@permission_required("view_documents")
def correspondence_list():
    event_id = request.args.get("event_id", type=int)
    category = request.args.get("category", "")
    status = request.args.get("status", "")
    keyword = request.args.get("q", "").strip()

    query = Correspondence.query
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            db.or_(Correspondence.subject.ilike(like), Correspondence.reference_number.ilike(like))
        )

    records = query.order_by(Correspondence.created_at.desc()).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()

    return render_template(
        "correspondence/list.html", records=records, events=events,
        categories=CORRESPONDENCE_CATEGORIES, statuses=CORRESPONDENCE_STATUSES,
        selected_event_id=event_id, selected_category=category, selected_status=status, keyword=keyword,
        today=date.today(),
    )


@correspondence_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("upload_documents")
def correspondence_new():
    form = CorrespondenceForm()
    _populate_choices(form)
    if form.validate_on_submit():
        if Correspondence.query.filter_by(reference_number=form.reference_number.data).first():
            flash("That reference number is already in use.", "danger")
            return render_template("correspondence/form.html", form=form, is_new=True)

        record = Correspondence(
            reference_number=form.reference_number.data,
            category=form.category.data,
            subject=form.subject.data,
            from_party=form.from_party.data,
            to_party=form.to_party.data,
            cooperative_day_id=form.cooperative_day_id.data,
            department_id=form.department_id.data or None,
            team_id=form.team_id.data or None,
            date_received=form.date_received.data,
            date_sent=form.date_sent.data,
            responsible_user_id=form.responsible_user_id.data or None,
            priority=form.priority.data,
            status=form.status.data,
            response_deadline=form.response_deadline.data,
            notes=form.notes.data,
            created_by_id=current_user.id,
        )
        db.session.add(record)
        db.session.flush()
        log_action("create", "Correspondence", record.id, f"Logged correspondence {record.reference_number}")
        db.session.commit()
        flash(f"Correspondence '{record.reference_number}' logged.", "success")
        return redirect(url_for("correspondence.correspondence_detail", correspondence_id=record.id))
    return render_template("correspondence/form.html", form=form, is_new=True)


@correspondence_bp.route("/<int:correspondence_id>")
@login_required
@permission_required("view_documents")
def correspondence_detail(correspondence_id):
    record = Correspondence.query.get_or_404(correspondence_id)
    return render_template("correspondence/detail.html", record=record)


@correspondence_bp.route("/<int:correspondence_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("upload_documents")
def correspondence_edit(correspondence_id):
    record = Correspondence.query.get_or_404(correspondence_id)
    form = CorrespondenceForm(obj=record)
    _populate_choices(form)
    if request.method == "GET":
        form.department_id.data = record.department_id or 0
        form.team_id.data = record.team_id or 0
        form.responsible_user_id.data = record.responsible_user_id or 0

    if form.validate_on_submit():
        existing = Correspondence.query.filter(
            Correspondence.reference_number == form.reference_number.data, Correspondence.id != record.id
        ).first()
        if existing:
            flash("That reference number is already in use.", "danger")
            return render_template("correspondence/form.html", form=form, is_new=False, record=record)

        record.reference_number = form.reference_number.data
        record.category = form.category.data
        record.subject = form.subject.data
        record.from_party = form.from_party.data
        record.to_party = form.to_party.data
        record.cooperative_day_id = form.cooperative_day_id.data
        record.department_id = form.department_id.data or None
        record.team_id = form.team_id.data or None
        record.date_received = form.date_received.data
        record.date_sent = form.date_sent.data
        record.responsible_user_id = form.responsible_user_id.data or None
        record.priority = form.priority.data
        record.status = form.status.data
        record.response_deadline = form.response_deadline.data
        record.notes = form.notes.data
        log_action("update", "Correspondence", record.id, f"Updated correspondence {record.reference_number}")
        db.session.commit()
        flash("Correspondence updated.", "success")
        return redirect(url_for("correspondence.correspondence_detail", correspondence_id=record.id))
    return render_template("correspondence/form.html", form=form, is_new=False, record=record)


@correspondence_bp.route("/<int:correspondence_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("upload_documents")
def correspondence_status(correspondence_id, new_status):
    record = Correspondence.query.get_or_404(correspondence_id)
    if new_status not in CORRESPONDENCE_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("correspondence.correspondence_detail", correspondence_id=record.id))
    record.status = new_status
    log_action("update", "Correspondence", record.id, f"Status changed to {new_status}")
    db.session.commit()
    flash(f"Status set to {new_status}.", "success")
    return redirect(url_for("correspondence.correspondence_detail", correspondence_id=record.id))


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.department_id.choices = [(0, "— None —")] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).order_by(Department.name)
    ]
    form.team_id.choices = [(0, "— None —")] + [(t.id, t.name) for t in Team.query.order_by(Team.name)]
    form.responsible_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
