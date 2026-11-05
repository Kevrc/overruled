"""Models behind the bots: Claude in headless mode, or a local Ollama model. None of them get tools,
so a bot can only return text, and the clerk checks that text."""
import asyncio, json, logging, os, re, tempfile
import httpx

OFFLINE = os.environ.get("OVERRULED_OFFLINE") == "1"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = 120


async def ask(system: str, prompt: str, model: str, offline: str) -> tuple[str, float]:
    """Returns the reply and its estimated API cost. `offline` is the scripted line for runs without Claude."""
    if OFFLINE:
        return offline, 0.0
    with tempfile.TemporaryDirectory() as empty:  # an empty folder, so no project files reach the model
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "--model", model, "--tools", "", "--no-session-persistence", "--output-format", "json",
            "--system-prompt", system, cwd=empty, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), 180)
    if proc.returncode != 0:
        raise RuntimeError(err.decode()[:300] or out.decode()[:300])
    data = json.loads(out)
    return data["result"].strip(), float(data.get("total_cost_usd") or 0)


async def ask_local(system: str, prompt: str, model: str) -> str:
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as h:
        r = await h.post(f"{OLLAMA}/api/chat", json={"model": model, "stream": False, "think": False, "format": "json",
                                                     "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
        r.raise_for_status()
    return re.sub(r"<think>.*?</think>", "", r.json()["message"]["content"], flags=re.S).strip()


async def ask_juror(system: str, prompt: str, spec: str, offline: str, fallback: str = "haiku") -> tuple[str, float, str]:
    """Returns the reply, its cost, and the model that really answered, so the verdict can't overstate who voted."""
    if OFFLINE:
        return offline, 0.0, "scripted"
    if spec.startswith("ollama:"):
        model = spec.removeprefix("ollama:")
        try:
            return await ask_local(system, prompt, model), 0.0, f"{model} (local)"
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logging.warning("ollama unavailable, using %s: %s", fallback, e)
            reply, cost = await ask(system, prompt, fallback, offline)
            return reply, cost, f"{fallback} (Ollama unavailable)"
    reply, cost = await ask(system, prompt, spec, offline)
    return reply, cost, spec
