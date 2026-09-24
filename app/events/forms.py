from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from app.models.event import EVENT_STATUSES


class CooperativeDayForm(FlaskForm):
    year = IntegerField("Year", validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    name = StringField("Event Name", validators=[DataRequired(), Length(max=150)])
    theme = StringField("Theme", validators=[Optional(), Length(max=255)])
    start_date = DateField("Start Date", validators=[Optional()])
    end_date = DateField("End Date", validators=[Optional()])
    location = StringField("Location", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional()])
    status = SelectField("Status", choices=[(s, s) for s in EVENT_STATUSES])
    coordinator_id = SelectField("Event Coordinator", coerce=int, validators=[Optional()])
    submit = SubmitField("Save Cooperative Day")
