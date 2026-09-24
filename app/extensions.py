"""Central place for Flask extension instances.

Instances are created here (unbound) and initialised on the app in
app/__init__.py via init_app(). This avoids circular imports between
models, blueprints and the app factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
