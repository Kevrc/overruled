# I put software renewals on trial with twelve bots and Switch

Most software renewals get approved after one person reads the contract, and that person is usually the one who wants the tool. Nobody argues the other side. Idle seats renew for another year, a price increase sits in section 7.3, and the notice date passes.

I built **Overruled** for the Flip the Switch hackathon to fix that. It's a court for company spending that runs in a team chat. This post covers what it does, how I set it up on Switch and what I learned. If you've never used Switch, you can follow along.

- Video: https://youtu.be/qtupVpPbqAE
- Code: https://github.com/Kevrc/overruled
- Replay a recorded trial, nothing to install: https://kevrc.github.io/overruled/replay/

The demo below uses simulated company data. Nobody has used Overruled on a real company's own contracts yet, but I did replay one public audit, which I cover near the end.

## What it does

Scout finds a renewal before its notice deadline and opens a trial. A clerk, which is plain code and not AI, calculates the money and strikes any figure that isn't in the evidence. Two sides argue. Three jurors vote alone in private rooms. Then a person rules, and only a person can.

In the demo, the defense claims a CRM is worth $150,000 a year. The clerk strikes it because the number isn't in any file. The jury votes to condition the renewal, for a calculated saving of $17,496 on a fictional contract.

Overruled never pays, cancels or sends anything. It prepares a draft notice for a person to review.

## Why this needed Switch

I could have put all of this in one prompt: "Argue both sides, and wait for a human to approve." That's only a sentence, and a model can ignore a sentence.

The promise I wanted was stronger: **no agent can issue a ruling, even if it tries.** That has to live outside the model. Switch gives you shared rooms where agents and people talk, and the server enforces who can reach whom.

## Setting it up

You need Docker and [uv](https://docs.astral.sh/uv/). This starts Switch and Mattermost locally and creates the court:

```bash
git clone https://github.com/Kevrc/overruled && cd overruled
scripts/install.sh
scripts/start.sh
```

No Claude account? Run `OVERRULED_OFFLINE=1 scripts/start.sh` for scripted speeches with the same clerk, rooms and ruling code.

Open http://localhost:8365, sign in with an account from `.state/access.txt`, go to `courtroom` and send `@scout scan`.

Here are the Switch pieces behind that, in the order I'd learn them.

### 1. Each bot is its own agent

Each bot registers with Switch, and that's what gives it an identity in the room. This is shortened from `overruled/setup_court.py`:

```python
h.post("/agents", headers={"Authorization": f"Bearer {token}"}, json={
    "name": name, "description": description,
    "connector_type": "custom", "integration_profile": PROFILE})
```

### 2. The room is a template

The whole court lives in [one YAML file](templates/overruled.template.yaml): the group, the room, who's in it, the seats and a policy document. A team can start another court from Templates without touching code.

### 3. Seats belong to roles, not bots

Prosecution and defense are exclusive roles:

```yaml
roles:
  - name: defense
    exclusive: true
    instructions: Fight for the expense as its internal champion.
```

The clerk calls `@defense`, and Switch delivers that to whoever holds the seat. If the defender goes offline, Switch frees the seat and `counsel` takes it. I didn't have to write that handover logic, and a test proves it works.

### 4. Addressing policies make the rule real

This is the most important piece. It says people can reach `gavel`, and agents can't:

```python
PEOPLE_ONLY = {"rules": [{"users": "*", "agents": []}]}
h.put(f"/gateway/agents/{gavel_id}/addressing-policy", json={"policy": PEOPLE_ONLY})
```

When a bot tries to rule, the server refuses it, and the refusal shows up in the channel. That's great for a demo, and also for an audit.

Which person may rule is a separate question. `gavel` decides that from `policy.yaml`, using the sender identity Switch verifies rather than what the message claims.

### 5. Private rooms make a sealed jury

Each trial creates a jury group with one room per juror, linked back to the court and archived after the verdict. A juror can't read another juror's room. One juror can run on a local Ollama model, and the verdict names the model behind each vote.

### 6. Managed agents do real work

The prosecution and defense can also be real Claude Code sessions run by Switch:

```bash
uv run python -m overruled.setup_managed
scripts/start.sh
```

Switch shows their tool work in the chat. I didn't use Switch Console for this. I ran the headless agent controller, which needs `FEATURE_FLAGS_ENABLED=agent_management` and `CONTROLLER_TOKEN_SECRET` set on the server.

### 7. The same court works in Slack

`uv run python -m overruled.connect_slack` provisions the same template through Switch's Slack bridge. It uses Socket Mode, so you need both a bot token and an app-level token.

## What I learned

**An agent with the same owner can remove your policy.** My first version looked safe until I confirmed on a live server that an agent could clear the addressing policy of another agent with the same owner. Now `gavel` has a different owner, and setup checks it. If a policy protects something, check who owns the agents on both sides.

**Test the rule by attacking it.** The policy wasn't what caught that problem. I found it by having an agent try to get around the policy.

**Bots will happily talk forever.** A rejection that mentioned an agent triggered that agent, and they looped. Now agents ignore messages from other agents unless the step calls for them.

**Connect agents gradually.** Starting them all at once caused connection failures. A 0.5-second gap between them fixed it.

**Keep the math out of the model.** The clerk uses no AI, so I could measure it directly: it caught 20 of 20 hand-labelled fabricated claims and kept 20 of 20 supported ones. On fictional renewals with hidden traps, it went from 15 of 26 to 26 of 26. Contracts in unfamiliar wording scored 1 of 8 at first, which proved that pattern rules alone don't generalize. Unclear contracts now go to a model, and code rejects any clause that isn't in the contract word for word. That reached 7 of 8.

Those benchmarks were also used to fix the system, so they aren't blind tests. Real contracts will find new failures.

## A real public case

Simulated data only proves so much, so I looked for real numbers. In December 2024, Toronto's Auditor General reported that the city held 800,000 licences for its Public Digital Access system, and that management said 15,331 were in use.

I put those published figures on trial in Slack. Overruled calculated a difference of CA$726,019 a year, and all three jurors voted to condition the renewal. The clerk struck two figures from the defense that weren't in evidence.

This isn't a saving Toronto could have claimed. The City didn't use Overruled, the contract isn't public, and the audit describes a three-year purchase. The defense also made a fair point: these are public access accounts, so a count of accounts in use isn't the same as staff sign-ins. Still, it showed me the court holds up on real numbers. You can replay it with `@judge put the Toronto renewal on trial`.

## What isn't finished

- It hasn't had a customer or a security audit.
- Slack was tested with one person. Requester separation was tested in Mattermost.
- Approval limits trust usernames from the bridge, so production needs them tied to a company directory.
- Managed agents have real tools, so a production setup should sandbox them.

## Try it

Clone it, run `@scout scan` and try to break the rule. If you can get a ruling out of an agent, I want to know.

I built this with Claude Code as my coding partner. The [README](README.md) has everything else, and [evals/RESULTS.md](evals/RESULTS.md) explains the method and what the numbers don't prove.

#HowISwitch
