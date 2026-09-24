from datetime import datetime
from app.extensions import db

EVENT_STATUSES = ["Planning", "Preparation", "Procurement", "Implementation", "Completed", "Cancelled"]


class CooperativeDay(db.Model):
    """One yearly Cooperative Day event/workspace, e.g. 'Cooperative Day 2026'.

    Everything else in the system (teams, tasks, documents, procurement,
    activities, communications, reports...) hangs off a CooperativeDay so
    that each year's data stays a self-contained, permanently accessible
    historical record.
    """

    __tablename__ = "cooperative_days"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)  # e.g. "Cooperative Day 2026"
    theme = db.Column(db.String(255))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    location = db.Column(db.String(255))
    description = db.Column(db.Text)

    status = db.Column(db.String(30), default="Planning", nullable=False)

    coordinator_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teams = db.relationship(
        "Team", backref="cooperative_day", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CooperativeDay {self.year}>"
