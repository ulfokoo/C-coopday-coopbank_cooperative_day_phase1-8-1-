from datetime import datetime
from app.extensions import db

DOCUMENT_TYPES = [
    "Official Letter", "Meeting Minutes", "Concept Note", "Event Plan", "Invitation",
    "Agreement", "Procurement Document", "Quotation", "Purchase Request", "Approval",
    "Receipt", "Contract", "Report", "Photo", "Video", "Design", "Poster",
    "Communication Material", "Instruction", "Other",
]

DOCUMENT_STATUSES = ["Draft", "Submitted", "Under Review", "Approved", "Rejected", "Archived"]

CONFIDENTIALITY_LEVELS = ["Public", "Internal", "Confidential", "Restricted"]


class Document(db.Model):
    """A managed document. The actual file(s) live in DocumentVersion so the
    same logical document (e.g. 'Cooperative_Day_2026_Plan') can carry v1,
    v2, ...Final while this row stays the stable metadata record."""

    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    document_type = db.Column(db.String(60), nullable=False)

    cooperative_day_id = db.Column(db.Integer, db.ForeignKey("cooperative_days.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))

    # optional cross-links, per spec ("a document can be linked to event,
    # team, department, task, procurement, meeting, instruction")
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"))
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id"))
    instruction_id = db.Column(db.Integer, db.ForeignKey("instructions.id"))
    correspondence_id = db.Column(db.Integer, db.ForeignKey("correspondence.id"))
    # Phase 5: now a real FK against procurement_requests.
    procurement_request_id = db.Column(db.Integer, db.ForeignKey("procurement_requests.id"))

    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    status = db.Column(db.String(20), default="Draft", nullable=False, index=True)
    confidentiality_level = db.Column(db.String(20), default="Internal", nullable=False)
    description = db.Column(db.Text)
    tags = db.Column(db.String(255))  # comma-separated, kept simple & searchable with LIKE

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cooperative_day = db.relationship("CooperativeDay", backref=db.backref("documents", lazy="dynamic"))
    department = db.relationship("Department")
    team = db.relationship("Team")
    task = db.relationship("Task", backref=db.backref("documents", lazy="dynamic"))
    meeting = db.relationship("Meeting", backref=db.backref("documents", lazy="dynamic"))
    instruction = db.relationship("Instruction", backref=db.backref("documents", lazy="dynamic"))
    procurement_request = db.relationship("ProcurementRequest", backref=db.backref("documents", lazy="dynamic"))
    owner = db.relationship("User", foreign_keys=[owner_id])
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])

    versions = db.relationship(
        "DocumentVersion", backref="document", lazy="dynamic",
        cascade="all, delete-orphan", order_by="DocumentVersion.version_number",
    )

    @property
    def latest_version(self):
        return self.versions.order_by(None).order_by(db.desc("version_number")).first()

    @property
    def tag_list(self):
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    def __repr__(self):
        return f"<Document {self.title}>"


class DocumentVersion(db.Model):
    """One physical uploaded file for a Document, e.g. v1, v2, Final."""

    __tablename__ = "document_versions"
    __table_args__ = (db.UniqueConstraint("document_id", "version_label", name="uq_doc_version_label"),)

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)

    version_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3... increments; "Final" tracked via label
    version_label = db.Column(db.String(30), nullable=False)  # "v1", "v2", "Final"

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)  # random/safe name on disk
    file_size = db.Column(db.Integer)  # bytes
    mime_type = db.Column(db.String(120))

    notes = db.Column(db.String(255))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    download_count = db.Column(db.Integer, default=0, nullable=False)

    uploaded_by = db.relationship("User")

    def __repr__(self):
        return f"<DocumentVersion {self.document_id}:{self.version_label}>"
