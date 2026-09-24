import os
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.communication import Communication, COMMUNICATION_TYPES, COMMUNICATION_STATUSES, APPROVAL_STATUSES
from app.models.event import CooperativeDay
from app.models.team import Team
from app.models.user import User
from app.communication.forms import CommunicationForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action
from app.utils.files import allowed_file, safe_stored_filename, upload_path

communication_bp = Blueprint("communication", __name__)


@communication_bp.route("/")
@login_required
@permission_required("view_communication")
def communication_list():
    event_id = request.args.get("event_id", type=int)
    communication_type = request.args.get("communication_type", "")
    status = request.args.get("status", "")
    approval_status = request.args.get("approval_status", "")

    query = Communication.query
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if communication_type:
        query = query.filter_by(communication_type=communication_type)
    if status:
        query = query.filter_by(status=status)
    if approval_status:
        query = query.filter_by(approval_status=approval_status)

    items = query.order_by(Communication.created_at.desc()).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()

    return render_template(
        "communication/list.html", items=items, events=events,
        communication_types=COMMUNICATION_TYPES, statuses=COMMUNICATION_STATUSES, approval_statuses=APPROVAL_STATUSES,
        selected_event_id=event_id, selected_type=communication_type,
        selected_status=status, selected_approval_status=approval_status,
    )


@communication_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_communication")
def communication_new():
    form = CommunicationForm()
    _populate_choices(form)
    if form.validate_on_submit():
        item = Communication(
            title=form.title.data,
            communication_type=form.communication_type.data,
            cooperative_day_id=form.cooperative_day_id.data,
            team_id=form.team_id.data or None,
            responsible_user_id=form.responsible_user_id.data or None,
            description=form.description.data,
            target_audience=form.target_audience.data,
            platform=form.platform.data,
            planned_date=form.planned_date.data,
            publication_date=form.publication_date.data,
            status=form.status.data,
            created_by_id=current_user.id,
        )
        upload = form.file.data
        if upload and upload.filename:
            if not allowed_file(upload.filename):
                flash("That file type is not allowed.", "danger")
                return render_template("communication/form.html", form=form, is_new=True)
            _save_attachment(item, upload)

        db.session.add(item)
        db.session.flush()
        log_action("create", "Communication", item.id, f"Created communication item '{item.title}'")
        db.session.commit()
        flash(f"'{item.title}' created.", "success")
        return redirect(url_for("communication.communication_detail", item_id=item.id))
    return render_template("communication/form.html", form=form, is_new=True)


@communication_bp.route("/<int:item_id>")
@login_required
@permission_required("view_communication")
def communication_detail(item_id):
    item = Communication.query.get_or_404(item_id)
    return render_template("communication/detail.html", item=item)


@communication_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_communication")
def communication_edit(item_id):
    item = Communication.query.get_or_404(item_id)
    form = CommunicationForm(obj=item)
    _populate_choices(form)
    if request.method == "GET":
        form.team_id.data = item.team_id or 0
        form.responsible_user_id.data = item.responsible_user_id or 0

    if form.validate_on_submit():
        item.title = form.title.data
        item.communication_type = form.communication_type.data
        item.cooperative_day_id = form.cooperative_day_id.data
        item.team_id = form.team_id.data or None
        item.responsible_user_id = form.responsible_user_id.data or None
        item.description = form.description.data
        item.target_audience = form.target_audience.data
        item.platform = form.platform.data
        item.planned_date = form.planned_date.data
        item.publication_date = form.publication_date.data
        item.status = form.status.data

        upload = form.file.data
        if upload and upload.filename:
            if not allowed_file(upload.filename):
                flash("That file type is not allowed.", "danger")
                return render_template("communication/form.html", form=form, is_new=False, item=item)
            _save_attachment(item, upload)

        log_action("update", "Communication", item.id, f"Updated communication item '{item.title}'")
        db.session.commit()
        flash("Communication item updated.", "success")
        return redirect(url_for("communication.communication_detail", item_id=item.id))
    return render_template("communication/form.html", form=form, is_new=False, item=item)


@communication_bp.route("/<int:item_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("manage_communication")
def communication_status(item_id, new_status):
    item = Communication.query.get_or_404(item_id)
    if new_status not in COMMUNICATION_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("communication.communication_detail", item_id=item.id))
    item.status = new_status
    log_action("update", "Communication", item.id, f"Status changed to {new_status}")
    db.session.commit()
    flash(f"Status set to {new_status}.", "success")
    return redirect(url_for("communication.communication_detail", item_id=item.id))


@communication_bp.route("/<int:item_id>/approval/<string:decision>", methods=["POST"])
@login_required
@permission_required("approve_communication")
def communication_approve(item_id, decision):
    item = Communication.query.get_or_404(item_id)
    if decision not in ("Approved", "Rejected"):
        flash("Invalid decision.", "danger")
        return redirect(url_for("communication.communication_detail", item_id=item.id))
    item.approval_status = decision
    item.approved_by_id = current_user.id
    item.approved_at = datetime.utcnow()
    log_action("update", "Communication", item.id, f"Approval decision: {decision}")
    db.session.commit()
    flash(f"Communication item {decision.lower()}.", "success")
    return redirect(url_for("communication.communication_detail", item_id=item.id))


@communication_bp.route("/<int:item_id>/download")
@login_required
@permission_required("view_communication")
def communication_download(item_id):
    item = Communication.query.get_or_404(item_id)
    if not item.stored_filename:
        abort(404)

    folder = upload_path("communication", str(item.cooperative_day_id))
    file_on_disk = os.path.join(folder, item.stored_filename)
    if not os.path.isfile(file_on_disk):
        abort(404)

    log_action("download", "Communication", item.id, f"Downloaded attachment for '{item.title}'")
    db.session.commit()

    # Served by stored_filename (a random UUID token), never the original
    # name or a predictable path — see app/utils/files.py.
    return send_from_directory(folder, item.stored_filename, as_attachment=True, download_name=item.original_filename)


def _save_attachment(item, upload_storage):
    folder = upload_path("communication", str(item.cooperative_day_id))
    os.makedirs(folder, exist_ok=True)

    stored_name = safe_stored_filename(upload_storage.filename)
    upload_storage.save(os.path.join(folder, stored_name))

    size = None
    try:
        size = os.path.getsize(os.path.join(folder, stored_name))
    except OSError:
        pass

    item.original_filename = upload_storage.filename
    item.stored_filename = stored_name
    item.file_size = size
    item.mime_type = upload_storage.mimetype


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.team_id.choices = [(0, "— None —")] + [(t.id, t.name) for t in Team.query.order_by(Team.name)]
    form.responsible_user_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
