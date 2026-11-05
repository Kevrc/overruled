"""Minimal Switch agent: events over WebSocket, messages over HTTP."""
import asyncio, json, logging, pathlib, re, uuid
import httpx, websockets

API = "http://localhost:8300"
STATE = pathlib.Path(__file__).parent.parent / ".state"
log = logging.getLogger("overruled")


def tables_to_lines(text: str) -> str:
    """Slack shows Markdown tables as raw pipes, so each row becomes a line."""
    lines = []
    for line in text.split("\n"):
        if re.fullmatch(r"\|[\s|:-]+\|", line.strip()):
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|") if c.strip()]
            line = "• " + ": ".join(cells[:2]) + "".join(f" · {c}" for c in cells[2:]) if cells else ""
        lines.append(line)
    return "\n".join(lines)


def load_agents() -> dict:
    return json.loads((STATE / "agents.json").read_text())


class Agent:
    def __init__(self, name: str, data: dict):
        self.name, self.id, self.key, self.rooms = name, data["id"], data["api_key"], data["rooms"]
        self.scope = data.get("scope", "single")  # "all" also covers rooms created after connecting
        self.conn = str(uuid.uuid4())
        self.slack = False
        self.http = httpx.AsyncClient(base_url=API, timeout=30, headers={"Authorization": f"Bearer {self.key}"})

    async def say(self, room: str, text: str) -> None:
        if self.slack:
            text = tables_to_lines(text)
        r = await self.http.post(f"/agents/{self.id}/message", json={"room_id": room, "content": text})
        r.raise_for_status()

    async def op(self, operation: str, **args) -> dict:
        r = await self.http.post(f"/agents/{self.id}/ops/{operation}", json=args,
                                 headers={"X-Switch-Connection-Id": self.conn})
        r.raise_for_status()
        return r.json()["result"]

    async def run(self, handle, on_connect=None) -> None:
        """`handle(room, payload)` only sees messages Switch marked as addressed to this agent."""
        url = f"ws://localhost:8300/agents/{self.id}/connection/ws?connection_id={self.conn}&scope={self.scope}&rooms={','.join(self.rooms)}"
        headers = {"Authorization": f"Bearer {self.key}"}
        seen: set[str] = set()
        cursor = 0
        while True:
            try:
                async with websockets.connect(url, additional_headers=headers, max_size=None) as ws:
                    log.info("%s connected", self.name)
                    if on_connect:
                        asyncio.create_task(self._safe_connect(on_connect))
                    async for raw in ws:
                        frame = json.loads(raw)
                        if isinstance(frame.get("id"), int):
                            cursor = frame["id"]
                        if frame.get("event") == "ping" or frame.get("type") == "ping":
                            await ws.send(json.dumps({"type": "pong", "cursor": cursor}))
                        elif frame.get("event") == "refused":
                            raise RuntimeError(f"Switch refused the connection: {frame['data']}")
                        elif frame.get("event") == "message":
                            p = frame["data"]["payload"]
                            # A message the policy refused still arrives, with addressed=False.
                            if p.get("addressed") is True and p["message_id"] not in seen:
                                seen.add(p["message_id"])
                                asyncio.create_task(self._safe(handle, frame["data"]["room_id"], p))
            except (OSError, websockets.ConnectionClosed) as e:
                # shortcut: messages missed while disconnected are not replayed, use start_at for production
                log.warning("%s reconnecting: %s", self.name, e)
                await asyncio.sleep(2)

    async def _safe_connect(self, on_connect) -> None:
        await asyncio.sleep(1)  # the op needs the connection to be open on the server
        try:
            await on_connect()
        except Exception:
            log.exception("%s could not finish connecting", self.name)

    async def _safe(self, handle, room, p) -> None:
        try:
            await handle(room, p)
        except Exception:
            log.exception("%s failed", self.name)
