from datetime import datetime, date
from app.extensions import db

INSTRUCTION_PRIORITIES = ["Low", "Medium", "High", "Critical"]
INSTRUCTION_STATUSES = ["New", "Assigned", "In Progress", "Completed", "Overdue", "Closed"]

DECISION_STATUSES = ["Open", "In Progress", "Implemented", "Closed"]


class Instruction(db.Model):
    """A management instruction/directive, e.g. 'Prepare the invitation
    package by September 15', with a responsible person and a deadline."""

    __tablename__ = "instructions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    source_person = db.Column(db.String(150))  # who issued the instruction
    instruction_date = db.Column(db.Date, default=date.today)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"))

    deadline = db.Column(db.Date, index=True)
    priority = db.Column(db.String(20), default="Medium", nullable=False)
    status = db.Column(db.String(20), default="New", nullable=False, index=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("instructions", lazy="dynamic"))
    department = db.relationship("Department")
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])
    team = db.relationship("Team")
    task = db.relationship("Task", backref=db.backref("instructions", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    @property
    def is_overdue(self):
        return bool(self.deadline and self.deadline < date.today() and self.status not in ("Completed", "Closed"))

    def __repr__(self):
        return f"<Instruction {self.title}>"


class Decision(db.Model):
    """Decision Register: important decisions made during meetings (or
    standalone), each with an optional owner and follow-up task."""

    __tablename__ = "decisions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"))
    decision_date = db.Column(db.Date, default=date.today)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    related_task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"))
    status = db.Column(db.String(20), default="Open", nullable=False)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("decisions", lazy="dynamic"))
    meeting = db.relationship("Meeting", backref=db.backref("decisions", lazy="dynamic"))
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])
    related_task = db.relationship("Task")
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Decision {self.title}>"
