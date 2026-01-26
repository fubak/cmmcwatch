#!/usr/bin/env python3
"""
LinkedIn OAuth 2.0 Authorization Flow

Runs a local server to handle the OAuth callback and save credentials.
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import requests
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv, set_key

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8888/callback"

# OAuth endpoints
AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# Requested permissions
SCOPES = [
    "openid",
    "profile",
    "email",
    "w_member_social",  # Share on LinkedIn
]


class OAuthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""

    def do_GET(self):
        """Handle OAuth callback"""
        # Parse query parameters
        query = parse_qs(urlparse(self.path).query)

        if "code" in query:
            auth_code = query["code"][0]
            print(f"\n✅ Authorization code received: {auth_code[:20]}...")

            # Exchange code for access token
            token_data = self.exchange_code_for_token(auth_code)

            if token_data:
                # Save tokens to .env
                self.save_tokens(token_data)

                # Success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"""
                    <html>
                    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                        <h1 style="color: #0077B5;">✅ LinkedIn Connected!</h1>
                        <p>Your access token has been saved to .env</p>
                        <p>You can close this window now.</p>
                    </body>
                    </html>
                """
                )
            else:
                # Error response
                self.send_response(500)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"""
                    <html>
                    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                        <h1 style="color: #cc0000;">❌ Token Exchange Failed</h1>
                        <p>Check the console for error details.</p>
                    </body>
                    </html>
                """
                )

        elif "error" in query:
            error = query["error"][0]
            error_description = query.get("error_description", ["Unknown error"])[0]
            print(f"\n❌ Authorization error: {error}")
            print(f"   Description: {error_description}")

            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #cc0000;">❌ Authorization Denied</h1>
                    <p>{error_description}</p>
                </body>
                </html>
            """.encode()
            )

    def exchange_code_for_token(self, auth_code: str) -> dict:
        """Exchange authorization code for access token"""
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }

        try:
            response = requests.post(TOKEN_URL, data=data, timeout=10)
            response.raise_for_status()
            token_data = response.json()

            print(f"✅ Access token received (expires in {token_data.get('expires_in', 0)} seconds)")
            return token_data

        except requests.exceptions.RequestException as e:
            print(f"❌ Token exchange failed: {e}")
            if hasattr(e.response, "text"):
                print(f"   Response: {e.response.text}")
            return None

    def save_tokens(self, token_data: dict):
        """Save tokens to .env file"""
        env_path = PROJECT_ROOT / ".env"

        # Create .env from example if it doesn't exist
        if not env_path.exists():
            example_path = PROJECT_ROOT / ".env.example"
            if example_path.exists():
                import shutil

                shutil.copy(example_path, env_path)
                print(f"✅ Created .env from .env.example")

        # Save tokens
        set_key(env_path, "LINKEDIN_ACCESS_TOKEN", token_data["access_token"])

        if "refresh_token" in token_data:
            set_key(env_path, "LINKEDIN_REFRESH_TOKEN", token_data["refresh_token"])

        print(f"✅ Tokens saved to {env_path}")

    def log_message(self, format, *args):
        """Suppress default HTTP server logging"""
        pass


def start_oauth_flow():
    """Start the OAuth authorization flow"""
    # Check for required credentials
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Error: LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set in .env")
        print("\nSee scripts/linkedin_api_setup.md for instructions.")
        sys.exit(1)

    # Build authorization URL
    scope_str = " ".join(SCOPES)
    auth_url = (
        f"{AUTHORIZE_URL}?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope={scope_str}"
    )

    print("=" * 60)
    print("LinkedIn OAuth 2.0 Authorization")
    print("=" * 60)
    print(f"\n1. Opening authorization URL in your browser...")
    print(f"   {auth_url[:80]}...")
    print(f"\n2. Please authorize the app in your browser")
    print(f"3. You'll be redirected to http://localhost:8888/callback")
    print(f"4. Your access token will be saved to .env automatically")
    print("\n" + "=" * 60)

    # Open browser
    webbrowser.open(auth_url)

    # Start local server to handle callback
    print(f"\n🔄 Starting local server on port 8888...")
    server = HTTPServer(("localhost", 8888), OAuthHandler)

    print("✅ Server running. Waiting for authorization callback...")
    print("   (Press Ctrl+C to cancel)\n")

    try:
        # Handle one request (the OAuth callback)
        server.handle_request()
    except KeyboardInterrupt:
        print("\n\n❌ Authorization cancelled by user")
    finally:
        server.server_close()
        print("\n✅ Done!")


if __name__ == "__main__":
    start_oauth_flow()
