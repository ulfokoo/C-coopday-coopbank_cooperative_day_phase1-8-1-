from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from app.models.task import TASK_PRIORITIES, TASK_STATUSES


class TaskForm(FlaskForm):
    title = StringField("Task Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    cooperative_day_id = SelectField("Cooperative Day", coerce=int, validators=[DataRequired()])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    team_id = SelectField("Team", coerce=int, validators=[Optional()])
    assigned_user_id = SelectField("Assigned To", coerce=int, validators=[Optional()])
    priority = SelectField("Priority", choices=[(p, p) for p in TASK_PRIORITIES])
    status = SelectField("Status", choices=[(s, s) for s in TASK_STATUSES])
    percent_complete = IntegerField("% Complete", validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    start_date = DateField("Start Date", validators=[Optional()])
    due_date = DateField("Due Date", validators=[Optional()])
    submit = SubmitField("Save Task")


class TaskCommentForm(FlaskForm):
    comment = TextAreaField("Add Comment", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Post Comment")
