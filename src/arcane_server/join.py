"""The join page of a multiplayer server (GET /join): the server's address as a QR code for the Multiplayer app, the
multiplayer client, plus the plain address and the deep link, for the operator to show or share.

The address is the one the CDN and the battle server are handed out on (public_url.public_base_url):
ARCANE_PUBLIC_BASE_URL when set, else the address this page was opened at. The QR code holds the deep link
arcane://connect?url=<address>: the Multiplayer app's own scanner reads it (or a plain address), and a phone's camera app
opening it starts the Multiplayer app with the address filled in (the app registers the scheme).
Both check the server exactly like a typed address before saving it.

Multiplayer profile only: the Multiplayer app leaves PvP / KOTH / club war battles to the server's battle server, which a
single-player server does not run; the offline variant's server is the phone itself. The QR code is drawn here (segno), nothing external is loaded.
"""

from __future__ import annotations

import html
import io
from functools import lru_cache
from typing import TYPE_CHECKING
from urllib.parse import quote

import segno
from aiohttp import web
from yarl import URL

from arcane_server.public_url import public_base_url

if TYPE_CHECKING:
    from arcane_server.config import Settings

PATH = "/join"
QR_PATH = PATH + "/qr.png"
# the Multiplayer app's deep link (the app's intent filter registers it)
SCHEME, LINK_HOST = "arcane", "connect"
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def enabled(settings: "Settings") -> bool:
    return settings.profile == "multiplayer"


def deep_link(server_url: str) -> str:
    """arcane://connect?url=<server_url, percent-encoded>"""
    return f"{SCHEME}://{LINK_HOST}?url={quote(server_url, safe='')}"


@lru_cache(maxsize=32)
def qr_png(text: str) -> bytes:
    """`text` as a QR code PNG: ink on parchment (dark on light, so every scanner reads it), a 4-module quiet zone."""
    buf = io.BytesIO()
    segno.make(text, error="m", micro=False).save(buf, kind="png", scale=10, border=4, dark="#141433", light="#fbf7ec")
    return buf.getvalue()


def _headers() -> dict[str, str]:
    return {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; frame-ancestors 'none'"}


def setup(app: web.Application, settings: "Settings") -> None:
    if not enabled(settings):
        return

    async def page(request: web.Request) -> web.Response:
        return web.Response(text=render(public_base_url(request, settings)), content_type="text/html",
                            headers=_headers())

    async def qr(request: web.Request) -> web.Response:
        return web.Response(body=qr_png(deep_link(public_base_url(request, settings))), content_type="image/png",
                            headers=_headers())

    app.router.add_get(PATH, page)
    app.router.add_get(QR_PATH, qr)


def render(server_url: str) -> str:
    link = deep_link(server_url)
    e = html.escape
    host = URL(server_url).host or ""
    warning = ""
    if host in LOOPBACK or host.startswith("127."):
        warning = f"""<p class="warn">This page was opened at <b>{e(host)}</b>, so the code points at the device that
        scans it, not at this server. Open this page at the address players use (LAN, VPN or public name), or set
        <code>ARCANE_PUBLIC_BASE_URL</code>.<br>此頁是用 {e(host)} 開的，QR code 會指向掃描的手機本身。請用玩家連線的位址開啟此頁，
        或設定 <code>ARCANE_PUBLIC_BASE_URL</code>。</p>"""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<link rel="icon" href="data:,">
<title>Join the Arena</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <header>
    <p class="eyebrow">Multiplayer</p>
    <h1>Join the Arena</h1>
    <p class="sub">加入這座競技場</p>
  </header>
  {warning}
  <section class="card">
    <figure class="qr">
      <img src="{QR_PATH}" width="330" height="330" alt="QR code: {e(link)}">
    </figure>
    <div class="info">
      <h2>Server address <span>伺服器位址</span></h2>
      <p class="addr"><code>{e(server_url)}</code></p>
      <a class="primary" href="{e(link)}">Open in the Multiplayer app <span>在多人版 App 開啟</span></a>
      <a class="quiet" href="{QR_PATH}" download="arcane-join.png">Save the QR code <span>下載 QR code</span></a>
      <p class="link">Deep link 連結：<code>{e(link)}</code></p>
    </div>
  </section>
  <section class="steps">
    <h2>How to join <span>加入方式</span></h2>
    <ol>
      <li>Install <b>the Multiplayer app</b> and open it. <span>安裝並開啟多人版 App。</span></li>
      <li>Tap <b>Scan QR code</b> and point the camera at the code above, or scan it with the phone's camera app.
        <span>點「Scan QR code」對準上方的 QR code，或用手機相機掃描。</span></li>
      <li>On the phone itself: tap <b>Open in the Multiplayer app</b>, or type the address. <span>在手機上看這頁：點「在多人版 App
        開啟」，或手動輸入位址。</span></li>
    </ol>
    <p class="muted">the Multiplayer app checks the server before it saves the address. 儲存前多人版 App 會先確認伺服器可連線。</p>
  </section>
</main>
</body>
</html>
"""


# The Multiplayer app launcher's look: midnight ink, deep violet card with a gold hairline,
# starlight gold, parchment text. Original artwork only.
CSS = """
:root { --ink:#141433; --ink-glow:#1e1b4b; --violet:#2a1f5c; --gold:#e8b84a; --parchment:#f3ecda; --lavender:#a99bd6;
  --rose:#e06a86; }
* { box-sizing:border-box; }
html { background:var(--ink); }
body { margin:0; min-height:100vh; color:var(--parchment); font:16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto,
  "Noto Sans TC", sans-serif; background:
  radial-gradient(1.5px 1.5px at 12% 18%, #fff8 50%, transparent 51%),
  radial-gradient(1px 1px at 78% 12%, #e8b84aaa 50%, transparent 51%),
  radial-gradient(1.5px 1.5px at 88% 46%, #fff6 50%, transparent 51%),
  radial-gradient(1px 1px at 30% 72%, #a99bd6aa 50%, transparent 51%),
  radial-gradient(1.5px 1.5px at 62% 86%, #e8b84a88 50%, transparent 51%),
  radial-gradient(1px 1px at 6% 92%, #fff6 50%, transparent 51%),
  radial-gradient(ellipse at 50% 0%, var(--ink-glow), var(--ink) 70%) fixed; }
main { max-width:880px; margin:0 auto; padding:32px 16px 48px; }
header { text-align:center; margin-bottom:24px; }
.eyebrow { margin:0; color:var(--lavender); letter-spacing:.2em; text-transform:uppercase; font-size:13px; }
h1 { margin:4px 0 0; color:var(--gold); font:700 clamp(32px, 7vw, 48px)/1.1 Georgia, "Times New Roman", serif;
  letter-spacing:.02em; text-shadow:0 0 24px #e8b84a40; }
.sub { margin:4px 0 0; color:var(--lavender); }
h2 { margin:0 0 8px; font-size:18px; font-weight:600; }
h2 span, a span, li span { display:block; font-size:.85em; color:var(--lavender); font-weight:400; }
.card { display:flex; flex-wrap:wrap; gap:24px; align-items:center; padding:24px; border-radius:20px;
  background:linear-gradient(160deg, #2a1f5cee, #1e1b4bee); border:1px solid #e8b84a66;
  box-shadow:0 0 0 4px #e8b84a14, 0 24px 60px #0008; }
.qr { margin:0 auto; padding:10px; border-radius:16px; background:#fbf7ec; border:2px solid var(--gold);
  box-shadow:0 0 32px #e8b84a40; }
.qr img { display:block; width:min(330px, 72vw); height:auto; image-rendering:pixelated; }
.info { flex:1 1 300px; min-width:0; }
.addr code { font-size:clamp(18px, 4vw, 24px); color:var(--gold); word-break:break-all; }
code { font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
a.primary { display:block; margin:16px 0 8px; padding:12px 20px; border-radius:28px; background:var(--gold);
  color:var(--ink); text-align:center; text-decoration:none; font-weight:600; }
a.primary span { color:#141433b0; }
a.quiet { display:block; padding:8px 20px; text-align:center; color:var(--gold); text-decoration:none; }
a:focus-visible { outline:3px solid var(--parchment); outline-offset:3px; }
.link { margin:12px 0 0; font-size:13px; color:var(--lavender); word-break:break-all; }
.steps { margin-top:32px; padding:0 8px; }
ol { padding-left:24px; } li { margin:8px 0; }
.muted { color:var(--lavender); font-size:14px; }
.warn { padding:12px 16px; border-radius:12px; border:1px solid var(--rose); background:#e06a8622; }
"""
