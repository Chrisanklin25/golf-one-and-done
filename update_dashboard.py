"""
CRUS11TOUR Survivor Pool — Dashboard Update Script
Writes this week's recommendations to data.json and pushes to GitHub Pages.

Called by the Wednesday scheduled task with JSON data:
    python update_dashboard.py '<json_string>'

Or with --confirm-pick to record/update a pick (upsert, no duplicates):
    python update_dashboard.py --confirm-pick '<player_name>' '<tournament_name>' '<result>' <earnings>

Or with --flag-login to flag a Splash Sports logout state on the dashboard:
    python update_dashboard.py --flag-login ['<optional custom message>']
"""

import json
import sys
import os
import base64
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, 'data.json')

# GitHub settings
GITHUB_REPO = 'chrisanklin25/golf-one-and-done'
GITHUB_BRANCH = 'main'
GITHUB_TOKEN = os.environ.get('GOLF_GITHUB_TOKEN', '')

# Load token from .env or .env.txt if not in environment
if not GITHUB_TOKEN:
    for env_name in ['.env', '.env.txt']:
        env_path = os.path.join(SCRIPT_DIR, env_name)
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('GOLF_GITHUB_TOKEN='):
                        GITHUB_TOKEN = line.strip().split('=', 1)[1].strip()
                        break
            if GITHUB_TOKEN:
                break


def load_data():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r') as f:
            return json.load(f)
    else:
        print(f"Warning: {DATA_PATH} not found, creating fresh.")
        return {
            "last_updated": None,
            "season": {"pool_name": "CRUS11TOUR", "total_events": 30, "players_in_pool": 40},
            "used_players": [],
            "schedule": [],
            "this_week": {
                "generated_at": None,
                "tournament": {},
                "recommendations": [],
                "save_for_later": [],
                "injury_watch": [],
                "upcoming_tier1": []
            }
        }


def save_data(data):
    with open(DATA_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {DATA_PATH}")


def push_to_github():
    """Push data.json to GitHub via the REST API. No git clone needed."""
    if not GITHUB_TOKEN:
        print("No GOLF_GITHUB_TOKEN configured. Add it to .env file.")
        return False

    try:
        import urllib.request
        import urllib.error

        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'golf-survivor-updater'
        }

        # Get current file SHA (required for updates)
        sha = None
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                existing = json.loads(resp.read().decode())
                sha = existing.get('sha')
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

        # Read and encode local data.json
        with open(DATA_PATH, 'r') as f:
            content = f.read()
        encoded = base64.b64encode(content.encode()).decode()

        # Push via Contents API
        payload = {
            'message': 'Weekly dashboard update',
            'content': encoded,
            'branch': GITHUB_BRANCH
        }
        if sha:
            payload['sha'] = sha

        req_body = json.dumps(payload).encode()
        req = urllib.request.Request(api_url, data=req_body, headers=headers, method='PUT')
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            print(f"Pushed to GitHub: {result['content']['html_url']}")
            return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if hasattr(e, 'read') else str(e)
        print(f"GitHub API error ({e.code}): {error_body}")
        return False
    except Exception as e:
        print(f"Push error: {e}")
        return False


def confirm_pick(player_name, tournament_name, result, earnings):
    """Record a confirmed pick in data.json. Upserts — updates existing entry if present, else appends."""
    data = load_data()

    # Upsert into used_players (avoid duplicates)
    updated_existing = False
    for p in data['used_players']:
        if p['name'] == player_name and p['tournament'] == tournament_name:
            p['result'] = result
            p['earnings'] = earnings
            updated_existing = True
            break
    if not updated_existing:
        data['used_players'].append({
            'name': player_name,
            'tournament': tournament_name,
            'result': result,
            'earnings': earnings
        })

    # Update the matching schedule event
    for event in data.get('schedule', []):
        if event['name'] == tournament_name:
            event['status'] = 'done'
            event['pick'] = player_name
            event['result'] = result
            event['earnings'] = earnings
            break

    # Clear any stale login-required banner once we've successfully recorded a pick
    if 'login_required' in data.get('this_week', {}):
        del data['this_week']['login_required']

    data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d')
    save_data(data)
    push_to_github()
    action = "Updated" if updated_existing else "Recorded"
    print(f"{action}: {player_name} at {tournament_name} -> {result} (${earnings:,})")


def flag_login_required(message=None):
    """Set a banner flag indicating Christopher needs to re-auth Splash Sports."""
    data = load_data()
    data.setdefault('this_week', {})
    data['this_week']['login_required'] = {
        'flagged_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'message': message or "Splash Sports session expired. Log in at https://app.splashsports.com/ so the next Wednesday run can pull last week's result automatically."
    }
    data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d')
    save_data(data)
    push_to_github()
    print("Login-required banner flagged.")


def clear_login_flag():
    """Remove the login-required banner once Christopher has re-authenticated."""
    data = load_data()
    if 'login_required' in data.get('this_week', {}):
        del data['this_week']['login_required']
        data['last_up