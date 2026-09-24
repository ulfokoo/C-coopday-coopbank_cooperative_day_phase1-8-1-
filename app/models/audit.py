from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """Lightweight audit trail: who did what, to which record, and when.
    Later phases (documents, procurement, tasks...) all write here through
    app.utils.audit.log_action() rather than each module rolling its own."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(50), nullable=False)  # create / update / delete / archive / login ...
    entity_type = db.Column(db.String(80), nullable=False)  # e.g. "User", "CooperativeDay"
    entity_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User")

    def __repr__(self):
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"
