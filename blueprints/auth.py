import os
import requests
from flask import Blueprint, redirect, url_for, render_template, request, session, jsonify, flash
from flask_login import login_user, current_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length
from google_auth_oauthlib.flow import Flow
from app import db
from models import User

auth = Blueprint('auth', __name__, template_folder='../templates')

# Forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    name = StringField('Name', validators=[DataRequired()])

# Routes
@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login via email/password"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        flash('Invalid email or password', 'danger')

    return render_template('login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return render_template('register.html', form=form)

        user = User(
            email=form.email.data,
            username=form.name.data
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Registration successful!', 'success')
        return redirect(url_for('index'))

    return render_template('register.html', form=form)

@auth.route('/google_login')
def google_login():
    """Initiate Google OAuth flow"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    redirect_uri = f"https://{os.environ.get('REPLIT_DOMAIN')}/auth/google_callback"
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        },
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
    )

    flow.redirect_uri = redirect_uri
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['oauth_state'] = state
    return redirect(authorization_url)

@auth.route('/google_callback')
def google_callback():
    """Handle Google OAuth callback"""
    if not session.get('oauth_state'):
        return redirect(url_for('auth.login'))

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [f"https://{os.environ.get('REPLIT_DOMAIN')}/auth/google_callback"]
            }
        },
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile'],
        state=session['oauth_state']
    )

    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        response = requests.get(userinfo_url, headers={"Authorization": f"Bearer {credentials.token}"})
        userinfo = response.json()

        email = userinfo.get('email')
        if not email:
            flash('Could not get email from Google', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                username=userinfo.get('name', email.split('@')[0])
            )
            db.session.add(user)
            db.session.commit()

        login_user(user)
        flash('Successfully logged in with Google!', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        flash('Error during Google authentication', 'danger')
        return redirect(url_for('auth.login'))

@auth.route('/logout')
def logout():
    """Handle user logout"""
    logout_user()
    flash('Successfully logged out', 'success')
    return redirect(url_for('auth.login'))