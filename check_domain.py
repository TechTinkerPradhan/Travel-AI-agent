import os

# Print all relevant environment variables for debugging
print("\nAvailable Environment Variables:")
print("================================")
env_vars = ['REPLIT_SLUG', 'REPL_ID', 'REPLIT_DEV_DOMAIN', 'REPL_SLUG', 'REPL_OWNER']
for var in env_vars:
    value = os.environ.get(var)
    print(f"{var}: {value if value else 'Not set'}")

# Get primary domain components
replit_slug = os.environ.get('REPLIT_SLUG', '')
repl_id = os.environ.get('REPL_ID', '')
replit_domain = f"{replit_slug}.{repl_id}.repl.co" if replit_slug and repl_id else None

print("\nGoogle OAuth Configuration Settings:")
print("====================================")

if replit_domain:
    print(f"\nPrimary Domain Configuration:")
    print("===========================")
    print(f"Your Replit Domain: {replit_domain}")
    print("\nAdd these URLs to Google Cloud Console:")
    print("1. Authorized JavaScript origins:")
    print(f"https://{replit_domain}")
    print("\n2. Authorized redirect URIs:")
    print(f"https://{replit_domain}/auth/google_callback")

# Alternative domain check using REPLIT_DEV_DOMAIN
dev_domain = os.environ.get('REPLIT_DEV_DOMAIN')
if dev_domain:
    print("\nAlternative Domain Configuration:")
    print("================================")
    print(f"Using REPLIT_DEV_DOMAIN: {dev_domain}")
    print("\nAdd these URLs to Google Cloud Console:")
    print("1. Authorized JavaScript origins:")
    print(f"https://{dev_domain}")
    print("\n2. Authorized redirect URIs:")
    print(f"https://{dev_domain}/auth/google_callback")

if not (replit_domain or dev_domain):
    print("\nWarning: Could not determine Replit domain.")
    print("Make sure you're running this in a Replit environment.")
    print("Please run this script in your Replit environment to get the correct domain.")