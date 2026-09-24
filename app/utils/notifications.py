"""Internal notification service (Phase 7 / spec section 22).

Two ways notifications get created:

1. Directly from a route, right when something happens that a specific user
   needs to know about — a task/instruction is assigned to them, a document
   or purchase request needs their action, a meeting action point lands on
   their desk. See notify() / notify_users_with_permission().

2. From scan_deadlines(), which looks for tasks/instructions/correspondence
   approaching or past their deadline and reminds the responsible person.
   It is safe to call often: it never raises the same reminder twice for the
   same record while an earlier one is still unread (see _remind_once).
"""
from datetime import date, timedelta

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User
from app.models.task import Task
from app.models.instruction import Instruction
from app.models.correspondence import Correspondence
from app.models.procurement import ProcurementRequest

DUE_SOON_WINDOW_DAYS = 3


def notify(user_id, title, message=None, category="System", link=None, entity_type=None, entity_id=None):
    """Create one notification for one user. Caller commits."""
    if not user_id:
        return None
    n = Notification(
        user_id=user_id, title=title, message=message, category=category, link=link,
        entity_type=entity_type, entity_id=entity_id,
    )
    db.session.add(n)
    return n


def notify_users_with_permission(code, title, message=None, category="System", link=None,
                                  entity_type=None, entity_id=None, exclude_user_id=None):
    """Notify every active user whose role grants permission `code` —
    used for "needs approval/action" alerts that aren't aimed at one person
    (e.g. a purchase request submitted for approval)."""
    users = User.query.filter_by(status="Active").all()
    for u in users:
        if exclude_user_id and u.id == exclude_user_id:
            continue
        if u.has_permission(code):
            notify(u.id, title, message, category, link, entity_type, entity_id)


def unread_count(user_id):
    if not user_id:
        return 0
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def _remind_once(user_id, category, entity_type, entity_id, title, message, link):
    """Only create the reminder if there isn't already an unread one for
    this exact user/record/category — keeps scan_deadlines idempotent."""
    exists = Notification.query.filter_by(
        user_id=user_id, category=category, entity_type=entity_type, entity_id=entity_id, is_read=False,
    ).first()
    if exists:
        return
    notify(user_id, title, message, category=category, link=link, entity_type=entity_type, entity_id=entity_id)


def scan_deadlines():
    """Raise reminders for tasks/instructions/correspondence that are due
    soon or overdue. Cheap enough to call on every dashboard load for an
    internal tool of this size; wire to a scheduled job if that changes."""
    today = date.today()
    soon = today + timedelta(days=DUE_SOON_WINDOW_DAYS)
    created = 0

    # --- tasks ---
    tasks = Task.query.filter(
        Task.due_date.isnot(None), Task.due_date <= soon, Task.status.notin_(["Completed", "Cancelled"]),
        Task.assigned_user_id.isnot(None),
    ).all()
    for t in tasks:
        overdue = t.due_date < today
        title = f"Task overdue: {t.title}" if overdue else f"Task due soon: {t.title}"
        msg = f"Due {t.due_date.isoformat()}." + (" This task is now overdue." if overdue else "")
        _remind_once(
            t.assigned_user_id, "Task", "Task", t.id, title, msg,
            link=f"/tasks/{t.id}",
        )
        created += 1

    # --- instructions ---
    instructions = Instruction.query.filter(
        Instruction.deadline.isnot(None), Instruction.deadline <= soon,
        Instruction.status.notin_(["Completed", "Closed"]), Instruction.responsible_user_id.isnot(None),
    ).all()
    for i in instructions:
        overdue = i.deadline < today
        title = f"Instruction overdue: {i.title}" if overdue else f"Instruction due soon: {i.title}"
        msg = f"Deadline {i.deadline.isoformat()}." + (" This instruction is now overdue." if overdue else "")
        _remind_once(
            i.responsible_user_id, "Instruction", "Instruction", i.id, title, msg,
            link=f"/instructions/{i.id}",
        )
        created += 1

    # --- correspondence response deadlines ---
    letters = Correspondence.query.filter(
        Correspondence.response_deadline.isnot(None), Correspondence.response_deadline <= soon,
        Correspondence.status.notin_(["Responded", "Closed"]), Correspondence.responsible_user_id.isnot(None),
    ).all()
    for c in letters:
        overdue = c.response_deadline < today
        title = f"Correspondence overdue: {c.subject}" if overdue else f"Response due soon: {c.subject}"
        msg = f"Response deadline {c.response_deadline.isoformat()}." + (
            " This is now overdue." if overdue else ""
        )
        _remind_once(
            c.responsible_user_id, "Correspondence", "Correspondence", c.id, title, msg,
            link=f"/correspondence/{c.id}",
        )
        created += 1

    # --- purchase requests awaiting action, past their required date ---
    requests = ProcurementRequest.query.filter(
        ProcurementRequest.required_date.isnot(None), ProcurementRequest.required_date < today,
        ProcurementRequest.status.notin_(["Completed", "Cancelled", "Delivered"]),
    ).all()
    for r in requests:
        if not r.requested_by_id:
            continue
        _remind_once(
            r.requested_by_id, "Procurement", "ProcurementRequest", r.id,
            f"Purchase request overdue: {r.item_service}",
            f"Required date {r.required_date.isoformat()} has passed and status is still '{r.status}'.",
            link=f"/procurement/requests/{r.id}",
        )
        created += 1

    if created:
        db.session.commit()
    return created
