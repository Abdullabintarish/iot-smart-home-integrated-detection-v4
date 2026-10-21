"""Screenshot running Streamlit pages through Edge/Chrome DevTools (no extra packages).

    python tools/cdp_screenshot.py <out_dir> <base_url> <path>[=<name>] ...

Expects a headless browser started with --remote-debugging-port=9222. Waits
until the page has rendered real content (Streamlit's skeleton gone and the
app idle), then captures the full page height. Uses the ``websockets`` client,
which Streamlit already depends on.
"""
import asyncio
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

from websockets.asyncio.client import connect

READY_JS = """(() => {
  const app = document.querySelector('[data-testid="stAppViewContainer"]');
  if (!app) return false;
  const skeleton = document.querySelector('[data-testid="stSkeleton"]');
  const running = document.querySelector('[data-testid="stStatusWidget"]');
  const text = (app.innerText || '').trim();
  return !skeleton && !running && text.length > 200;
})()"""


async def main(out_dir: Path, base: str, targets: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    port = os.environ.get("CDP_PORT", "9222")     # capture_screenshots.ps1 sets it
    tab = json.loads(urllib.request.urlopen(
        urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")).read())
    ws = await connect(tab["webSocketDebuggerUrl"], max_size=200 * 2**20)
    seq = 0

    async def call(method, **params):
        nonlocal seq
        seq += 1
        await ws.send(json.dumps({"id": seq, "method": method, "params": params}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == seq:
                return msg.get("result", {})

    await call("Page.enable")
    await call("Emulation.setDeviceMetricsOverride", width=1500, height=1000,
               deviceScaleFactor=1, mobile=False)
    for t in targets:
        path, _, name = t.partition("=")
        name = name or (path.strip("/") or "home")
        await call("Page.navigate", url=base.rstrip("/") + "/" + path.lstrip("/"))
        ready = False
        for _ in range(120):                      # up to 60 s
            await asyncio.sleep(0.5)
            r = await call("Runtime.evaluate", expression=READY_JS, returnByValue=True)
            if r.get("result", {}).get("value"):
                ready = True
                break
        await asyncio.sleep(2.0)                  # let charts finish drawing
        h = await call("Runtime.evaluate", returnByValue=True, expression=
                       "Math.max(document.body.scrollHeight, ...[...document.querySelectorAll('section.main, [data-testid=stMain]')].map(e => e.scrollHeight))")
        height = min(int(h.get("result", {}).get("value") or 2400) + 40, 9000)
        await call("Emulation.setDeviceMetricsOverride", width=1500, height=height,
                   deviceScaleFactor=1, mobile=False)
        await asyncio.sleep(1.0)
        # The viewport already spans the full page; capturing "beyond" it
        # shifts the fixed sidebar out of frame.
        shot = await call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        (out_dir / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))
        print(f"{name}: ready={ready} height={height}")
        await call("Emulation.setDeviceMetricsOverride", width=1500, height=1000,
                   deviceScaleFactor=1, mobile=False)
    await ws.close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2], sys.argv[3:]))
