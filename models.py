from app import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    profile_pic = db.Column(db.String(200))
