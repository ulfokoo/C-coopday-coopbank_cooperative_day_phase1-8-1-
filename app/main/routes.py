from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user

from app.models.event import CooperativeDay
from app.models.team import Team
from app.models.department import Department
from app.models.user import User
from app.models.task import Task
from app.models.instruction import Instruction
from app.models.document import Document
from app.models.meeting import Meeting
from app.models.procurement import ProcurementRequest
from app.models.activity import Activity
from app.utils.notifications import scan_deadlines

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    # Raise any new due-soon/overdue reminders. Cheap and idempotent — see
    # app.utils.notifications.scan_deadlines / _remind_once.
    scan_deadlines()

    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    teams = Team.query.order_by(Team.name).all()
    users = User.query.filter_by(status="Active").order_by(User.full_name).all()

    # --- filters: Cooperative Day year, department, team, status, responsible person ---
    event_id = request.args.get("event_id", type=int)
    department_id = request.args.get("department_id", type=int)
    team_id = request.args.get("team_id", type=int)
    status = request.args.get("status", "", type=str)
    responsible_user_id = request.args.get("responsible_user_id", type=int)

    active_event = (
        CooperativeDay.query.get(event_id) if event_id else (events[0] if events else None)
    )

    def apply_task_filters(query):
        if event_id:
            query = query.filter(Task.cooperative_day_id == event_id)
        if department_id:
            query = query.filter(Task.department_id == department_id)
        if team_id:
            query = query.filter(Task.team_id == team_id)
        if status:
            query = query.filter(Task.status == status)
        if responsible_user_id:
            query = query.filter(Task.assigned_user_id == responsible_user_id)
        return query

    today = date.today()
    soon = today + timedelta(days=7)

    total_events = len(events)
    total_teams = Team.query.filter_by(cooperative_day_id=event_id).count() if event_id else Team.query.count()
    total_staff = User.query.filter_by(status="Active").count()

    # --- task indicators (respecting filters) ---
    total_tasks = apply_task_filters(Task.query).count()
    completed_tasks = apply_task_filters(Task.query).filter(Task.status == "Completed").count()
    pending_tasks = apply_task_filters(Task.query).filter(Task.status.notin_(["Completed", "Cancelled"])).count()
    overdue_tasks = apply_task_filters(Task.query).filter(
        Task.due_date.isnot(None), Task.due_date < today, Task.status.notin_(["Completed", "Cancelled"])
    ).count()
    tasks_due_soon = apply_task_filters(Task.query).filter(
        Task.due_date.isnot(None), Task.due_date >= today, Task.due_date <= soon,
        Task.status.notin_(["Completed", "Cancelled"]),
    ).count()

    # --- instruction indicators ---
    instr_query = Instruction.query
    if event_id:
        instr_query = instr_query.filter_by(cooperative_day_id=event_id)
    open_instructions = instr_query.filter(Instruction.status.notin_(["Completed", "Closed"])).count()
    overdue_instructions = instr_query.filter(
        Instruction.deadline.isnot(None), Instruction.deadline < today,
        Instruction.status.notin_(["Completed", "Closed"]),
    ).count()

    # --- document indicators ---
    doc_query = Document.query
    if event_id:
        doc_query = doc_query.filter_by(cooperative_day_id=event_id)
    total_documents = doc_query.count()
    pending_document_approvals = doc_query.filter(Document.status.in_(["Submitted", "Under Review"])).count()

    # --- procurement indicators ---
    proc_query = ProcurementRequest.query
    if event_id:
        proc_query = proc_query.filter_by(cooperative_day_id=event_id)
    total_purchase_requests = proc_query.count()
    pending_purchase_requests = proc_query.filter(
        ProcurementRequest.status.in_(["Draft", "Submitted", "Under Review"])
    ).count()
    completed_purchases = proc_query.filter(ProcurementRequest.status == "Completed").count()

    # --- meetings ---
    meeting_query = Meeting.query.filter(Meeting.meeting_date >= today)
    if event_id:
        meeting_query = meeting_query.filter_by(cooperative_day_id=event_id)
    upcoming_meetings = meeting_query.order_by(Meeting.meeting_date).limit(5).all()

    # --- upcoming activities ---
    activity_query = Activity.query.filter(
        Activity.activity_date.isnot(None), Activity.activity_date >= today,
        Activity.status.notin_(["Cancelled", "Completed"]),
    )
    if event_id:
        activity_query = activity_query.filter_by(cooperative_day_id=event_id)
    upcoming_activities = activity_query.order_by(Activity.activity_date).limit(5).all()
    upcoming_activities_count = activity_query.count()

    # ---------------------------------------------------------------------
    # Chart.js data
    # ---------------------------------------------------------------------
    from app.models.task import TASK_STATUSES
    from app.models.procurement import PROCUREMENT_STATUSES
    from app.models.document import DOCUMENT_STATUSES

    task_status_chart = {
        "labels": TASK_STATUSES,
        "data": [apply_task_filters(Task.query).filter(Task.status == s).count() for s in TASK_STATUSES],
    }

    proc_status_chart = {
        "labels": PROCUREMENT_STATUSES,
        "data": [proc_query.filter(ProcurementRequest.status == s).count() for s in PROCUREMENT_STATUSES],
    }

    doc_status_chart = {
        "labels": DOCUMENT_STATUSES,
        "data": [doc_query.filter(Document.status == s).count() for s in DOCUMENT_STATUSES],
    }

    activities_by_dept = {}
    act_dept_query = Activity.query
    if event_id:
        act_dept_query = act_dept_query.filter_by(cooperative_day_id=event_id)
    for a in act_dept_query.all():
        key = a.team.name if a.team else "Unassigned"
        activities_by_dept[key] = activities_by_dept.get(key, 0) + 1
    activities_by_dept_chart = {
        "labels": list(activities_by_dept.keys()), "data": list(activities_by_dept.values()),
    }

    tasks_by_team = {}
    tbt_query = Task.query
    if event_id:
        tbt_query = tbt_query.filter_by(cooperative_day_id=event_id)
    for t in tbt_query.all():
        key = t.team.name if t.team else "Unassigned"
        tasks_by_team[key] = tasks_by_team.get(key, 0) + 1
    tasks_by_team_chart = {"labels": list(tasks_by_team.keys()), "data": list(tasks_by_team.values())}

    progress_by_year_labels = []
    progress_by_year_data = []
    for e in sorted(events, key=lambda e: e.year):
        year_tasks = Task.query.filter_by(cooperative_day_id=e.id)
        total = year_tasks.count()
        completed = year_tasks.filter_by(status="Completed").count()
        pct = round((completed / total) * 100, 1) if total else 0
        progress_by_year_labels.append(str(e.year))
        progress_by_year_data.append(pct)
    progress_by_year_chart = {"labels": progress_by_year_labels, "data": progress_by_year_data}

    return render_template(
        "main/dashboard.html",
        events=events, active_event=active_event,
        departments=departments, teams=teams, users=users,
        selected_event_id=event_id, selected_department_id=department_id, selected_team_id=team_id,
        selected_status=status, selected_responsible_user_id=responsible_user_id,
        task_statuses=TASK_STATUSES,
        total_events=total_events, total_teams=total_teams, total_staff=total_staff,
        total_tasks=total_tasks, completed_tasks=completed_tasks, pending_tasks=pending_tasks,
        overdue_tasks=overdue_tasks, tasks_due_soon=tasks_due_soon,
        open_instructions=open_instructions, overdue_instructions=overdue_instructions,
        total_documents=total_documents, pending_document_approvals=pending_document_approvals,
        total_purchase_requests=total_purchase_requests, pending_purchase_requests=pending_purchase_requests,
        completed_purchases=completed_purchases,
        upcoming_meetings=upcoming_meetings, upcoming_activities=upcoming_activities,
        upcoming_activities_count=upcoming_activities_count,
        task_status_chart=task_status_chart, proc_status_chart=proc_status_chart,
        doc_status_chart=doc_status_chart, activities_by_dept_chart=activities_by_dept_chart,
        tasks_by_team_chart=tasks_by_team_chart, progress_by_year_chart=progress_by_year_chart,
    )
