from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

from app.models.communication import COMMUNICATION_TYPES, COMMUNICATION_STATUSES

# Kept in sync with config.ALLOWED_EXTENSIONS — see app/documents/forms.py for
# the same pattern; app.utils.files.allowed_file is the real server-side guard.
_ALLOWED_EXT = ["pdf", "doc", "docx", "png", "jpg", "jpeg", "gif", "mp4", "mov", "zip"]


class CommunicationForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    communication_type = SelectField("Type", choices=[(t, t) for t in COMMUNICATION_TYPES])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    team_id = SelectField("Responsible Team", coerce=int, validators=[Optional()])
    responsible_user_id = SelectField("Responsible Person", coerce=int, validators=[Optional()])
    description = TextAreaField("Description", validators=[Optional()])
    target_audience = StringField("Target Audience", validators=[Optional(), Length(max=255)])
    platform = StringField("Platform", validators=[Optional(), Length(max=120)])
    planned_date = DateField("Planned Date", validators=[Optional()])
    publication_date = DateField("Publication Date", validators=[Optional()])
    status = SelectField("Status", choices=[(s, s) for s in COMMUNICATION_STATUSES])
    file = FileField("Attachment", validators=[Optional(), FileAllowed(_ALLOWED_EXT, "That file type is not allowed.")])
    submit = SubmitField("Save")
