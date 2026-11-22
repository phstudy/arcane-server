"""RPC registry: maps the envelope's `rpc_name` to a typed handler.

Handlers are registered with `@rpc("name", RequestType)` and return a response protobuf message
(or an `RpcError`). The registry is the single list of implemented RPCs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from google.protobuf.message import Message

from google.protobuf import text_format

from arcane_server import wire_time
from arcane_server.clock import player_timezone
from arcane_server.proto import serverproto_pb2 as pb
from arcane_server.rpc_catalog import CATALOG

if TYPE_CHECKING:
    from arcane_server.game import Game

log = logging.getLogger(__name__)


class RpcError(Exception):
    def __init__(self, code: int = pb.ERROR, message: str = ""):
        super().__init__(message or pb.ResponseCode.Name(code))
        self.code = code
        self.message = message


@dataclass
class Session:
    """One authenticated client connection."""

    public_id: str
    game: "Game"
    # the host name this client reached the server at (app.client_host): a battle server address without a host
    # (ARCANE_BATTLE_SERVER=":port") is handed out on it
    client_host: str = "127.0.0.1"
    # dynamic messages to piggy-back on the next response
    pending_dynamic: list[pb.DynamicMessage] = field(default_factory=list)
    # per-connection state owned by handlers and AFTER_RPC hooks (e.g. what this client was last told), keyed by module
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def player(self) -> pb.Player:
        return self.game.player(self.public_id)

    def save(self) -> None:
        self.game.save(self.public_id)


def _ensure_inventory_delta(msg: Message) -> None:
    """Responses with an `inventory_delta` field always carry one, empty if nothing changed, as the client
    expects: it passes it straight to its inventory handlers, and its club inventory handler crashes on a missing
    one."""
    field = msg.DESCRIPTOR.fields_by_name.get("inventory_delta")
    if field is not None and field.message_type is not None and not msg.HasField("inventory_delta"):
        msg.inventory_delta.SetInParent()


# Request param is Any: each handler takes its concrete request type (checked against the catalog at startup).
Handler = Callable[[Session, Any], Awaitable[Message]]


@dataclass(frozen=True)
class RpcSpec:
    name: str
    request_type: type[Message]
    handler: Handler


REGISTRY: dict[str, RpcSpec] = {}
# Called after every handled RPC (session, rpc name), successful or not, in the player's timezone, before the
# response goes out: cross-cutting reactions that queue dynamic messages on session.pending_dynamic
# (arcane_server.tutorial: contextual messages, feature unlocks; handlers/special_offers.py: the current offers).
AFTER_RPC: list[Callable[[Session, str], None]] = []
# Watch what a handler changes: each watcher is called before the handler (in the player's timezone) and returns a
# finisher, or None when it has nothing to watch; the finisher gets the response of a successful handler before it is
# reported (conversions, wire time), so it can still add to the response's InventoryDelta. Items granted while the
# handler ran are counted in `inventory.granted()` (handlers/leaderboards.py: the character-upgrade contests).
WATCHERS: list[Callable[[Session], Callable[[Message], None] | None]] = []


def registry_problems() -> list[str]:
    """Handlers whose name/request type disagree with the client's RPC catalog (checked at startup)."""
    problems = []
    for name, spec in sorted(REGISTRY.items()):
        entry = CATALOG.get(name)
        if entry is None:
            problems.append(f"handler '{name}' is not an RPC the v29 client knows")
        elif spec.request_type.DESCRIPTOR.name != entry[0]:
            problems.append(f"handler '{name}' takes {spec.request_type.DESCRIPTOR.name}, client sends {entry[0]}")
    return problems


def response_type(name: str) -> type[Message] | None:
    entry = CATALOG.get(name)
    return getattr(pb, entry[1], None) if entry else None


def describe_request(name: str, payload: bytes) -> str:
    entry = CATALOG.get(name)
    msg_type = getattr(pb, entry[0], None) if entry else None
    if msg_type is None:
        return f"<{len(payload)}B, unknown rpc>"
    try:
        return text_format.MessageToString(msg_type.FromString(payload), as_one_line=True)[:500] or "{}"
    except Exception as e:
        return f"<undecodable {msg_type.__name__}: {e}>"


def rpc(name: str, request_type: type[Message]) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        if name in REGISTRY:
            raise RuntimeError(f"duplicate rpc handler: {name}")
        REGISTRY[name] = RpcSpec(name, request_type, fn)
        return fn

    return deco


async def dispatch(session: Session, req: pb.RequestEnvelope) -> pb.ResponseEnvelope:
    res = pb.ResponseEnvelope(correlation_id=req.correlation_id)
    spec = REGISTRY.get(req.rpc_name)
    if spec is None:
        # Unknown RPC: an empty payload decodes as a default message of any type, which keeps
        # most screens alive. Logged loudly so the gap is visible.
        log.warning(
            "UNIMPLEMENTED rpc=%s cid=%d req=%s", req.rpc_name, req.correlation_id, describe_request(req.rpc_name, req.payload)
        )
        session.game.record_unimplemented(req.rpc_name, req.payload)
        # ...but a default message still needs its inventory_delta: the client hands it to its inventory handlers
        # (the club inventory handler crashed on buy_expired_daily_login before it was implemented).
        resp_type = response_type(req.rpc_name)
        if resp_type is not None:
            out = resp_type()
            _ensure_inventory_delta(out)
            res.payload = out.SerializeToString()
        return res
    from arcane_server.inventory import counting_grants, report_conversions

    session.game.take_conversions(session.public_id)  # made outside an RPC (admin): not this response's to report
    try:
        body = spec.request_type.FromString(req.payload)
        wire_time.from_client(body)  # the client's real timestamps -> game time (handlers work in game time)
        with player_timezone(session.game.timezone(session.public_id)), counting_grants():
            finishers = [f for w in WATCHERS if (f := w(session)) is not None]
            out = await spec.handler(session, body)
            _ensure_inventory_delta(out)
            for finish in finishers:
                finish(out)
        # extra tokens etc. the handler granted were converted when it saved (game.Game.save): report it like the
        # game, in the response's InventoryDelta (the client shows them as CONVERTED)
        report_conversions(out, session.game.take_conversions(session.public_id))
        res.payload = wire_time.payload_to_client(type(out), out.SerializeToString())  # game -> real time
        log.info("rpc=%s cid=%d ok %dB", req.rpc_name, req.correlation_id, len(res.payload))
    except RpcError as e:
        res.response_code = e.code
        res.error_message = e.message
        log.warning("rpc=%s cid=%d error=%s %s", req.rpc_name, req.correlation_id, e.code, e.message)
    except Exception:
        log.exception("rpc=%s cid=%d crashed", req.rpc_name, req.correlation_id)
        res.response_code = pb.ERROR
        res.error_message = "internal error"
    for hook in AFTER_RPC:
        try:
            with player_timezone(session.game.timezone(session.public_id)):
                hook(session, req.rpc_name)
        except Exception:
            log.exception("after-rpc hook %s failed (rpc=%s)", getattr(hook, "__name__", hook), req.rpc_name)
    if session.pending_dynamic:
        res.dynamic_messages.extend(wire_time.dynamic_to_client(session.pending_dynamic))
        session.pending_dynamic.clear()
    return res
