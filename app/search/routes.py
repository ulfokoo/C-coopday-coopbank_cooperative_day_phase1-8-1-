from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.models.document import Document
from app.models.task import Task
from app.models.correspondence import Correspondence
from app.models.instruction import Instruction
from app.models.procurement import ProcurementRequest
from app.models.meeting import Meeting
from app.models.activity import Activity
from app.models.user import User
from app.models.team import Team

search_bp = Blueprint("search", __name__)

RESULTS_PER_SECTION = 15


@search_bp.route("/")
@login_required
def search_results():
    q = request.args.get("q", "", type=str).strip()
    results = {}

    if q:
        like = f"%{q}%"

        if current_user.has_permission("view_documents"):
            results["Documents"] = (
                Document.query.filter(
                    (Document.title.ilike(like)) | (Document.description.ilike(like)) | (Document.tags.ilike(like))
                ).order_by(Document.created_at.desc()).limit(RESULTS_PER_SECTION).all()
            )

        if current_user.has_permission("manage_tasks"):
            results["Tasks"] = (
                Task.query.filter(
                    (Task.title.ilike(like)) | (Task.description.ilike(like))
                ).order_by(Task.created_at.desc()).limit(RESULTS_PER_SECTION).all()
            )

        if current_user.has_permission("view_documents"):
            results["Correspondence"] = (
                Correspondence.query.filter(
                    (Correspondence.subject.ilike(like))
                    | (Correspondence.reference_number.ilike(like))
                    | (Correspondence.from_party.ilike(like))
                    | (Correspondence.to_party.ilike(like))
                ).order_by(Correspondence.created_at.desc()).limit(RESULTS_PER_SECTION).all()
            )

        if current_user.has_permission("manage_instructions"):
            results["Instructions"] = (
                Instruction.query.filter(
                    (Instruction.title.ilike(like)) | (Instruction.description.ilike(like))
                ).order_by(Instruction.created_at.desc()).limit(RESULTS_PER_SECTION).all()
            )

        if current_user.has_permission("view_procurement"):
            results["Procurement"] = (
                ProcurementRequest.query.filter(
                    (ProcurementRequest.item_service.ilike(like))
                    | (ProcurementRequest.request_number.ilike(like))
                    | (ProcurementRequest.description.ilike(like))
                ).order_by(ProcurementRequest.created_at.desc()).limit(RESULTS_PER_SECTION).all()
            )

        if current_user.has_permission("manage_meetings"):
            results["Meetings"] = (
                Meeting.query.filter(
                    (Meeting.title.ilike(like)) | (Meeting.agenda.ilike(like)) | (Meeting.minutes.ilike(like))
                ).order_by(Meeting.meeting_date.desc()).limit(RESULTS_PER_SECTION).all()
            )

        if current_user.has_permission("view_activities"):
            results["Activities"] = (
                Activity.query.filter(
                    (Activity.name.ilike(like)) | (Activity.description.ilike(like))
                ).order_by(Activity.created_at.desc()).limit(RESULTS_PER_SECTION).all()
            )

        if current_user.has_permission("manage_users"):
            results["Users"] = (
                User.query.filter(
                    (User.full_name.ilike(like)) | (User.username.ilike(like)) | (User.email.ilike(like))
                ).order_by(User.full_name).limit(RESULTS_PER_SECTION).all()
            )

        results["Teams"] = (
            Team.query.filter(
                (Team.name.ilike(like)) | (Team.description.ilike(like))
            ).order_by(Team.name).limit(RESULTS_PER_SECTION).all()
        )

        # drop empty sections so the template only shows what actually matched
        results = {k: v for k, v in results.items() if v}

    total_hits = sum(len(v) for v in results.values())
    return render_template("search/results.html", q=q, results=results, total_hits=total_hits)
