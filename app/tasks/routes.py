from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.task import Task, TaskComment
from app.models.event import CooperativeDay
from app.models.department import Department
from app.models.team import Team
from app.models.user import User
from app.tasks.forms import TaskForm, TaskCommentForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action
from app.utils.notifications import notify
from app.utils.team_scope import restrict_query, can_access, team_choices

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/")
@login_required
@permission_required("manage_tasks")
def tasks_list():
    event_id = request.args.get("event_id", type=int)
    team_id = request.args.get("team_id", type=int)
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    assigned_user_id = request.args.get("assigned_user_id", type=int)
    keyword = request.args.get("q", "").strip()

    query = restrict_query(Task.query, Task)
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if team_id:
        query = query.filter_by(team_id=team_id)
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if assigned_user_id:
        query = query.filter_by(assigned_user_id=assigned_user_id)
    if keyword:
        query = query.filter(Task.title.ilike(f"%{keyword}%"))

    tasks = query.order_by(Task.due_date.is_(None), Task.due_date, Task.priority.desc()).all()

    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    teams = Team.query.order_by(Team.name).all()
    users = User.query.filter_by(status="Active").order_by(User.full_name).all()

    from app.models.task import TASK_PRIORITIES, TASK_STATUSES

    return render_template(
        "tasks/list.html", tasks=tasks, events=events, teams=teams, users=users,
        statuses=TASK_STATUSES, priorities=TASK_PRIORITIES,
        selected_event_id=event_id, selected_team_id=team_id, selected_status=status,
        selected_priority=priority, selected_assigned_user_id=assigned_user_id, keyword=keyword,
        today=date.today(),
    )


@tasks_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_tasks")
def task_new():
    form = TaskForm()
    _populate_choices(form)
    if form.validate_on_submit():
        task = Task(
            title=form.title.data,
            description=form.description.data,
            cooperative_day_id=form.cooperative_day_id.data,
            department_id=form.department_id.data or None,
            team_id=form.team_id.data or None,
            assigned_user_id=form.assigned_user_id.data or None,
            priority=form.priority.data,
            status=form.status.data,
            percent_complete=form.percent_complete.data or 0,
            start_date=form.start_date.data,
            due_date=form.due_date.data,
            created_by_id=current_user.id,
        )
        db.session.add(task)
        db.session.flush()
        log_action("create", "Task", task.id, f"Created task '{task.title}'")
        if task.assigned_user_id and task.assigned_user_id != current_user.id:
            notify(
                task.assigned_user_id, f"Task assigned: {task.title}",
                f"You were assigned a {task.priority.lower()} priority task"
                + (f", due {task.due_date.isoformat()}." if task.due_date else "."),
                category="Task", link=f"/tasks/{task.id}", entity_type="Task", entity_id=task.id,
            )
        db.session.commit()
        flash(f"Task '{task.title}' created.", "success")
        return redirect(url_for("tasks.task_detail", task_id=task.id))
    return render_template("tasks/form.html", form=form, is_new=True)


@tasks_bp.route("/<int:task_id>")
@login_required
@permission_required("manage_tasks")
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    if not can_access(task):
        abort(403)
    comment_form = TaskCommentForm()
    comments = task.comments.order_by(TaskComment.created_at.desc()).all()
    return render_template("tasks/detail.html", task=task, comment_form=comment_form, comments=comments)


@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_tasks")
def task_edit(task_id):
    task = Task.query.get_or_404(task_id)
    if not can_access(task):
          abort(403)
    form = TaskForm(obj=task)
    _populate_choices(form)
    if request.method == "GET":
        form.department_id.data = task.department_id or 0
        form.team_id.data = task.team_id or 0
        form.assigned_user_id.data = task.assigned_user_id or 0

    if form.validate_on_submit():
        previous_assignee_id = task.assigned_user_id
        task.title = form.title.data
        task.description = form.description.data
        task.cooperative_day_id = form.cooperative_day_id.data
        task.department_id = form.department_id.data or None
        task.team_id = form.team_id.data or None
        task.assigned_user_id = form.assigned_user_id.data or None
        task.priority = form.priority.data
        task.status = form.status.data
        task.percent_complete = form.percent_complete.data or 0
        task.start_date = form.start_date.data
        task.due_date = form.due_date.data
        log_action("update", "Task", task.id, f"Updated task '{task.title}'")
        if (
            task.assigned_user_id
            and task.assigned_user_id != previous_assignee_id
            and task.assigned_user_id != current_user.id
        ):
            notify(
                task.assigned_user_id, f"Task assigned: {task.title}",
                f"You were assigned a {task.priority.lower()} priority task"
                + (f", due {task.due_date.isoformat()}." if task.due_date else "."),
                category="Task", link=f"/tasks/{task.id}", entity_type="Task", entity_id=task.id,
            )
        db.session.commit()
        flash(f"Task '{task.title}' updated.", "success")
        return redirect(url_for("tasks.task_detail", task_id=task.id))
    return render_template("tasks/form.html", form=form, is_new=False, task=task)


@tasks_bp.route("/<int:task_id>/comments", methods=["POST"])
@login_required
@permission_required("manage_tasks")
def task_comment_add(task_id):
    task = Task.query.get_or_404(task_id)
    if not can_access(task):
          abort(403)
    form = TaskCommentForm()
    if form.validate_on_submit():
        comment = TaskComment(task_id=task.id, user_id=current_user.id, comment=form.comment.data)
        db.session.add(comment)
        db.session.flush()
        log_action("create", "TaskComment", comment.id, f"Commented on task {task.id}")
        db.session.commit()
        flash("Comment added.", "success")
    else:
        flash("Comment could not be added.", "danger")
    return redirect(url_for("tasks.task_detail", task_id=task.id))


@tasks_bp.route("/<int:task_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("manage_tasks")
def task_quick_status(task_id, new_status):
    from app.models.task import TASK_STATUSES

    task = Task.query.get_or_404(task_id)
    if not can_access(task):
        abort(403)
    if new_status not in TASK_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("tasks.task_detail", task_id=task.id))
    task.status = new_status
    if new_status == "Completed":
        task.percent_complete = 100
    log_action("update", "Task", task.id, f"Status changed to {new_status}")
    db.session.commit()
    flash(f"Task status set to {new_status}.", "success")
    return redirect(url_for("tasks.task_detail", task_id=task.id))


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.department_id.choices = [(0, "— None —")] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).order_by(Department.name)
    ]
    form.team_id.choices = team_choices()
    form.assigned_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
