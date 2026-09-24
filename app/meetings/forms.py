from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, TimeField, SubmitField
from wtforms.validators import DataRequired, Optional, Length


class MeetingForm(FlaskForm):
    title = StringField("Meeting Title", validators=[DataRequired(), Length(max=200)])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    meeting_date = DateField("Date", validators=[DataRequired()])
    meeting_time = TimeField("Time", validators=[Optional()])
    location = StringField("Location", validators=[Optional(), Length(max=255)])
    organizer_id = SelectField("Organizer", coerce=int, validators=[Optional()])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    agenda = TextAreaField("Agenda", validators=[Optional()])
    submit = SubmitField("Save Meeting")


class MinutesForm(FlaskForm):
    minutes = TextAreaField("Minutes", validators=[Optional()])
    submit = SubmitField("Save Minutes")


class ParticipantForm(FlaskForm):
    user_id = SelectField("Staff Member", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Add Participant")


class ActionPointForm(FlaskForm):
    description = TextAreaField("Action Point", validators=[DataRequired(), Length(max=1000)])
    responsible_user_id = SelectField("Responsible Person", coerce=int, validators=[Optional()])
    due_date = DateField("Due Date", validators=[Optional()])
    submit = SubmitField("Add Action Point")
