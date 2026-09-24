from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

from app.models.correspondence import CORRESPONDENCE_CATEGORIES, CORRESPONDENCE_PRIORITIES, CORRESPONDENCE_STATUSES


class CorrespondenceForm(FlaskForm):
    reference_number = StringField("Reference Number", validators=[DataRequired(), Length(max=60)])
    category = SelectField("Category", choices=[(c, c) for c in CORRESPONDENCE_CATEGORIES])
    subject = StringField("Subject", validators=[DataRequired(), Length(max=255)])
    from_party = StringField("From", validators=[Optional(), Length(max=150)])
    to_party = StringField("To", validators=[Optional(), Length(max=150)])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    date_received = DateField("Date Received", validators=[Optional()])
    date_sent = DateField("Date Sent", validators=[Optional()])
    responsible_user_id = SelectField("Responsible Person", coerce=int, validators=[Optional()])
    priority = SelectField("Priority", choices=[(p, p) for p in CORRESPONDENCE_PRIORITIES])
    status = SelectField("Status", choices=[(s, s) for s in CORRESPONDENCE_STATUSES])
    response_deadline = DateField("Response Deadline", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save Correspondence")
