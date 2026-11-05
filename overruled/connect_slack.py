"""Moves the court to a Slack workspace. Tokens are read from the clipboard and only sent to the local Switch server.

Usage: python -m overruled.connect_slack
"""
import json, subprocess, sys
import httpx
from dotenv import dotenv_values

from overruled.client import API, STATE

ROOT = STATE.parent
ICONS = "https://raw.githubusercontent.com/Kevrc/overruled/main/assets/avatars"


def ok(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        sys.exit(f"{r.request.url.path}: {r.status_code} {r.text[:300]}")
    return r.json()


def ask_token(what: str, prefix: str) -> str:
    """Reads the token from the clipboard, so nothing has to be pasted into an invisible prompt."""
    while True:
        input(f"\n{what}\nCopy it, then press Enter here: ")
        token = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
        if token.startswith(prefix):
            subprocess.run(["pbcopy"], input="", text=True)
            print("Got it.")
            return token
        print(f"That isn't it. This token must start with {prefix}. Nothing was sent.")


def set_icons(h: httpx.Client, data: dict) -> None:
    """Slack shows agent pictures from public links, so these point at the published repo."""
    for name, agent in data.items():
        if name != "_meta":
            ok(h.put(f"/gateway/agents/{agent['id']}/icon", json={"icon_url": f"{ICONS}/{name}.png"}))


def main() -> None:
    env = dotenv_values(ROOT / ".switch" / ".env")
    h = httpx.Client(base_url=API, timeout=30)
    ok(h.post("/gateway/auth/login", json={"email": env["GATEWAY_ADMIN_EMAIL"], "password": env["GATEWAY_ADMIN_PASSWORD"]}))
    if len(sys.argv) == 3:  # the connection exists, and only the last steps are left
        finish(h, sys.argv[1], sys.argv[2])
        return
    bot = ask_token("STEP 1: open your Slack app at https://api.slack.com/apps, then OAuth & Permissions.\nPress Install to Workspace, then Allow. Find Bot User OAuth Token (xoxb-).", "xoxb-")
    app = ask_token("STEP 2: open Basic Information.\nApp-Level Tokens > Generate Token and Scopes. Name: switch. Scope: connections:write. Generate (xapp-).", "xapp-")
    checked = ok(h.post("/gateway/collaborations/setup/slack/check", json={"bot_token": bot, "app_token": app}))
    print(f"Tokens work for {checked['workspace_name']}.")

    bridge = ok(h.post("/gateway/collaborations", json={"bridge_type": "slack", "display_name": "Overruled Slack", "connection_config": {
        "bot_token": bot, "app_token": app, "workspace_id": checked["workspace_id"]}}))
    finish(h, bridge["bridge_id"], input("Your name in Slack: ").strip())


def finish(h: httpx.Client, bridge_id: str, me: str) -> None:
    people = ok(h.get(f"/gateway/collaborations/{bridge_id}/directory", params={"query": me}))["users"]
    if len(people) != 1:
        sys.exit(f"Found {len(people)} people for {me}: {', '.join(p['display_name'] for p in people)}")
    person = people[0]
    ok(h.post(f"/gateway/collaborations/{bridge_id}/identities", json={"external_user_id": person["external_user_id"], "username": person["username"]}))
    name = person["username"]
    made = ok(h.post("/gateway/rooms/from-yaml", json={
        "yaml": (ROOT / "templates" / "overruled.template.yaml").read_text(), "template_name": "Overruled court on Slack",
        "inputs": {"court": "overruled-court", "group_name": "Overruled on Slack", "bridge": "Overruled Slack", "cfo": name, "requester": name, "manager": name,
                   "policy": (ROOT / "policy.yaml").read_text()}}))
    court = made["rooms"][0]["room_id"]
    data = json.loads((STATE / "agents.json").read_text())
    for bot_name, agent in data.items():
        if bot_name != "_meta" and not bot_name.startswith("jury"):
            agent["rooms"] = [court]
    data["_meta"] |= {"court_room": court, "cfo": name, "chat": "slack"}
    (STATE / "agents.json").write_text(json.dumps(data, indent=1))
    set_icons(h, data)
    print(f"Done. Open the #overruled-court channel in Slack. You are {name}, and you own gavel.")


if __name__ == "__main__":
    main()
