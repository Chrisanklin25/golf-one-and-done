"""
CRUS11TOUR Survivor Pool — Dashboard Update Script
Writes this week's recommendations to data.json and pushes to GitHub Pages.

Called by the Wednesday scheduled task with JSON data:
    python update_dashboard.py '<json_string>'

Or with --confirm-pick to record a pick:
    python update_dashboard.py --confirm-pick '<player_name>' '<tournament_name>' '<result>' <earnings>

JSON format for weekly update:
{
  "generated_at": "2026-04-29 08:00",
  "tournament": {
    "name": "The Players Championship",
    "purse": 25000000,
    "tier": 1,
    "type": "Players",
    "month": "Mar 2026"
  },
  "players_used": 6,
  "players_available": 34,
  "recommendations": [
    {
      "rank": 1,
      "name": "Tommy Fleetwood",
      "world_rank": 4,
      "odds_position": 3,
      "odds": "+550",
      "value_score": 1.33,
      "course_fit": 4,
      "form": 4,
      "injury_penalty": 0,
      "composite": 9.0,
      "notes": "Strong TPC Sawgrass history"
    }
  ],
  "save_for_later": [
    {"name": "Scottie Scheffler", "reason": "Masters in 3 weeks — save for $20M purse"}
  ],
  "injury_watch": [
    {"name": "Viktor Hovland", "concern": "Back tightness reported; monitor Tuesday"}
  ],
  "upcoming_tier1": [
    {"name": "Masters Tournament", "month": "Apr 2026", "purse": 20000000, "type": "Major", "weeks_away": 3}
  ]
}
"""

import json
import sys
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, 'data.json')

# ── GitHub settings ──
# Set these environment variables or edit here:
GITHUB_REPO = os.environ.get('GOLF_GITHUB_REPO', '')  # e.g. 'christopheranklin/golf-survivor'
GITHUB_TOKEN = os.environ.get('GOLF_GITHUB_TOKEN', '')  # personal access token


def load_data():
    """Load the current data.json."""
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
    """Save data.json locally."""
    with open(DATA_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {DATA_PATH}")


def push_to_github():
    """Push data.json to GitHub Pages repo via git."""
    if not GITHUB_REPO:
        print("No GITHUB_REPO configured — skipping push. Set GOLF_GITHUB_REPO env var.")
        return False

    try:
        # Try git push from the dashboard directory
        os.chdir(SCRIPT_DIR)
        subprocess.run(['git', 'add', 'data.json'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Weekly update'], check=True, capture_output=True)
        result = subprocess.run(['git', 'push'], check=True, capture_output=True, text=True)
        print(f"Pushed to GitHub: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git push failed: {e.stderr if hasattr(e, 'stderr') else e}")
        return False
    except Exception as e:
        print(f"Push error: {e}")
        return False


def confirm_pick(player_name, tournament_name, result, earnings):
    """Record a confirmed pick in data.json."""
    data = load_data()

    # Add to used_players
    data['used_players'].append({
        'name': player_name,
        'tournament': tournament_name,
        'result': result,
        'earnings': earnings
    })

    # Update the schedule entry
    for event in data.get('schedule', []):
        if event['name'] == tournament_name:
            event['status'] = 'done'
            event['pick'] = player_name
            event['result'] = result
            event['earnings'] = earnings
            break

    import datetime
    data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d')

    save_data(data)
    push_to_github()
    print(f"Confirmed: {player_name} at {tournament_name} → {result} (${earnings:,})")


def weekly_update(update_json):
    """Update this_week section with fresh recommendations."""
    data = load_data()

    # Replace the this_week section
    data['this_week'] = {
        'generated_at': update_json.get('generated_at'),
        'tournament': update_json.get('tournament', {}),
        'recommendations': update_json.get('recommendations', []),
        'save_for_later': update_json.get('save_for_later', []),
        'injury_watch': update_json.get('injury_watch', []),
        'upcoming_tier1': update_json.get('upcoming_tier1', [])
    }

    import datetime
    data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d')

    save_data(data)
    push_to_github()

    t_name = update_json.get('tournament', {}).get('name', 'Unknown')
    recs = update_json.get('recommendations', [])
    top = recs[0]['name'] if recs else 'N/A'
    print(f"Done! '{t_name}' recommendations written.")
    print(f"Top pick: {top}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Weekly update:  python update_dashboard.py '<json_string>'")
        print("  Confirm pick:   python update_dashboard.py --confirm-pick 'Player' 'Tournament' 'Result' earnings")
        sys.exit(1)

    if sys.argv[1] == '--confirm-pick':
        if len(sys.argv) < 6:
            print("Usage: python update_dashboard.py --confirm-pick 'Player Name' 'Tournament Name' 'Result' earnings")
            sys.exit(1)
        confirm_pick(
            player_name=sys.argv[2],
            tournament_name=sys.argv[3],
            result=sys.argv[4],
            earnings=int(sys.argv[5])
        )
    else:
        try:
            update_json = json.loads(sys.argv[1])
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            sys.exit(1)
        weekly_update(update_json)


if __name__ == '__main__':
    main()
