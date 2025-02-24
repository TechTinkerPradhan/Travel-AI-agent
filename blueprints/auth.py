# blueprints/auth.py

import os
import requests
from flask import Blueprint, redirect, url_for, render_template, request, session
from flask_login import login_user, current_user, logout_user
from google_auth_oauthlib.flow import Flow
from app import db
from models.user import User

auth = Blueprint('auth', __name__, template_folder='../templates')


@auth.route('/login')
def login():
    """Renders your login page with the 'Sign in with Google' button."""
    # If the user is already logged in, redirect them to the main page
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template("login.html")  # Your login.html


@auth.route('/google_login')
def google_login():
    """
    Initiates Google OAuth flow with short scopes: 'openid', 'email', 'profile'.
    Then user is redirected to Google's consent page.
    """
    # Hardcode your callback route
    redirect_uri = "https://ai-travel-buddy-bboyswagat.replit.app/auth/google_callback"

    # Build Flow with short scope strings
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
                "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        },
        scopes=["openid", "email", "profile"]  # short scope style
    )

    flow.redirect_uri = redirect_uri

    authorization_url, state = flow.authorization_url(
        access_type='offline', include_granted_scopes='true', prompt='consent')

    # Store state in session
    session['oauth_state'] = state
    return redirect(authorization_url)


@auth.route('/callback')
def callback():
    """
    Google OAuth callback. Exchanges 'code' for tokens and fetches user info.
    Then logs in / registers user in local DB.
    """
    # Retrieve state
    state = session.get('oauth_state')
    if not state:
        return "Missing OAuth state, or session expired", 400

    # Build Flow again with same scopes
    redirect_uri = "https://yourapp.repl.co/auth/callback"
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
                "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        },
        scopes=["openid", "email", "profile"],  # same short scopes
        state=state)
    flow.redirect_uri = redirect_uri

    # Finish OAuth handshake
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Now we can get user info. We'll call Google userinfo endpoint using short scope approach:
    # For 'profile'/'email', we can use the token to get user info from an endpoint like:
    creds = flow.credentials
    token = creds.token

    # You can use either the old "v2" userinfo or the OIDC "userinfo" endpoint:
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    # or "https://openidconnect.googleapis.com/v1/userinfo"

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(userinfo_url, headers=headers)
    if response.status_code != 200:
        return f"Failed to retrieve user info: {response.text}", 400

    google_user = response.json()
    # google_user should have "email", "id" or "sub", "picture", "name", etc.

    email = google_user.get('email')
    google_id = google_user.get('id') or google_user.get('sub')
    if not email:
        return "Unable to retrieve email from Google", 400

    # Check or create user in DB
    existing_user = User.query.filter_by(email=email).first()
    if not existing_user:
        # Create user
        new_user = User(email=email, google_id=google_id)
        db.session.add(new_user)
        db.session.commit()
        existing_user = new_user

    # Log the user in
    login_user(existing_user)
    return redirect(url_for('index'))  # or wherever your main AI page is


@auth.route('/logout')
def logout():
    """Logout current user."""
    logout_user()
    return redirect(url_for('auth.login'))
