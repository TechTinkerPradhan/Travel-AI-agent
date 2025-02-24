from flask import Blueprint, redirect, url_for, session, request, render_template
from flask_login import login_user, logout_user, login_required, current_user
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import json
import logging
from models.user import User
from app import db
from services.airtable_service import AirtableService

auth = Blueprint('auth', __name__)

# Configure Google OAuth
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
REPLIT_DOMAIN = "ai-travel-buddy-bboyswagat.replit.app"

# Initialize Airtable service
airtable_service = AirtableService()

@auth.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@auth.route('/google_login')
def google_login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [f"https://{REPLIT_DOMAIN}/auth/google_callback"]
            }
        },
        # Keep only authentication scopes, remove calendar scopes
        scopes=['openid', 'email', 'profile']
    )

    # Set the redirect URI using the configured domain
    flow.redirect_uri = f"https://{REPLIT_DOMAIN}/auth/google_callback"

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    session['state'] = state
    return redirect(authorization_url)

@auth.route('/google_callback')
def google_callback():
    # Verify state to prevent CSRF
    state = session.get('state')
    if not state or state != request.args.get('state'):
        return "Invalid state parameter", 400

    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [f"https://{REPLIT_DOMAIN}/auth/google_callback"]
                }
            },
            scopes=['openid', 'email', 'profile'],
            state=state
        )

        # Use the same redirect_uri as configured in flow
        flow.redirect_uri = f"https://{REPLIT_DOMAIN}/auth/google_callback"

        # Handle authorization response
        flow.fetch_token(authorization_response=request.url)

        # Get user info from Google
        credentials = flow.credentials
        try:
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, requests.Request(), GOOGLE_CLIENT_ID
            )
        except ValueError as e:
            logging.error(f"Error verifying Google token: {e}")
            return "Invalid token", 400

        email = id_info.get('email')
        name = id_info.get('name')
        google_id = id_info.get('sub')

        if not email or not google_id:
            logging.error("Missing email or google_id from token")
            return "Invalid user info", 400

        # Create or get user
        user = User.query.filter_by(email=email).first()
        is_new_user = False

        if not user:
            is_new_user = True
            user = User(
                email=email,
                name=name,
                google_id=google_id
            )
            db.session.add(user)
            db.session.commit()

        # If this is a new user, initialize their Airtable records
        if is_new_user:
            try:
                # Initialize user preferences with default values
                preferences = {
                    'budget': 'Moderate',  # Default budget preference
                    'travelStyle': 'Adventure'  # Default travel style
                }

                # Save initial preferences to Airtable
                airtable_service.save_user_preferences(
                    user_id=str(user.id),
                    preferences=preferences
                )

                logging.info(f"Initialized Airtable records for new user {user.id}")
            except Exception as e:
                logging.error(f"Error initializing Airtable records for user {user.id}: {e}")
                # Don't block login if Airtable initialization fails
                pass

        login_user(user)
        return redirect(url_for('index'))

    except Exception as e:
        logging.error(f"Error in google_callback: {e}", exc_info=True)
        return f"Authentication error: {str(e)}", 400

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))