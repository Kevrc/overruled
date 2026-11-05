"""Exports a finished trial from the channel into one page anyone can open, with nothing to install.

Usage: python -m overruled.replay docs/replay
"""
import base64, html, json, pathlib, re, sys
import httpx

from overruled.client import STATE

MM = "http://localhost:8365/api/v4"
PAGE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Overruled replay</title>
<style>:root{--bg:#f5f6f8;--c:#fff;--t:#16233d;--m:#6b7890}*{box-sizing:border-box}body{margin:0;background:var(--bg);font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial;color:var(--t)}
header{position:sticky;top:0;z-index:2;display:flex;gap:12px;align-items:center;background:#17375e;color:#fff;padding:12px 16px}header b{font-size:20px;color:#fff;letter-spacing:2px}header span{flex:1;color:#c8d3e8;font-size:14px}
button{font:inherit;font-weight:700;border:0;border-radius:8px;padding:8px 14px;background:#fff;color:#17375e;cursor:pointer}main{max-width:860px;margin:0 auto;background:var(--c);min-height:100vh;padding:16px}
.m{display:flex;gap:12px;padding:10px 0;animation:in .3s}.m img{width:40px;height:40px;border-radius:50%}.m div{min-width:0;flex:1}.n{font-weight:700}.n small{color:var(--m);font-weight:400;margin-left:6px}
table{border-collapse:collapse;margin:8px 0;display:block;overflow-x:auto}td,th{border:1px solid #d9dfe9;padding:5px 10px;text-align:left}code{background:#eef1f6;border-radius:4px;padding:1px 5px}blockquote{margin:6px 0;padding-left:10px;border-left:3px solid #d9dfe9}
del{color:var(--m)}p{margin:4px 0}.hit{background:#e6ecf5;border-radius:8px}@keyframes in{from{opacity:0;transform:translateY(10px)}}</style>
<header><b>OVERRULED</b><span>A real trial, replayed. Fictional company data, real model output.</span><button id=b>Play</button></header><main id=f></main>
<script>const D=__DATA__,f=document.getElementById('f'),b=document.getElementById('b');let i=0,t=null;
function md(s){const e=x=>x.replace(/&/g,'&amp;').replace(/</g,'&lt;');const inl=x=>e(x).replace(/~~(.+?)~~/g,'<del>$1</del>').replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\\*(.+?)\\*/g,'<i>$1</i>');
let o='',ls=s.split('\\n');for(let k=0;k<ls.length;k++){const l=ls[k];if(l.startsWith('|')){let r='<table>';while(k<ls.length&&ls[k].startsWith('|')){if(!/^\\|[-| ]+\\|$/.test(ls[k]))r+='<tr>'+ls[k].slice(1,-1).split('|').map(c=>'<td>'+inl(c.trim())+'</td>').join('')+'</tr>';k++}k--;o+=r+'</table>'}else if(l.startsWith('>'))o+='<blockquote>'+inl(l.replace(/^>\\s?/,''))+'</blockquote>';else if(l.trim())o+='<p>'+inl(l)+'</p>'}return o}
function show(m){const d=document.createElement('div');d.className='m'+(/STRICKEN|OVERRULED|SUSTAINED/.test(m.text)?' hit':'');d.innerHTML='<img alt="" src="'+m.img+'"><div><div class=n>'+m.who+(m.bot?'<small>bot</small>':'')+'</div>'+md(m.text)+'</div>';f.append(d);window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})}
function step(){if(i>=D.length){t=null;b.textContent='Replay';return}show(D[i]);i++;t=setTimeout(step,Math.min(4200,900+D[i-1].text.length*14))}
b.onclick=()=>{if(t){clearTimeout(t);t=null;b.textContent='Play';return}if(i>=D.length){i=0;f.innerHTML=''}b.textContent='Pause';step()};
if(new URLSearchParams(location.search).get('all')!==null){D.forEach(show);i=D.length;b.textContent='Replay'}else b.click()</script></html>"""


def main(out: str) -> None:
    access = (STATE / "access.txt").read_text()
    user, password = re.search(r"CFO: (\S+) / (\S+)", access).groups()
    h = httpx.Client(base_url=MM, timeout=30)
    r = h.post("/users/login", json={"login_id": user, "password": password})
    r.raise_for_status()
    h.headers["Authorization"] = f"Bearer {r.headers['Token']}"
    channel = next(c["id"] for c in h.get(f"/users/{r.json()['id']}/channels").json() if c["name"].startswith("courtroom"))
    posts = h.get(f"/channels/{channel}/posts", params={"per_page": 200}).json()["posts"].values()
    rows, names = [], {}
    avatars = pathlib.Path(__file__).parent.parent / "assets" / "avatars"
    for p in sorted(posts, key=lambda x: x["create_at"]):
        if p["type"] or not p["message"].strip() or p["root_id"] and "not permitted" not in p["message"]:
            continue
        name = names.setdefault(p["user_id"], h.get(f"/users/{p['user_id']}").json()["username"])
        if re.search(r"just tag|Mention @|Ping @|me when|to get started|mention @|anytime|if you need|to loop me|get my attention|Tag @", p["message"]):
            continue
        image = avatars / f"{name}.png"
        src = "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode() if image.exists() else ""
        if rows and "Reminder for" in rows[-1]["text"]:
            break  # one trial only: stop where the first one ends
        rows.append({"who": name, "bot": bool(p.get("props", {}).get("from_bot")) or name not in ("cfo", "alex", "maya"), "text": p["message"], "img": src})
    target = pathlib.Path(out)
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(PAGE.replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")))
    print(f"{len(rows)} messages written to {target / 'index.html'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/replay")
