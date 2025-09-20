from eduvision_mvp.app import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student/company
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)  # OTP verify flag
