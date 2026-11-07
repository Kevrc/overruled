# Overruled

**Every expense stands trial.**

Companies approve software renewals on one side of the story, then pay for idle seats, hidden price increases and missed deadlines. Overruled is an adversarial renewal review inside your team chat. Scout finds the renewals worth questioning. Bots argue both sides, a clerk with no AI strikes what can't be proven, jurors vote alone, and a person with the authority makes the call. Overruled never pays, cancels or sends anything.

Built for the Flip the Switch hackathon, Track 01: Best Business Workflow. The demo and tests run on simulated company data, and Overruled hasn't been used by a customer yet.

**[Watch the video](https://youtu.be/tFVlc39mc5g)** · **[Project page](https://kevrc.github.io/overruled/)** · **[Uncut real-time demo](docs/demo-uncut.mp4)** · **[Build story](BLOG.md)** · **[Replay a real trial in your browser](docs/replay/index.html)**, nothing to install.

The demo is one continuous take with Claude Code agents managed by Switch and a local juror, recorded in Mattermost. A script drives the two test accounts. The trailer is edited, with a camera moving across a capture of an earlier trial.

Slack has been tested too. A person uploaded a contract and sign-ins in the channel, and a trial ran on that upload with the managed agents and the local juror. Rulings and notices in Slack were tested in an earlier run, without managed agents.

![A verdict in Slack, and gavel refusing the person who asked for the expense](docs/slack-separation.png)

![The courtroom in Mattermost](docs/canal.png)

## The problem

Renewals get approved because the person who wants the tool is the only one who read the contract. Nobody argues the other side, a price increase sits in section 7.3, idle seats renew for another year, and the notice deadline passes unnoticed.

One AI opinion doesn't fix that. It's one confident voice, and it may invent the numbers.

## A real run

Everything below comes from one recorded run with Claude. The invented figures change from run to run.

| | |
|---|---|
| Scout found | Pipewave CRM: 21 of 50 seats active, notice due in 32 days |
| Asked to pay | $32,400, including an 8% automatic increase |
| The requester testified | "It brings in $500,000 a year". **Stricken** |
| The defense claimed | "$150,000+ annually". **Stricken** |
| A bot tried to rule | **Refused by Switch** |
| Jury | Condition |
| Ruling | Renew 23 seats for $14,904 |
| **Calculated saving** | **$17,496** |
| Estimated model cost | $0.09 |
| Next step | Draft notice and calendar reminder, ready for a person |

Scout also skipped a renewal whose notice deadline had passed, reported that $4,920 was gone for this term, flagged an app with no contract, and found software installed with no bill.

## Measured, not promised

| Clerk test | Result |
|---|---|
| Fabricated claims caught | 20 of 20 |
| Supported claims kept | 20 of 20 |
| Real defense speeches with an unsupported figure struck | 20 of 20 |
| Real prosecution speeches struck | 1 of 20, a real misquote |

| Simulated company: renewals with hidden traps | 26 of 26 |
| Contracts in wording the rules hadn't seen | 7 of 8, up from 1 of 8 |
| Planted instructions obeyed by the AI, in 10 runs | 0 |

The method, the bugs it exposed, and what these numbers don't prove are in [evals/RESULTS.md](evals/RESULTS.md).

## A full company, simulated

Harborline is a simulated company with a realistic mess: partial usage exports, mismatched bills, hidden increases, missed deadlines and overlapping tools. One command runs everything it has through Scout at once.

| | |
|---|---|
| Renewals reviewed | 26 |
| Sign-in records and installed apps read | 1,411 and 780 |
| Sent to trial | 15, worth $292,500 as written |
| Calculated saving found | $169,132 |
| Stopped for a person, with the reason | 9 |
| Overlapping tools flagged | 1 pair |

Run it with `uv run python -m evals.company`. Harborline was built with planted traps, so its saving isn't a forecast for a real company.

## Who does what

| Bot | Runs on | Job |
|---|---|---|
| `scout` | Code, no AI | Reads company exports, ranks renewals, reads contracts people bring, opens trials |
| `judge` | Code | Runs the trial, seats the jury, reveals the votes together |
| `clerk` | Code, no AI | Calculates the money, cites sources, strikes what can't be proven |
| `witness` | Claude Sonnet | States the evidence |
| `prosecutor` | Claude Sonnet | Holds the prosecution seat and argues against the expense |
| `defender` | Claude Sonnet | Holds the defense seat, fights like an internal champion, and isn't told the clerk's rules |
| `counsel` | Claude Sonnet | Waits on the bench and takes the defense seat if the defender drops |
| `prosecution-agent`, `defense-agent` | Claude Code, managed by Switch | Optional real agents that read the case files and argue. If one stays silent, the seat holder steps in |
| `jury-1` to `jury-3` | Claude Haiku and a local model | Vote alone as finance, team lead and risk |
| `gavel` | Code | Takes the ruling and enforces approval limits |
| `paralegal` | Code | Drafts the vendor notice and a calendar reminder, lists the seats to release, and follows up until a person confirms the notice went out |

People stay in the loop three ways:

- **The requester testifies**, and is held to the same evidence rules as the bots.
- **Anyone can paste a vendor offer.** It becomes evidence to weigh. Vendors never join the room, so they see no internal data.
- **A person rules.** The limits live in [policy.yaml](policy.yaml): a manager up to $15,000, the CFO above that. Whoever asked for the expense can't approve it.

## Why this needs Switch

| Switch feature | What it does here |
|---|---|
| Templates | [The court is a Switch template](templates/overruled.template.yaml): install provisions it and saves it to the workspace, so a team can start another court from Templates |
| Managed agents | With `setup_managed`, Switch's headless agent controller runs real Claude Code sessions, starts them when called, and shows their tool work in the chat |
| Exclusive roles | `prosecution` and `defense` are seats, not bots. The clerk calls `@defense`, and Switch delivers it to whoever holds the seat |
| Seat failover | If the defender goes offline, Switch frees the seat and `counsel` takes it. Nobody reassigns anything, and a test proves it |
| Agents in a shared room | Every hand-off between bots travels through the channel, so people watch the whole trial |
| Room groups and links | The court lives in an `Overruled` group. Each trial adds a nested jury group, with private rooms linked back to the court and archived after the verdict |
| Any model behind any agent | Each juror's model is set in [policy.yaml](policy.yaml). By default one vote runs on a local Ollama model, and the verdict names the model behind each vote |
| Room isolation | A juror can't read or post to another juror's room, and carries no memory between cases |
| Addressing policy | No agent can reach `gavel`. The server enforces it, not a prompt |
| Agent ownership | `gavel` has a different owner from the other bots, so they can't edit its policy |
| Verified sender identity | Approval limits rely on who Switch says is speaking, not on what the message claims |
| Visible refusals | When a bot tries to rule, the refusal appears in the channel |
| Attachments and room documents | Contracts come in through chat. The approval policy, rulings and notices stay in the room |
| Messaging bridge | The same template runs in Mattermost and Slack. Full trials ran in both. Microsoft Teams hasn't been tested |

Without Switch there's no sealed jury and no enforced ruling, only a long transcript.

**A design detail worth copying:** two agents with the same owner can change each other's addressing policy. We confirmed that on a live server, which is why `gavel` has its own owner.

## Built for a real company

- **Nothing happens by itself.** Overruled prepares the decision and the paperwork. People pay, cancel and send.
- **Every figure has a source.** The clerk cites the file and line, and only figures from the evidence reach the jury.
- **Deadlines count.** A saving can't be claimed once the notice date has passed.
- **Separation of duties.** Requesters can't approve their own expense.
- **Follow-through.** A conditional ruling lists the idle seats to release, longest idle first. If nobody confirms the notice, `paralegal` reminds the person who ruled 14, 7 and 1 days before the deadline, and once after it passes. Overruled removes nothing and sends nothing: people do that and confirm it, and the confirmation goes into the ledger.
- **Tamper-evident ledger.** Each ruling records the evidence hash, record, strikes, votes and approver, chained to the one before. Check it with `uv run python -m overruled.audit`.
- **Less data reaches the model.** Sign-in files stay out of the prompts, so employee names and emails aren't sent. Contracts and requests are sent to the model, so check that against your own policy.
- **A vote can stay on your machine.** A juror on Ollama doesn't send its prompt to any cloud provider.
- **No live credentials yet.** The first step is file exports, so a trial run needs no access to production systems.

### Rollout plan

Only phase 1 exists today. The others are the planned path, and each vendor's API and licensing would need checking first.

| Phase | Source | Purpose | Access |
|---|---|---|---|
| 1 (built) | CSV exports and uploaded contracts | Prove value with no access granted | None |
| 2 | Okta, Microsoft Entra or Google Workspace | Real usage per app | Read only |
| 3 | QuickBooks, Xero or NetSuite | Bills and renewals | Read only |
| 4 | Google Drive or SharePoint | Contracts | Read only, one folder |
| 5 (Slack built) | Slack or Microsoft Teams | Where teams already approve | One channel |
| 6 | NinjaOne or similar | Installed software, as a supporting signal | Read only |

## Run it

You need Docker and [uv](https://docs.astral.sh/uv/). Everything binds to localhost.

```bash
git clone https://github.com/Kevrc/overruled && cd overruled
scripts/install.sh
```

With Claude Code signed in:

```bash
scripts/start.sh
```

Without Claude, using scripted speeches and the same clerk, rooms and ruling code:

```bash
OVERRULED_OFFLINE=1 scripts/start.sh
```

The local juror is optional. To use it, install [Ollama](https://ollama.com) and run `ollama pull qwen3:4b`. If Ollama isn't running, that juror uses Claude and the verdict says so.

Open http://localhost:8365. The accounts are in `.state/access.txt`, and the channel is `courtroom`. Bots and people get their pictures from `assets/avatars`.

### Use real Claude Code agents

```bash
uv run python -m overruled.setup_managed
scripts/start.sh
```

This installs Switch's agent controller in `.controller`, enrolls this machine and creates `prosecution-agent` and `defense-agent`. They have their own owner, and setup stops if they would share one with `gavel`. Node 22.13 or later is required.

### Move it to Slack

Create a Slack app from [Switch's manifest](docs/slack-manifest.json), then run:

```bash
uv run python -m overruled.connect_slack
```

It reads the two tokens from your clipboard and sends them only to your local Switch server. It then links your Slack account as the owner of `gavel`, and provisions the same template in `#overruled-court`. In Slack, agent names don't autocomplete, so type them by hand.

### Try it

1. As `alex`: `@scout scan`
2. When the clerk asks, reply `@clerk testify It brings in $500,000 a year.`, or `@clerk proceed`
3. As `cfo`: `@gavel rule condition`
4. Read the draft notice and the list of seats to release. The next trial opens by itself
5. Once the notice is sent, tell the court: `@paralegal sent pipewave`

Other things to try:

| Try | What happens |
|---|---|
| `@judge put the Helpline renewal on trial` | A healthy tool: as `maya`, rule on it within her limit |
| `@judge put the Formly renewal on trial` | Refused: the notice deadline passed |
| `@clerk offer We can give you 15% off for 2 years.` during a trial | The offer becomes evidence |
| `@scout report` | A summary for finance: renewals coming up, saving available, notices missed, and saving decided against saving with a confirmed notice |
| `@paralegal export` | `decisions.csv`, one line per ruling with who confirmed the notice |
| `@judge reopen the Pipewave renewal` | Opens a ruled case again when there's new evidence |
| Attach a contract (PDF, Markdown or text) and a sign-in CSV, then `@scout intake app="Acme" renewal=2027-03-01` | Scout shows what it read and waits for `@scout confirm acme` |

To scan on a timer, start with `OVERRULED_SCAN_MINUTES=60`. Set `OVERRULED_EXPORTS` to use your own folder.

## Import a company's own data

```bash
uv run python -m overruled.importer imports/sample
```

| File | Where it would come from | What it adds |
|---|---|---|
| `software_inventory.csv` | An endpoint tool | Installed devices, and software with no bill on file |
| `signins.csv` | An identity provider | Who really uses each tool |
| `bills.csv` | Accounting | Seats, price, renewal date and owner |
| `contracts/` | Your contract folder | The price increase and notice clauses, kept as exact quotes |

An app is skipped, with the reason, when its contract or sign-in data is missing or its numbers don't add up. Missing data is never treated as zero use. These CSV columns are this project's own sample format.

For one renewal, a person can attach files in the chat instead, with no access to company systems. `@scout intake` reads contracts as PDF, Markdown or text. For sign-ins, it reads the file above, an [Okta Application Usage report](https://help.okta.com/oie/en-us/content/topics/reports/app-usage-report.htm) or a [Microsoft 365 Apps usage report](https://learn.microsoft.com/en-us/graph/api/reportroot-getm365appuserdetail?view=graph-rest-1.0) covering at least 90 days. Their columns come from the vendors' documentation, not from a real company's file.

## Tests

```bash
uv run python -m evals.clerk_eval
uv run pytest tests
```

The trial tests need the court running offline, with a short testimony window: `OVERRULED_OFFLINE=1 OVERRULED_TESTIMONY_SECONDS=4 scripts/start.sh`.

To test the managed fallback, run `setup_managed`, start the court without its controller using `OVERRULED_OFFLINE=1 OVERRULED_TESTIMONY_SECONDS=2 OVERRULED_MANAGED_SECONDS=6 uv run python -m overruled.court`, then run `OVERRULED_SEAT_FALLBACK=1 uv run pytest tests/test_trial.py -k seat_holders`.

To test seat failover, start with `OVERRULED_DOWN=defender` as well, wait for counsel to take the seat, and run `OVERRULED_FAILOVER=1 uv run pytest tests/test_trial.py -k counsel`.

## Limits

- **A calculated saving isn't guaranteed.** It depends on the input files and on the contract allowing fewer seats.
- **Not legal advice.** A draft notice needs review by a person, and by legal where it matters.
- **The clerk checks figures and quotes.** A false claim with neither can reach the jury, and a person still rules.
- **PDFs aren't read yet.** Contracts must be text or Markdown.
- **Contract reading can fail.** Clear contracts use pattern rules and unclear ones go to a model. Code checks every clause against the contract, and people must confirm what Scout read from a new one.
- **The benchmark is simulated and was used to fix the system,** so it isn't proof of accuracy on real contracts.
- **The sample cases use a fixed date,** 2026-11-04, so results are reproducible. A company's own files use the real date.
- **The seat list is visible to everyone in the court room,** because it's posted there as a file. Production should send it to the tool owner privately. Reminders only run while the court is running.
- **Contracts can be in Spanish, but the court speaks English.** Spanish contracts go to the model, and code checks each quote word for word. Trials and notices stay in English.
- **Only US dollars.** A contract priced in another currency stops with a reason. A plain `$` in a Spanish contract could mean pesos, so the person who confirms has to check it.
- **Scanned PDFs can't be read.** They stop the intake with a reason. Page headers and footers stay in the text, so a clause split by one goes to a person.
- **Okta exports list only people who signed in.** The report has to cover the last 90 days, and Scout asks the person to check that.
- **Approval limits trust chat usernames from the bridge.** Production needs them tied to the company directory.
- **Slack was tested with one person**, who owned `gavel`. Delegated approvals and requester separation were tested in Mattermost.
- **Vendor offers are unverified.** They come from the vendor and are labelled that way.
- **A trial is held in memory.** If the process restarts mid-trial, open it again.
- **Trial cost** is the API-equivalent estimate from Claude Code, and doesn't include managed agents.
- **Managed agents have real tools.** Their instructions limit them to reading the case files, and the clerk checks what they say, but a production setup should sandbox them.
- **No desktop app needed.** Managed agents run through Switch's headless controller, which runs the same agent host as Switch Console, so the court works on a server. Switch Console itself wasn't used.
- **The local model is weaker.** It's one vote of three, and its figures still pass through the clerk.
- **Only two model families were tested:** Claude and Qwen through Ollama.

Switch is pinned to 0.31.0. Its license is Apache 2.0 with a Commons Clause; this repo only downloads it. Overruled is under the [MIT license](LICENSE).
