from datetime import datetime
from app.extensions import db


class Department(db.Model):
    """Departments/sectors are fully admin-configurable — never hard-coded
    into application logic. Examples: Agri Business, Procurement, Finance..."""

    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", backref="department", lazy="dynamic")

    def __repr__(self):
        return f"<Department {self.name}>"
