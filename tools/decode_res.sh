#!/bin/sh
# Decode a ResponseEnvelope file: tools/decode_res.sh <file.res.bin>
# The payload is bytes; decode it with the type named for its rpc in src/arcane_server/rpc_catalog.py.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec protoc --decode serverproto.ResponseEnvelope -I "$ROOT/proto" "$ROOT/proto/serverproto.proto" < "$1"
