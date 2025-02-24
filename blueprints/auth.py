import os
import requests
from flask import Blueprint, redirect, url_for, render_template, request, session, jsonify
from flask_login import login_user, current_user, logout_user
from google_auth_oauthlib.flow import Flow
from app import db
from models.user import User
from services.calendar_service import CalendarService

auth = Blueprint('auth', __name__, template_folder='../templates')

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
REPLIT_DOMAIN = "ai-travel-buddy-bboyswagat.replit.app"

# Initialize calendar service at blueprint level
calendar_service = CalendarService()

@auth.route('/login')
def login():
    """Renders login page with the 'Sign in with Google' button."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template("login.html")

@auth.route('/google_login')
def google_login():
    """
    Initiates Google OAuth flow for authentication (NOT calendar).
    Uses only authentication scopes: 'openid', 'email', 'profile'
    """
    # Auth-specific callback URL
    redirect_uri = f"https://{REPLIT_DOMAIN}/auth/google_callback"

    # Strictly use only authentication scopes
    auth_scopes = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ]

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        },
        scopes=auth_scopes
    )

    flow.redirect_uri = redirect_uri

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='false',  # Don't include additional scopes
        prompt='consent'
    )

    session['oauth_state'] = state
    return redirect(authorization_url)

@auth.route('/google_callback')
def google_callback():
    """
    Handle callbacks for both authentication and calendar authorization.
    """
    calendar_state = session.get('calendar_oauth_state')
    auth_state = session.get('oauth_state')

    # Handle calendar callback
    if calendar_state:
        try:
            if not calendar_service.check_availability():
                return jsonify({
                    "status": "error",
                    "message": "Calendar integration is not configured"
                }), 503

            creds = calendar_service.verify_oauth2_callback(request.url, calendar_state)
            session["google_calendar_credentials"] = creds
            session.pop("calendar_oauth_state", None)  # Clear the state
            return redirect(url_for("index"))
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # Handle authentication callback
    elif auth_state:
        try:
            redirect_uri = f"https://{REPLIT_DOMAIN}/auth/google_callback"
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=['openid', 'email', 'profile'],
                state=auth_state
            )

            flow.redirect_uri = redirect_uri
            flow.fetch_token(authorization_response=request.url)
            credentials = flow.credentials

            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {credentials.token}"}
            response = requests.get(userinfo_url, headers=headers)

            if response.status_code != 200:
                return f"Failed to get user info: {response.text}", 400

            userinfo = response.json()
            email = userinfo.get('email')
            if not email:
                return "Could not get user email", 400

            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    email=email,
                    name=userinfo.get('name'),
                    google_id=userinfo.get('id')
                )
                db.session.add(user)
                db.session.commit()

            login_user(user)
            return redirect(url_for('index'))

        except Exception as e:
            return f"Error in OAuth callback: {str(e)}", 400

    return "Invalid callback state", 400

@auth.route('/logout')
def logout():
    """Logout current user."""
    logout_user()
    return redirect(url_for('auth.login'))