from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.instruction import Instruction, Decision, INSTRUCTION_STATUSES
from app.models.event import CooperativeDay
from app.models.department import Department
from app.models.team import Team
from app.models.task import Task
from app.models.user import User
from app.instructions.forms import InstructionForm, DecisionForm
from app.utils.decorators import permission_required
from app.utils.audit import log_action
from app.utils.notifications import notify

instructions_bp = Blueprint("instructions", __name__)


# ---------------------------------------------------------------- instructions
@instructions_bp.route("/")
@login_required
@permission_required("manage_instructions")
def instructions_list():
    event_id = request.args.get("event_id", type=int)
    status = request.args.get("status", "")
    query = Instruction.query
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    if status:
        query = query.filter_by(status=status)
    instructions = query.order_by(Instruction.deadline.is_(None), Instruction.deadline).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template(
        "instructions/list.html", instructions=instructions, events=events,
        statuses=INSTRUCTION_STATUSES, selected_event_id=event_id, selected_status=status,
        today=date.today(),
    )


@instructions_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("manage_instructions")
def instruction_new():
    form = InstructionForm()
    _populate_choices(form)
    if form.validate_on_submit():
        instr = Instruction(
            title=form.title.data,
            description=form.description.data,
            cooperative_day_id=form.cooperative_day_id.data,
            source_person=form.source_person.data,
            instruction_date=form.instruction_date.data or date.today(),
            department_id=form.department_id.data or None,
            responsible_user_id=form.responsible_user_id.data or None,
            team_id=form.team_id.data or None,
            task_id=form.task_id.data or None,
            deadline=form.deadline.data,
            priority=form.priority.data,
            status=form.status.data,
            created_by_id=current_user.id,
        )
        db.session.add(instr)
        db.session.flush()
        log_action("create", "Instruction", instr.id, f"Created instruction '{instr.title}'")
        if instr.responsible_user_id and instr.responsible_user_id != current_user.id:
            notify(
                instr.responsible_user_id, f"Instruction assigned: {instr.title}",
                f"From {instr.source_person or 'management'}."
                + (f" Deadline {instr.deadline.isoformat()}." if instr.deadline else ""),
                category="Instruction", link=f"/instructions/{instr.id}",
                entity_type="Instruction", entity_id=instr.id,
            )
        db.session.commit()
        flash(f"Instruction '{instr.title}' recorded.", "success")
        return redirect(url_for("instructions.instruction_detail", instruction_id=instr.id))
    return render_template("instructions/form.html", form=form, is_new=True)


@instructions_bp.route("/<int:instruction_id>")
@login_required
@permission_required("manage_instructions")
def instruction_detail(instruction_id):
    instr = Instruction.query.get_or_404(instruction_id)
    return render_template("instructions/detail.html", instruction=instr)


@instructions_bp.route("/<int:instruction_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("manage_instructions")
def instruction_edit(instruction_id):
    instr = Instruction.query.get_or_404(instruction_id)
    form = InstructionForm(obj=instr)
    _populate_choices(form)
    if request.method == "GET":
        form.department_id.data = instr.department_id or 0
        form.responsible_user_id.data = instr.responsible_user_id or 0
        form.team_id.data = instr.team_id or 0
        form.task_id.data = instr.task_id or 0

    if form.validate_on_submit():
        instr.title = form.title.data
        instr.description = form.description.data
        instr.cooperative_day_id = form.cooperative_day_id.data
        instr.source_person = form.source_person.data
        instr.instruction_date = form.instruction_date.data or date.today()
        instr.department_id = form.department_id.data or None
        instr.responsible_user_id = form.responsible_user_id.data or None
        instr.team_id = form.team_id.data or None
        instr.task_id = form.task_id.data or None
        instr.deadline = form.deadline.data
        instr.priority = form.priority.data
        instr.status = form.status.data
        log_action("update", "Instruction", instr.id, f"Updated instruction '{instr.title}'")
        db.session.commit()
        flash(f"Instruction '{instr.title}' updated.", "success")
        return redirect(url_for("instructions.instruction_detail", instruction_id=instr.id))
    return render_template("instructions/form.html", form=form, is_new=False, instruction=instr)


@instructions_bp.route("/<int:instruction_id>/status/<string:new_status>", methods=["POST"])
@login_required
@permission_required("manage_instructions")
def instruction_quick_status(instruction_id, new_status):
    instr = Instruction.query.get_or_404(instruction_id)
    if new_status not in INSTRUCTION_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("instructions.instruction_detail", instruction_id=instr.id))
    instr.status = new_status
    log_action("update", "Instruction", instr.id, f"Status changed to {new_status}")
    db.session.commit()
    flash(f"Instruction status set to {new_status}.", "success")
    return redirect(url_for("instructions.instruction_detail", instruction_id=instr.id))


# -------------------------------------------------------------- decision register
@instructions_bp.route("/decisions")
@login_required
@permission_required("manage_instructions")
def decisions_list():
    event_id = request.args.get("event_id", type=int)
    query = Decision.query
    if event_id:
        query = query.filter_by(cooperative_day_id=event_id)
    decisions = query.order_by(Decision.decision_date.desc()).all()
    events = CooperativeDay.query.order_by(CooperativeDay.year.desc()).all()
    return render_template("instructions/decisions_list.html", decisions=decisions, events=events, selected_event_id=event_id)


@instructions_bp.route("/decisions/new/<int:event_id>", methods=["GET", "POST"])
@login_required
@permission_required("manage_instructions")
def decision_new(event_id):
    event = CooperativeDay.query.get_or_404(event_id)
    form = DecisionForm()
    _populate_decision_choices(form, event)
    if form.validate_on_submit():
        decision = Decision(
            title=form.title.data,
            description=form.description.data,
            cooperative_day_id=event.id,
            decision_date=form.decision_date.data or date.today(),
            responsible_user_id=form.responsible_user_id.data or None,
            related_task_id=form.related_task_id.data or None,
            status=form.status.data,
            created_by_id=current_user.id,
        )
        db.session.add(decision)
        db.session.flush()
        log_action("create", "Decision", decision.id, f"Recorded decision '{decision.title}'")
        db.session.commit()
        flash("Decision recorded in the register.", "success")
        return redirect(url_for("instructions.decisions_list", event_id=event.id))
    return render_template("instructions/decision_form.html", form=form, event=event)


def _populate_choices(form):
    form.cooperative_day_id.choices = [
        (e.id, e.name) for e in CooperativeDay.query.order_by(CooperativeDay.year.desc())
    ]
    form.department_id.choices = [(0, "— None —")] + [
        (d.id, d.name) for d in Department.query.filter_by(is_active=True).order_by(Department.name)
    ]
    form.responsible_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
    form.team_id.choices = [(0, "— None —")] + [(t.id, t.name) for t in Team.query.order_by(Team.name)]
    form.task_id.choices = [(0, "— None —")] + [(t.id, t.title) for t in Task.query.order_by(Task.title)]


def _populate_decision_choices(form, event):
    form.responsible_user_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(status="Active").order_by(User.full_name)
    ]
    form.related_task_id.choices = [(0, "— None —")] + [
        (t.id, t.title) for t in Task.query.filter_by(cooperative_day_id=event.id).order_by(Task.title)
    ]
