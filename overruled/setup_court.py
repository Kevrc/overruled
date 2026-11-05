"""Creates the accounts, bots, policies and rooms. Runs once, after install.sh."""
import json, secrets, sys
import httpx
from dotenv import dotenv_values

from overruled.client import API, STATE

MM = "http://localhost:8365/api/v4"
AVATARS = STATE.parent / "assets" / "avatars"
TEMPLATE = STATE.parent / "templates" / "overruled.template.yaml"
PROFILE = {"connection_model": "always_on", "message_exchange": True, "pre_invocation_mediation": [],
           "post_invocation_mediation": [], "event_reporting": []}
BOTS = {"scout": "Finds renewals worth a trial", "judge": "Runs the trial", "clerk": "Checks every claim against the evidence, with no AI", "witness": "States the evidence",
        "prosecutor": "Argues against the expense", "defender": "Argues for the expense", "counsel": "Takes the defense seat if the defender goes offline",
        "paralegal": "Prepares notices for a person to send", "jury-1": "Finance juror", "jury-2": "Team lead juror", "jury-3": "Risk juror"}
# People only: no agent can reach gavel. Which person may rule is decided by policy.yaml.
PEOPLE_ONLY = {"rules": [{"users": "*", "agents": []}]}


def ok(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        sys.exit(f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text[:300]}")
    return r.json()


def upload_avatars(mm: httpx.Client, cfo: str) -> None:
    for image in sorted(AVATARS.glob("*.png")):
        name = cfo if image.stem == "cfo" else image.stem
        user = mm.get(f"/users/username/{name}")
        if user.status_code == 404:
            print(f"No Mattermost user for {name}, keeping the default picture")
            continue
        uid = ok(user)["id"]
        files = {"image": (image.name, image.read_bytes(), "image/png")}
        r = mm.post(f"/users/{uid}/image", files=files)
        if r.status_code >= 400:  # bot accounts take their picture through another route
            ok(mm.post(f"/bots/{uid}/icon", files=files))


def main() -> None:
    env = dotenv_values(STATE.parent / ".switch" / ".env")
    if (STATE / "agents.json").exists():
        sys.exit("The court already exists. Run scripts/install.sh --clean to start over.")
    STATE.mkdir(exist_ok=True)
    h = httpx.Client(base_url=API, timeout=30)
    ok(h.post("/gateway/auth/login", json={"email": env["GATEWAY_ADMIN_EMAIL"], "password": env["GATEWAY_ADMIN_PASSWORD"]}))
    personal = ok(h.post("/gateway/api-keys", json={"label": "cfo"}))["key"]

    def register(name: str, token: str, description: str) -> dict:
        return ok(h.post("/agents", headers={"Authorization": f"Bearer {token}"}, json={
            "name": name, "description": description, "connector_type": "custom", "integration_profile": PROFILE}))

    # Two owners on purpose: an agent can rewrite the policy of another agent with the same owner.
    bots = {n: register(n, env["AGENT_REGISTRATION_TOKEN"], d) for n, d in BOTS.items()}
    bots["gavel"] = register("gavel", personal, "Records the ruling of the responsible person")
    ok(h.put(f"/gateway/agents/{bots['gavel']['id']}/addressing-policy", json={"policy": PEOPLE_ONLY}))

    mm = httpx.Client(base_url=MM, timeout=30)
    r = mm.post("/users/login", json={"login_id": env["MATTERMOST_ADMIN_USER"], "password": env["MATTERMOST_ADMIN_PASSWORD"]})
    ok(r)
    mm.headers["Authorization"] = f"Bearer {r.headers['Token']}"
    password = secrets.token_urlsafe(18)
    team = ok(mm.get(f"/teams/name/{env['MATTERMOST_TEAM_NAME']}"))
    for name in ("alex", "maya"):
        person = ok(mm.post("/users", json={"email": f"{name}@court.local", "username": name, "password": password}))
        ok(mm.post(f"/teams/{team['id']}/members", json={"team_id": team["id"], "user_id": person["id"]}))

    # The court is a Switch template: the same file a team can run again from Templates.
    template = TEMPLATE.read_text()
    inputs = {"cfo": env["MATTERMOST_USER"], "policy": (STATE.parent / "policy.yaml").read_text()}
    made = ok(h.post("/gateway/rooms/from-yaml", json={"yaml": template, "inputs": inputs, "template_name": "Overruled court"}))
    (STATE / "provisioned.json").write_text(json.dumps(made, indent=1))
    court = next(r for r in made["rooms"] if r["room_name"] == "courtroom")
    ok(h.post("/gateway/templates", json={"name": "Overruled court", "description": "Every expense stands trial", "kind": "group", "content": template}))
    upload_avatars(mm, env["MATTERMOST_USER"])  # bot accounts exist in Mattermost once they join a room
    # People open trials through the judge and ask scout to scan.
    for name in ("judge", "scout", "clerk", "paralegal"):
        ok(h.put(f"/gateway/agents/{bots[name]['id']}/addressing-policy", json={"policy": {"rules": [{"users": "*", "agents": "*"}]}}))

    data = {n: {**b, "rooms": [court["room_id"]]} for n, b in bots.items()}
    # The judge opens a private room per juror for each trial, so they need connections that cover new rooms.
    data["judge"]["scope"] = "all"
    for n in ("jury-1", "jury-2", "jury-3"):
        data[n] |= {"rooms": [], "scope": "all"}
    data["_meta"] = {"court_room": court["room_id"], "cfo": env["MATTERMOST_USER"], "requester": "alex"}
    (STATE / "agents.json").write_text(json.dumps(data, indent=1))
    (STATE / "agents.json").chmod(0o600)
    access = STATE / "access.txt"
    access.write_text(f"Mattermost: http://localhost:8365\nCFO: {env['MATTERMOST_USER']} / {env['MATTERMOST_USER_PASSWORD']}\nRequester: alex / {password}\nManager: maya / {password}\n")
    access.chmod(0o600)
    print("Court ready. Accounts are in .state/access.txt")


if __name__ == "__main__":
    main()
