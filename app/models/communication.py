from datetime import datetime
from app.extensions import db

COMMUNICATION_TYPES = [
    "Press Release", "Social Media Post", "Poster", "Invitation", "Video", "Photo",
    "Media Coverage", "Radio/TV Communication", "Website Communication", "Other",
]

COMMUNICATION_STATUSES = ["Planned", "In Progress", "Published", "Cancelled"]

APPROVAL_STATUSES = ["Pending", "Approved", "Rejected"]


class Communication(db.Model):
    """One communication/media item (press release, poster, social post...).

    Carries a single optional attachment (the flyer/photo/video file itself)
    — heavier document version history belongs to the Documents module;
    this stays a lightweight record for the comms/media pipeline.
    """

    __tablename__ = "communications"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    communication_type = db.Column(db.String(60), nullable=False)

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    description = db.Column(db.Text)
    target_audience = db.Column(db.String(255))
    platform = db.Column(db.String(120))

    planned_date = db.Column(db.Date)
    publication_date = db.Column(db.Date)

    status = db.Column(db.String(20), default="Planned", nullable=False, index=True)
    approval_status = db.Column(db.String(20), default="Pending", nullable=False, index=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)

    # optional single attachment — same safe-filename convention as Documents
    original_filename = db.Column(db.String(255))
    stored_filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(120))

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("communications", lazy="dynamic"))
    team = db.relationship("Team")
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    @property
    def has_attachment(self):
        return bool(self.stored_filename)

    def __repr__(self):
        return f"<Communication {self.title}>"
