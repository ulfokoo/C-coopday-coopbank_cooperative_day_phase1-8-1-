from datetime import datetime
from app.extensions import db

# Groups notifications for icons/filtering in the notification center.
NOTIFICATION_CATEGORIES = [
    "Task", "Instruction", "Document", "Procurement", "Meeting",
    "Correspondence", "Activity", "Communication", "System",
]


class Notification(db.Model):
    """One in-app notification for one user.

    Created either directly by a route (e.g. 'you were assigned a task') or
    by the periodic deadline scan (app.utils.notifications.scan_deadlines),
    which uses entity_type/entity_id/category to avoid raising the same
    reminder twice while it's still unread.
    """

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500))
    category = db.Column(db.String(30), default="System", nullable=False)
    link = db.Column(db.String(500))  # relative url to open when clicked

    # Optional pointer back to the source record, used for de-duplication.
    entity_type = db.Column(db.String(80))
    entity_id = db.Column(db.Integer)

    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    def __repr__(self):
        return f"<Notification user={self.user_id} {self.title!r}>"
