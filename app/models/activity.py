from datetime import datetime
from app.extensions import db

ACTIVITY_STATUSES = ["Planned", "Confirmed", "In Progress", "Completed", "Cancelled"]

# Common Cooperative Day activity types, per spec section 17. Kept as free
# text on the model (not an FK) so admins are never blocked from typing a
# new one — this list only seeds the form's dropdown with sensible defaults.
ACTIVITY_TYPES = [
    "Opening Ceremony", "Exhibition", "Cooperative Awards", "Farmer/Cooperative Visit",
    "Panel Discussion", "Training", "Media Event", "Community Activity",
    "Closing Ceremony", "Other",
]


class Activity(db.Model):
    """One scheduled Cooperative Day activity/event item, e.g. 'Opening Ceremony'.

    Belongs to a CooperativeDay year, optionally owned by a Team, and can
    carry an expected participant list via ActivityParticipant.
    """

    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    activity_type = db.Column(db.String(60))

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))  # responsible team
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # responsible person

    activity_date = db.Column(db.Date)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    location = db.Column(db.String(255))

    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    budget_reference = db.Column(db.String(120))  # free-text pointer to a ProcurementRequest/budget line

    status = db.Column(db.String(20), default="Planned", nullable=False, index=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("activities", lazy="dynamic"))
    team = db.relationship("Team")
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    participants = db.relationship(
        "ActivityParticipant", backref="activity", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Activity {self.name}>"


class ActivityParticipant(db.Model):
    """A staff member (or invited participant, tracked by name) expected at
    an activity. Mirrors MeetingParticipant's attended-tracking pattern."""

    __tablename__ = "activity_participants"
    __table_args__ = (db.UniqueConstraint("activity_id", "user_id", name="uq_activity_user"),)

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    attended = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User")

    def __repr__(self):
        return f"<ActivityParticipant activity={self.activity_id} user={self.user_id}>"
