#!/usr/bin/env python3
"""
Robinhood Agentic Trading MCP - Auth & Tool Discovery

This script:
1. Registers a dynamic OAuth client with Robinhood's MCP endpoint
2. Opens a browser for you to log in and authorize
3. Captures the auth code via a local callback server
4. Exchanges for an access token
5. Connects to the MCP endpoint and lists available tools

Usage: python3 auth_and_discover.py
"""

import json
import hashlib
import secrets
import base64
import urllib.parse
import webbrowser
import http.server
import threading
import time
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── Config ──────────────────────────────────────────────────────────────
MCP_URL = "https://agent.robinhood.com/mcp/trading"
REGISTER_URL = "https://agent.robinhood.com/oauth/trading/register"
AUTH_URL = "https://robinhood.com/oauth"
TOKEN_URL = "https://api.robinhood.com/oauth2/token/"
CALLBACK_PORT = 8888
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"

# ── Step 1: Dynamic Client Registration ─────────────────────────────────
def register_client():
    print("[1/5] Registering OAuth client...")
    data = json.dumps({
        "client_name": "Trading Pipeline Agent",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none"
    }).encode()
    
    req = Request(REGISTER_URL, data=data, headers={"Content-Type": "application/json"})
    resp = urlopen(req)
    result = json.loads(resp.read())
    print(f"  ✓ Client ID: {result['client_id']}")
    return result["client_id"]

# ── Step 2: PKCE Challenge ───────────────────────────────────────────────
def generate_pkce():
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge

# ── Step 3: Local callback server to capture auth code ───────────────────
auth_code_result = {"code": None, "error": None}

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            auth_code_result["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>&#9989; Authorized!</h1><p>You can close this tab and return to the terminal.</p></body></html>")
        elif "error" in params:
            auth_code_result["error"] = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Error</h1><p>{auth_code_result['error']}</p></body></html>".encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Silence request logs

def start_callback_server():
    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), CallbackHandler)
    server.timeout = 120
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    return server, thread

# ── Step 4: Token exchange ───────────────────────────────────────────────
def exchange_token(client_id, code, verifier):
    print("[4/5] Exchanging auth code for access token...")
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier
    }).encode()
    
    req = Request(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        resp = urlopen(req)
        result = json.loads(resp.read())
        print(f"  ✓ Access token obtained (expires in {result.get('expires_in', '?')}s)")
        return result
    except HTTPError as e:
        body = e.read().decode()
        print(f"  ✗ Token exchange failed ({e.code}): {body}")
        return None

# ── Step 5: MCP Tool Discovery ──────────────────────────────────────────
def mcp_request(access_token, method, params=None, req_id=1):
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
    }
    if params:
        payload["params"] = params
    
    data = json.dumps(payload).encode()
    req = Request(MCP_URL, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    })
    resp = urlopen(req)
    return json.loads(resp.read())

def discover_tools(access_token):
    print("[5/5] Connecting to MCP and discovering tools...")
    
    # Initialize
    init_resp = mcp_request(access_token, "initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "trading-pipeline", "version": "0.1.0"}
    }, req_id=1)
    print(f"  ✓ MCP initialized: {json.dumps(init_resp.get('result', {}).get('serverInfo', {}))}")
    
    # Send initialized notification
    notify_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }).encode()
    req = Request(MCP_URL, data=notify_payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    })
    try:
        urlopen(req)
    except:
        pass  # Notifications don't always return responses
    
    # List tools
    tools_resp = mcp_request(access_token, "tools/list", {}, req_id=2)
    tools = tools_resp.get("result", {}).get("tools", [])
    
    print(f"\n{'='*60}")
    print(f"  ROBINHOOD MCP TOOLS ({len(tools)} available)")
    print(f"{'='*60}\n")
    
    for tool in tools:
        name = tool.get("name", "?")
        desc = tool.get("description", "No description")
        schema = tool.get("inputSchema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])
        
        print(f"  ◆ {name}")
        print(f"    {desc}")
        if props:
            print(f"    Parameters:")
            for pname, pinfo in props.items():
                req_mark = " (required)" if pname in required else ""
                ptype = pinfo.get("type", "any")
                pdesc = pinfo.get("description", "")
                print(f"      - {pname}: {ptype}{req_mark} — {pdesc}")
        print()
    
    # Save tools to JSON for reference
    output_path = "/Users/chris/code/trading-pipeline/robinhood-mcp/tools.json"
    with open(output_path, "w") as f:
        json.dump(tools, f, indent=2)
    print(f"  Tools saved to {output_path}")
    
    return tools

# ── Main ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Robinhood Agentic Trading MCP — Auth & Discovery")
    print("=" * 60)
    print()
    
    # Register client
    client_id = register_client()
    
    # Generate PKCE
    verifier, challenge = generate_pkce()
    
    # Start callback server
    print("[2/5] Starting local auth server...")
    server, thread = start_callback_server()
    print(f"  ✓ Listening on localhost:{CALLBACK_PORT}")
    
    # Build auth URL
    state = secrets.token_urlsafe(32)
    auth_params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": "internal",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256"
    })
    auth_url = f"{AUTH_URL}?{auth_params}"
    
    # Open browser
    print(f"\n[3/5] Opening browser for Robinhood login...")
    print(f"  If it doesn't open, go to:\n  {auth_url}\n")
    webbrowser.open(auth_url)
    
    # Wait for callback
    print("  Waiting for authorization (up to 2 minutes)...")
    thread.join(timeout=120)
    
    if auth_code_result["error"]:
        print(f"\n  ✗ Authorization error: {auth_code_result['error']}")
        sys.exit(1)
    
    if not auth_code_result["code"]:
        print("\n  ✗ Timed out waiting for authorization")
        sys.exit(1)
    
    print(f"  ✓ Authorization code received")
    
    # Exchange for token
    token_data = exchange_token(client_id, auth_code_result["code"], verifier)
    if not token_data:
        sys.exit(1)
    
    # Save token for later use
    token_path = "/Users/chris/code/trading-pipeline/robinhood-mcp/token.json"
    with open(token_path, "w") as f:
        json.dump({
            "client_id": client_id,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type"),
        }, f, indent=2)
    print(f"  Token saved to {token_path}")
    
    # Discover tools
    discover_tools(token_data["access_token"])
    
    print(f"\n{'='*60}")
    print("  Done! Token saved. Ready to integrate with pipeline.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
