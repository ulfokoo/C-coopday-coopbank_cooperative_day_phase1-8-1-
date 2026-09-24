from datetime import datetime, date
from app.extensions import db

TASK_PRIORITIES = ["Low", "Medium", "High", "Critical"]
TASK_STATUSES = ["Not Started", "In Progress", "Waiting", "Completed", "Cancelled"]


class Task(db.Model):
    """A unit of work under a Cooperative Day year. Can be linked to a team,
    department, user, document, instruction and/or a meeting action point."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    priority = db.Column(db.String(20), default="Medium", nullable=False)
    status = db.Column(db.String(20), default="Not Started", nullable=False, index=True)
    percent_complete = db.Column(db.Integer, default=0, nullable=False)

    start_date = db.Column(db.Date)
    due_date = db.Column(db.Date, index=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("tasks", lazy="dynamic"))
    department = db.relationship("Department", backref=db.backref("tasks", lazy="dynamic"))
    team = db.relationship("Team", backref=db.backref("tasks", lazy="dynamic"))
    assigned_user = db.relationship("User", foreign_keys=[assigned_user_id], backref=db.backref("assigned_tasks", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    comments = db.relationship("TaskComment", backref="task", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def is_overdue(self):
        return bool(
            self.due_date and self.due_date < date.today() and self.status not in ("Completed", "Cancelled")
        )

    def __repr__(self):
        return f"<Task {self.title}>"


class TaskComment(db.Model):
    __tablename__ = "task_comments"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")

    def __repr__(self):
        return f"<TaskComment task={self.task_id}>"
