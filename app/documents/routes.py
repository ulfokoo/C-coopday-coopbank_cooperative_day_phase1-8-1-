import os

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.document import Document, DocumentVersion, DOCUMENT_TYPES, DOCUMENT_STATUSES
from app.models.event import CooperativeDay
from app.models.department import Department
from app.models.team import Team
from app.models.task import Task
from app.models.meeting import Meeting
from app.models.instruction import Instruction
from app.models.correspondence import Correspondence
from app.models.procurement import ProcurementRequest
from app.models.user import User
from app.documents.forms import DocumentUploadForm, DocumentMetadataForm, DocumentVersionForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action
from app.utils.files import allowed_file, safe_stored_filename, upload_path
from app.utils.notifications import notify_users_with_permission
from app.utils.team_scope import restrict_query, can_access, team_choices

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/")
@login_required
@permission_required("view_documents")
def documents_list():
    event_id = request.args.get("event_id", type=int)
    document_type = request.args.get("document_type", "")
    department_id = request.args.get("department_id", type=int)
    team_id = request.args.get("team_id", type=int)
    status = request.args.get("status", "")
    keyword = request.args.get("q", "").strip()

    query = restrict_query(Document.query, Document)
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if document_type:
        query = query.filter_by(document_type=document_type)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if team_id:
        query = query.filter_by(team_id=team_id)
    if status:
        query = query.filter_by(status=status)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            db.or_(Document.title.ilike(like), Document.description.ilike(like), Document.tags.ilike(like))
        )

    documents = query.order_by(Document.created_at.desc()).all()

    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    teams = Team.query.order_by(Team.name).all()

    return render_template(
        "documents/list.html", documents=documents, events=events, departments=departments, teams=teams,
        document_types=DOCUMENT_TYPES, statuses=DOCUMENT_STATUSES,
        selected_event_id=event_id, selected_document_type=document_type,
        selected_department_id=department_id, selected_team_id=team_id, selected_status=status, keyword=keyword,
    )


@documents_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("upload_documents")
def document_new():
    form = DocumentUploadForm()
    _populate_choices(form)
    if request.method == "GET" and request.args.get("team_id", type=int):
        form.team_id.data = request.args.get("team_id", type=int)
    if form.validate_on_submit():
        upload = form.file.data
        if not allowed_file(upload.filename):
            flash("That file type is not allowed.", "danger")
            return render_template("documents/form.html", form=form, is_new=True)

        doc = Document(
            title=form.title.data,
            document_type=form.document_type.data,
            cooperative_day_id=form.cooperative_day_id.data,
            department_id=form.department_id.data or None,
            team_id=form.team_id.data or None,
            task_id=form.task_id.data or None,
            meeting_id=form.meeting_id.data or None,
            instruction_id=form.instruction_id.data or None,
            correspondence_id=form.correspondence_id.data or None,
            procurement_request_id=form.procurement_request_id.data or None,
            owner_id=form.owner_id.data or current_user.id,
            uploaded_by_id=current_user.id,
            confidentiality_level=form.confidentiality_level.data,
            description=form.description.data,
            tags=form.tags.data,
            status="Submitted",
        )
        db.session.add(doc)
        db.session.flush()

        _save_version(doc, upload, "v1", 1, form.version_notes.data)

        log_action("create", "Document", doc.id, f"Uploaded document '{doc.title}' (v1)")
        notify_users_with_permission(
            "approve_documents", f"Document needs approval: {doc.title}",
            f"'{doc.title}' ({doc.document_type}) was submitted and is awaiting review.",
            category="Document", link=f"/documents/{doc.id}",
            entity_type="Document", entity_id=doc.id, exclude_user_id=current_user.id,
        )
        db.session.commit()
        flash(f"Document '{doc.title}' uploaded.", "success")
        return redirect(url_for("documents.document_detail", document_id=doc.id))
    return render_template("documents/form.html", form=form, is_new=True)


@documents_bp.route("/<int:document_id>")
@login_required
@permission_required("view_documents")
def document_detail(document_id):
    doc = Document.query.get_or_404(document_id)
    if not can_access(doc):
        abort(403)
    version_form = DocumentVersionForm()
    versions = doc.versions.order_by(DocumentVersion.version_number.desc()).all()
    return render_template("documents/detail.html", document=doc, versions=versions, version_form=version_form)


@documents_bp.route("/<int:document_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("upload_documents")
def document_edit(document_id):
    doc = Document.query.get_or_404(document_id)
    if not can_access(doc):
        abort(403)
    form = DocumentMetadataForm(obj=doc)
    _populate_choices(form)
    if request.method == "GET":
        form.department_id.data = doc.department_id or 0
        form.team_id.data = doc.team_id or 0
        form.task_id.data = doc.task_id or 0
        form.meeting_id.data = doc.meeting_id or 0
        form.instruction_id.data = doc.instruction_id or 0
        form.correspondence_id.data = doc.correspondence_id or 0
        form.procurement_request_id.data = doc.procurement_request_id or 0
        form.owner_id.data = doc.owner_id or 0

    if form.validate_on_submit():
        doc.title = form.title.data
        doc.document_type = form.document_type.data
        doc.cooperative_day_id = form.cooperative_day_id.data
        doc.department_id = form.department_id.data or None
        doc.team_id = form.team_id.data or None
        doc.task_id = form.task_id.data or None
        doc.meeting_id = form.meeting_id.data or None
        doc.instruction_id = form.instruction_id.data or None
        doc.correspondence_id = form.correspondence_id.data or None
        doc.procurement_request_id = form.procurement_request_id.data or None
        doc.owner_id = form.owner_id.data or None
        doc.confidentiality_level = form.confidentiality_level.data
        doc.description = form.description.data
        doc.tags = form.tags.data
        log_action("update", "Document", doc.id, f"Updated metadata for '{doc.title}'")
        db.session.commit()
        flash("Document updated.", "success")
        return redirect(url_for("documents.document_detail", document_id=doc.id))
    return render_template("documents/form_edit.html", form=form, document=doc)


@documents_bp.route("/<int:document_id>/versions/new", methods=["POST"])
@login_required
@permission_required("upload_documents")
def document_version_new(document_id):
    doc = Document.query.get_or_404(document_id)
    if not can_access(doc):
        abort(403)
    form = DocumentVersionForm()
    if form.validate_on_submit():
        upload = form.file.data
        if not allowed_file(upload.filename):
            flash("That file type is not allowed.", "danger")
            return redirect(url_for("documents.document_detail", document_id=doc.id))

        next_number = (doc.versions.count() or 0) + 1
        label = form.version_label.data.strip() or f"v{next_number}"
        if DocumentVersion.query.filter_by(document_id=doc.id, version_label=label).first():
            flash(f"Version label '{label}' already exists for this document.", "danger")
            return redirect(url_for("documents.document_detail", document_id=doc.id))

        _save_version(doc, upload, label, next_number, form.notes.data)
        doc.status = "Submitted"
        log_action("create", "DocumentVersion", doc.id, f"Uploaded new version '{label}' of '{doc.title}'")
        db.session.commit()
        flash(f"New version '{label}' uploaded.", "success")
    else:
        flash("Could not upload the new version — check the file and try again.", "danger")
    return redirect(url_for("documents.document_detail", document_id=doc.id))


@documents_bp.route("/<int:document_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("approve_documents")
def document_status(document_id, new_status):
    doc = Document.query.get_or_404(document_id)
    if new_status not in DOCUMENT_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("documents.document_detail", document_id=doc.id))
    doc.status = new_status
    log_action("update", "Document", doc.id, f"Status changed to {new_status}")
    db.session.commit()
    flash(f"Document status set to {new_status}.", "success")
    return redirect(url_for("documents.document_detail", document_id=doc.id))


@documents_bp.route("/versions/<int:version_id>/download")
@login_required
@permission_required("download_documents")
def version_download(version_id):
    version = DocumentVersion.query.get_or_404(version_id)
    doc = version.document
    if not can_access(doc):
        abort(403)

    folder = upload_path("documents", str(doc.cooperative_day_id))
    file_on_disk = os.path.join(folder, version.stored_filename)
    if not os.path.isfile(file_on_disk):
        abort(404)

    version.download_count = (version.download_count or 0) + 1
    log_action(
        "download", "DocumentVersion", version.id,
        f"Downloaded '{doc.title}' ({version.version_label}) as '{version.original_filename}'",
    )
    db.session.commit()

    # Served by stored_filename (a random UUID token), never the original
    # name or a predictable path — see app/utils/files.py.
    return send_from_directory(
        folder, version.stored_filename, as_attachment=True, download_name=version.original_filename
    )


def _save_version(doc, upload_storage, label, number, notes):
    folder = upload_path("documents", str(doc.cooperative_day_id))
    os.makedirs(folder, exist_ok=True)

    stored_name = safe_stored_filename(upload_storage.filename)
    upload_storage.save(os.path.join(folder, stored_name))

    size = None
    try:
        size = os.path.getsize(os.path.join(folder, stored_name))
    except OSError:
        pass

    version = DocumentVersion(
        document_id=doc.id,
        version_number=number,
        version_label=label,
        original_filename=upload_storage.filename,
        stored_filename=stored_name,
        file_size=size,
        mime_type=upload_storage.mimetype,
        notes=notes,
        uploaded_by_id=current_user.id,
    )
    db.session.add(version)
    return version


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.department_id.choices = [(0, "— None —")] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).order_by(Department.name)
    ]
    form.team_id.choices = team_choices()
    form.task_id.choices = [(0, "— None —")] + [(t.id, t.title) for t in Task.query.order_by(Task.title)]
    form.meeting_id.choices = [(0, "— None —")] + [(m.id, m.title) for m in Meeting.query.order_by(Meeting.title)]
    form.instruction_id.choices = [(0, "— None —")] + [
        (i.id, i.title) for i in Instruction.query.order_by(Instruction.title)
    ]
    form.correspondence_id.choices = [(0, "— None —")] + [
        (c.id, c.reference_number) for c in Correspondence.query.order_by(Correspondence.reference_number)
    ]
    form.procurement_request_id.choices = [(0, "— None —")] + [
        (p.id, p.request_number) for p in ProcurementRequest.query.order_by(ProcurementRequest.request_number)
    ]
    form.owner_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]