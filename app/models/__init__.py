# Import every model here so that Flask-Migrate / db.create_all() can see them
# through a single `from app.models import *`-style discovery.
#
# Import order matters only in that a model referenced by string name in a
# db.relationship()/db.ForeignKey() must be registered on the same
# declarative base before mappers are configured — importing everything
# here, once, at app start-up (see app/__init__.py) takes care of that.
from app.models.user import User, Role, Permission, role_permissions
from app.models.department import Department
from app.models.event import CooperativeDay
from app.models.team import Team, TeamMember
from app.models.task import Task, TaskComment
from app.models.meeting import Meeting, MeetingParticipant, ActionPoint
from app.models.instruction import Instruction, Decision
from app.models.correspondence import Correspondence
from app.models.procurement import Supplier, ProcurementRequest, ProcurementItem, Material
from app.models.document import Document, DocumentVersion
from app.models.activity import Activity, ActivityParticipant
from app.models.communication import Communication
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.models.report import AnnualReport
