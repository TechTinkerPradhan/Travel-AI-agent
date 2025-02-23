import os

# Get Replit domain components
replit_slug = os.environ.get('REPLIT_SLUG', '')
repl_id = os.environ.get('REPL_ID', '')
replit_domain = f"{replit_slug}.{repl_id}.repl.co" if replit_slug and repl_id else None

print("\nGoogle OAuth Configuration Settings:")
print("====================================")
print(f"Your Replit Domain: {replit_domain}")
if replit_domain:
    print("\nAdd these URLs to Google Cloud Console:")
    print("1. Authorized JavaScript origins:")
    print(f"https://{replit_domain}")
    print("\n2. Authorized redirect URIs:")
    print(f"https://{replit_domain}/api/calendar/oauth2callback")
else:
    print("\nWarning: Could not determine Replit domain.")
    print("Make sure you're running this in a Replit environment.")
