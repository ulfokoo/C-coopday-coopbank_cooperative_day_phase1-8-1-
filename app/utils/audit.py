from flask import request
from flask_login import current_user
from app.extensions import db
from app.models.audit import AuditLog


def log_action(action, entity_type, entity_id=None, description=None):
    """Write one audit trail row. Call this from route handlers after a
    create/update/delete/archive so every module shares one audit log."""
    entry = AuditLog(
        user_id=current_user.id if getattr(current_user, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
    # Caller is responsible for db.session.commit() as part of its own transaction.
