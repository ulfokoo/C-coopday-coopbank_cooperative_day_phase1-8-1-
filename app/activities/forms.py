from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, TimeField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

from app.models.activity import ACTIVITY_TYPES, ACTIVITY_STATUSES


class ActivityForm(FlaskForm):
    name = StringField("Activity Name", validators=[DataRequired(), Length(max=200)])
    activity_type = SelectField("Activity Type", choices=[(t, t) for t in ACTIVITY_TYPES], validators=[Optional()])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    team_id = SelectField("Responsible Team", coerce=int, validators=[Optional()])
    responsible_user_id = SelectField("Responsible Person", coerce=int, validators=[Optional()])
    activity_date = DateField("Date", validators=[Optional()])
    start_time = TimeField("Start Time", validators=[Optional()])
    end_time = TimeField("End Time", validators=[Optional()])
    location = StringField("Location", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional()])
    requirements = TextAreaField("Requirements", validators=[Optional()])
    budget_reference = StringField("Budget Reference", validators=[Optional(), Length(max=120)])
    status = SelectField("Status", choices=[(s, s) for s in ACTIVITY_STATUSES])
    submit = SubmitField("Save Activity")


class ActivityParticipantForm(FlaskForm):
    user_id = SelectField("Staff Member", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Add Participant")
