from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

from app.models.document import DOCUMENT_TYPES, CONFIDENTIALITY_LEVELS

# Kept in sync with config.ALLOWED_EXTENSIONS; FileAllowed gives an early,
# friendly form error, while app.utils.files.allowed_file is the real
# server-side guard applied again at save time.
_ALLOWED_EXT = [
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "png", "jpg", "jpeg", "gif", "mp4", "mov", "zip", "csv", "txt",
]


class DocumentUploadForm(FlaskForm):
    """Create a brand-new Document plus its first (v1) file."""

    title = StringField("Document Title", validators=[DataRequired(), Length(max=200)])
    document_type = SelectField("Document Type", choices=[(t, t) for t in DOCUMENT_TYPES])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    task_id = SelectField("Related Task", coerce=int, validators=[Optional()])
    meeting_id = SelectField("Related Meeting", coerce=int, validators=[Optional()])
    instruction_id = SelectField("Related Instruction", coerce=int, validators=[Optional()])
    correspondence_id = SelectField("Related Correspondence", coerce=int, validators=[Optional()])
    procurement_request_id = SelectField("Related Procurement", coerce=int, validators=[Optional()])
    owner_id = SelectField("Owner", coerce=int, validators=[Optional()])
    confidentiality_level = SelectField("Confidentiality", choices=[(c, c) for c in CONFIDENTIALITY_LEVELS])
    description = TextAreaField("Description", validators=[Optional()])
    tags = StringField("Tags (comma-separated)", validators=[Optional(), Length(max=255)])
    file = FileField("File", validators=[FileRequired("Please choose a file to upload."), FileAllowed(_ALLOWED_EXT, "That file type is not allowed.")])
    version_notes = StringField("Version Notes", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Upload Document")


class DocumentMetadataForm(FlaskForm):
    """Edit an existing Document's metadata (no new file)."""

    title = StringField("Document Title", validators=[DataRequired(), Length(max=200)])
    document_type = SelectField("Document Type", choices=[(t, t) for t in DOCUMENT_TYPES])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    task_id = SelectField("Related Task", coerce=int, validators=[Optional()])
    meeting_id = SelectField("Related Meeting", coerce=int, validators=[Optional()])
    instruction_id = SelectField("Related Instruction", coerce=int, validators=[Optional()])
    correspondence_id = SelectField("Related Correspondence", coerce=int, validators=[Optional()])
    procurement_request_id = SelectField("Related Procurement", coerce=int, validators=[Optional()])
    owner_id = SelectField("Owner", coerce=int, validators=[Optional()])
    confidentiality_level = SelectField("Confidentiality", choices=[(c, c) for c in CONFIDENTIALITY_LEVELS])
    description = TextAreaField("Description", validators=[Optional()])
    tags = StringField("Tags (comma-separated)", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save Changes")


class DocumentVersionForm(FlaskForm):
    """Upload a new version (v2, v3, Final...) of an existing Document."""

    version_label = StringField("Version Label", validators=[DataRequired(), Length(max=30)], default="")
    file = FileField("File", validators=[FileRequired("Please choose a file to upload."), FileAllowed(_ALLOWED_EXT, "That file type is not allowed.")])
    notes = StringField("Version Notes", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Upload New Version")


class DocumentSearchForm(FlaskForm):
    """GET-only search/filter bar — CSRF not needed since it never mutates."""

    class Meta:
        csrf = False

    q = StringField("Keyword", validators=[Optional()])
    event_id = SelectField("Cooperative Day", coerce=int, validators=[Optional()])
    document_type = SelectField("Type", validators=[Optional()])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    status = SelectField("Status", validators=[Optional()])
