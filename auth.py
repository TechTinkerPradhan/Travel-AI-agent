import json
import os
from flask import Blueprint, redirect, request, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from oauthlib.oauth2 import WebApplicationClient
import requests
from app import db
from models import User

auth = Blueprint('auth', __name__, url_prefix='/auth')

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Initialize OAuth client
client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    try:
        return requests.get(GOOGLE_DISCOVERY_URL).json()
    except Exception as e:
        print(f"Error fetching Google configuration: {e}")
        return None

@auth.route("/login")
def login():
    # User is redirected to Google's OAuth page
    google_provider_cfg = get_google_provider_cfg()
    if not google_provider_cfg:
        flash("Error connecting to Google", "error")
        return redirect(url_for("index"))

    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.url_root.rstrip('/') + "/auth/google_callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@auth.route("/google_callback")
def callback():
    # Get authorization code from Google
    code = request.args.get("code")
    if not code:
        flash("Authentication failed - no code received", "error")
        return redirect(url_for("index"))

    try:
        # Fetch tokens from Google
        google_provider_cfg = get_google_provider_cfg()
        token_endpoint = google_provider_cfg["token_endpoint"]

        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=request.base_url,
            code=code,
        )

        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        client.parse_request_body_response(json.dumps(token_response.json()))

        # Get user info from Google
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        if userinfo_response.json().get("email_verified"):
            google_id = userinfo_response.json()["sub"]
            email = userinfo_response.json()["email"]
            name = userinfo_response.json().get("given_name", email.split('@')[0])
            picture = userinfo_response.json().get("picture", "")

            # Create or update user
            user = User.query.filter_by(google_id=google_id).first()
            if not user:
                user = User(
                    google_id=google_id,
                    name=name,
                    email=email,
                    profile_pic=picture
                )
                db.session.add(user)
                db.session.commit()

            # Begin user session
            login_user(user)
            return redirect(url_for("index"))
        else:
            flash("Google authentication failed - email not verified", "error")
            return redirect(url_for("index"))

    except Exception as e:
        flash(f"Failed to authenticate with Google: {str(e)}", "error")
        return redirect(url_for("index"))

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))