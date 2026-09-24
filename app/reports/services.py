"""Computes the quantitative content of a Cooperative Day Annual Report.

Kept as plain functions (not tied to Flask request/response) so the same
context dict can back the "view online" page, the PDF export and the
Excel export, and so the year-comparison dashboard can call it once per
year without duplicating any query logic.
"""
from app.models.team import Team, TeamMember
from app.models.task import Task, TASK_STATUSES
from app.models.document import Document, DOCUMENT_STATUSES
from app.models.correspondence import Correspondence
from app.models.instruction import Instruction, Decision, INSTRUCTION_STATUSES
from app.models.meeting import Meeting, ActionPoint
from app.models.procurement import ProcurementRequest, ProcurementItem, PROCUREMENT_STATUSES
from app.models.activity import Activity, ACTIVITY_STATUSES
from app.models.communication import Communication, COMMUNICATION_TYPES
from app.models.user import User


def _status_counts(query, column, statuses):
    return [{"status": s, "count": query.filter(column == s).count()} for s in statuses]


def build_report_context(event):
    """Return every computed figure the Annual Report page/PDF/Excel needs
    for one CooperativeDay `event`. Nothing here is stored — it is always
    freshly queried so the report reflects the live state of the records."""

    teams = Team.query.filter_by(cooperative_day_id=event.id).order_by(Team.name).all()
    team_ids = [t.id for t in teams]

    # --- staff participation: every distinct user touching this year ---
    staff_ids = set()
    if team_ids:
        for row in TeamMember.query.filter(TeamMember.team_id.in_(team_ids)).with_entities(TeamMember.user_id):
            if row[0]:
                staff_ids.add(row[0])
    for model, col in [
        (Task, "assigned_user_id"), (Instruction, "responsible_user_id"),
        (Activity, "responsible_user_id"), (Communication, "responsible_user_id"),
        (ProcurementRequest, "requested_by_id"), (Meeting, "organizer_id"),
    ]:
        q = model.query.filter_by(cooperative_day_id=event.id).with_entities(getattr(model, col))
        for row in q:
            if row[0]:
                staff_ids.add(row[0])
    staff = User.query.filter(User.id.in_(staff_ids)).order_by(User.full_name).all() if staff_ids else []

    # --- tasks ---
    task_q = Task.query.filter_by(cooperative_day_id=event.id)
    tasks_total = task_q.count()
    tasks_completed = task_q.filter(Task.status == "Completed").count()
    tasks_not_completed = tasks_total - tasks_completed
    tasks_overdue = sum(1 for t in task_q.all() if t.is_overdue)
    tasks_by_status = _status_counts(task_q, Task.status, TASK_STATUSES)

    # --- documents ---
    doc_q = Document.query.filter_by(cooperative_day_id=event.id)
    documents_total = doc_q.count()
    documents_by_status = _status_counts(doc_q, Document.status, DOCUMENT_STATUSES)

    # --- correspondence ---
    corr_q = Correspondence.query.filter_by(cooperative_day_id=event.id)
    correspondence_total = corr_q.count()
    correspondence_closed = corr_q.filter(Correspondence.status == "Closed").count()

    # --- instructions & decisions ---
    instr_q = Instruction.query.filter_by(cooperative_day_id=event.id)
    instructions_total = instr_q.count()
    instructions_completed = instr_q.filter(Instruction.status.in_(["Completed", "Closed"])).count()
    instructions_overdue = sum(1 for i in instr_q.all() if i.is_overdue)
    instructions_by_status = _status_counts(instr_q, Instruction.status, INSTRUCTION_STATUSES)
    decisions_total = Decision.query.filter_by(cooperative_day_id=event.id).count()

    # --- meetings & action points ---
    meeting_q = Meeting.query.filter_by(cooperative_day_id=event.id)
    meetings_total = meeting_q.count()
    meeting_ids = [m.id for m in meeting_q.all()]
    action_points_total = ActionPoint.query.filter(ActionPoint.meeting_id.in_(meeting_ids)).count() if meeting_ids else 0
    action_points_completed = (
        ActionPoint.query.filter(ActionPoint.meeting_id.in_(meeting_ids), ActionPoint.status == "Completed").count()
        if meeting_ids else 0
    )

    # --- procurement & purchases ---
    proc_q = ProcurementRequest.query.filter_by(cooperative_day_id=event.id)
    procurement_total = proc_q.count()
    procurement_completed = proc_q.filter(ProcurementRequest.status == "Completed").count()
    procurement_pending = proc_q.filter(
        ProcurementRequest.status.in_(["Draft", "Submitted", "Under Review"])
    ).count()
    procurement_by_status = _status_counts(proc_q, ProcurementRequest.status, PROCUREMENT_STATUSES)
    estimated_cost_total = sum((r.estimated_cost or 0) for r in proc_q.all())
    paid_amount_total = sum((r.paid_amount or 0) for r in proc_q.all())
    suppliers_used = len({r.supplier_id for r in proc_q.all() if r.supplier_id})

    # --- activities ---
    act_q = Activity.query.filter_by(cooperative_day_id=event.id)
    activities_total = act_q.count()
    activities_completed = act_q.filter(Activity.status == "Completed").count()
    activities_by_status = _status_counts(act_q, Activity.status, ACTIVITY_STATUSES)

    # --- communication / media ---
    comm_q = Communication.query.filter_by(cooperative_day_id=event.id)
    communications_total = comm_q.count()
    communications_published = comm_q.filter(Communication.status == "Published").count()
    communications_by_type = [
        {"type": t, "count": comm_q.filter(Communication.communication_type == t).count()}
        for t in COMMUNICATION_TYPES
    ]

    return {
        "event": event,
        "teams": teams,
        "teams_total": len(teams),
        "staff": staff,
        "staff_total": len(staff),
        "tasks_total": tasks_total,
        "tasks_completed": tasks_completed,
        "tasks_not_completed": tasks_not_completed,
        "tasks_overdue": tasks_overdue,
        "tasks_completion_rate": round((tasks_completed / tasks_total) * 100, 1) if tasks_total else 0,
        "tasks_by_status": tasks_by_status,
        "documents_total": documents_total,
        "documents_by_status": documents_by_status,
        "correspondence_total": correspondence_total,
        "correspondence_closed": correspondence_closed,
        "instructions_total": instructions_total,
        "instructions_completed": instructions_completed,
        "instructions_overdue": instructions_overdue,
        "instructions_by_status": instructions_by_status,
        "decisions_total": decisions_total,
        "meetings_total": meetings_total,
        "action_points_total": action_points_total,
        "action_points_completed": action_points_completed,
        "procurement_total": procurement_total,
        "procurement_completed": procurement_completed,
        "procurement_pending": procurement_pending,
        "procurement_by_status": procurement_by_status,
        "estimated_cost_total": estimated_cost_total,
        "paid_amount_total": paid_amount_total,
        "suppliers_used": suppliers_used,
        "activities_total": activities_total,
        "activities_completed": activities_completed,
        "activities_by_status": activities_by_status,
        "communications_total": communications_total,
        "communications_published": communications_published,
        "communications_by_type": communications_by_type,
    }


# Metrics shown on the year-comparison dashboard: (context key, display label)
COMPARISON_METRICS = [
    ("teams_total", "Teams / Committees"),
    ("staff_total", "Staff Involved"),
    ("activities_total", "Activities"),
    ("activities_completed", "Activities Completed"),
    ("tasks_total", "Tasks"),
    ("tasks_completed", "Tasks Completed"),
    ("tasks_overdue", "Tasks Overdue"),
    ("documents_total", "Documents Processed"),
    ("procurement_total", "Procurement Requests"),
    ("procurement_completed", "Purchases Completed"),
    ("instructions_total", "Instructions"),
    ("meetings_total", "Meetings"),
    ("decisions_total", "Decisions"),
    ("communications_total", "Communication Items"),
]


def build_comparison(events):
    """Return one report context per event, for side-by-side comparison."""
    return [build_report_context(e) for e in events]
