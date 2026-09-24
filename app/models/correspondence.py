from datetime import datetime, date
from app.extensions import db

CORRESPONDENCE_CATEGORIES = [
    "Incoming Letter", "Outgoing Letter", "Internal Memo", "Email Record",
    "Instruction", "Meeting Decision", "Request", "Response",
]

CORRESPONDENCE_PRIORITIES = ["Low", "Medium", "High", "Critical"]

# tracked lifecycle, per spec: Received / Assigned / In progress / Responded / Closed
CORRESPONDENCE_STATUSES = ["Received", "Assigned", "In Progress", "Responded", "Closed"]


class Correspondence(db.Model):
    """Incoming/outgoing letters, memos, instructions and other tracked
    correspondence, with its own reference number and response deadline."""

    __tablename__ = "correspondence"

    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(60), unique=True, nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False)
    subject = db.Column(db.String(255), nullable=False)

    from_party = db.Column(db.String(150))
    to_party = db.Column(db.String(150))

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))

    date_received = db.Column(db.Date)
    date_sent = db.Column(db.Date)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    priority = db.Column(db.String(20), default="Medium", nullable=False)
    status = db.Column(db.String(20), default="Received", nullable=False, index=True)
    response_deadline = db.Column(db.Date, index=True)

    notes = db.Column(db.Text)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("correspondences", lazy="dynamic"))
    department = db.relationship("Department")
    team = db.relationship("Team")
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    # Documents (attachments) uploaded against this correspondence record —
    # see Document.correspondence_id.
    attachments = db.relationship("Document", backref="correspondence", lazy="dynamic")

    @property
    def is_overdue(self):
        return bool(
            self.response_deadline and self.response_deadline < date.today()
            and self.status not in ("Responded", "Closed")
        )

    def __repr__(self):
        return f"<Correspondence {self.reference_number}>"
