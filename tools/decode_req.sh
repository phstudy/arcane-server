#!/bin/sh
# Decode a RequestEnvelope file: tools/decode_req.sh <file.req.bin>
# The payload is bytes; decode it with the type named for its rpc in src/arcane_server/rpc_catalog.py.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec protoc --decode serverproto.RequestEnvelope -I "$ROOT/proto" "$ROOT/proto/serverproto.proto" < "$1"
