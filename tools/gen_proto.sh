#!/usr/bin/env bash
# Regenerate Python protobuf bindings from proto/serverproto.proto.
set -euo pipefail
cd "$(dirname "$0")/.."
protoc -I proto --python_out=src/arcane_server/proto --pyi_out=src/arcane_server/proto proto/serverproto.proto
