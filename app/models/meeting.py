from datetime import datetime, date
from app.extensions import db

ACTION_POINT_STATUSES = ["Open", "In Progress", "Completed", "Cancelled"]


class Meeting(db.Model):
    """A scheduled meeting: agenda + minutes + decisions + action points."""

    __tablename__ = "meetings"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)

    meeting_date = db.Column(db.Date, default=date.today, nullable=False)
    meeting_time = db.Column(db.Time)
    location = db.Column(db.String(255))

    organizer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))

    agenda = db.Column(db.Text)
    minutes = db.Column(db.Text)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("meetings", lazy="dynamic"))
    organizer = db.relationship("User", foreign_keys=[organizer_id])
    team = db.relationship("Team")
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    participants = db.relationship("MeetingParticipant", backref="meeting", lazy="dynamic", cascade="all, delete-orphan")
    action_points = db.relationship("ActionPoint", backref="meeting", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Meeting {self.title}>"


class MeetingParticipant(db.Model):
    __tablename__ = "meeting_participants"
    __table_args__ = (db.UniqueConstraint("meeting_id", "user_id", name="uq_meeting_user"),)

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    attended = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User")

    def __repr__(self):
        return f"<MeetingParticipant meeting={self.meeting_id} user={self.user_id}>"


class ActionPoint(db.Model):
    """An action item raised in a meeting. Can be promoted into a full Task
    (see instructions.services.create_task_from_action_point)."""

    __tablename__ = "action_points"

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="Open", nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"))  # set once promoted to a task

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    responsible_user = db.relationship("User")
    task = db.relationship("Task", backref=db.backref("source_action_point", uselist=False))

    def __repr__(self):
        return f"<ActionPoint meeting={self.meeting_id}>"
