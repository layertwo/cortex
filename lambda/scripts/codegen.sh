#!/usr/bin/env bash
# Regenerate pydantic models from the Smithy/OpenAPI contract.
#
# Smithy is the single source of truth. This builds the OpenAPI via gradle, then
# emits snake_case pydantic v2 models with camelCase aliases (baked in by
# datamodel-codegen) onto GeneratedBaseModel, so the backend honors the camelCase
# wire contract the web client targets.
#
# models.py is a GENERATED ARTIFACT (gitignored, like packages/client). CI
# regenerates it before linting/tests; run this locally after any smithy/ change.
# Requires a JDK (JAVA_HOME) and `uv sync --group dev`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPENAPI="$REPO_ROOT/build/smithy/openapi/openapi/Cortex.openapi.json"
GENERATED_DIR="$REPO_ROOT/lambda/src/shared/generated"

# Build the OpenAPI from Smithy via gradle. The standalone `smithy build` CLI
# can't produce it here — smithy-build.json declares no maven deps, so it lacks
# the openapi plugin; the gradle build supplies it. --rerun-tasks is required:
# the smithy-gradle plugin falsely reports UP-TO-DATE after a .smithy edit.
echo "==> gradle smithyBuild"
(cd "$REPO_ROOT" && smithy/gradlew smithyBuild --project-dir smithy --rerun-tasks -q)

rm -f "$GENERATED_DIR/models.py"
mkdir -p "$GENERATED_DIR"
touch "$GENERATED_DIR/__init__.py"

# --type-mappings string+byte=binary: emit pydantic Base64Bytes for Smithy Blob
# (raw bytes Python-side, standard base64 on the JSON wire) instead of the default
# Base64Str, which forces UTF-8 on decode and can't carry binary (salts/ciphertext).
# --target-python-version 3.13: the CI matrix runs black under 3.13, which cannot
# parse 3.14-only syntax — keep generated code 3.13-compatible.
echo "==> codegen: $OPENAPI -> $GENERATED_DIR/models.py"
(cd "$REPO_ROOT/lambda" && uv run --quiet datamodel-codegen \
  --input "$OPENAPI" \
  --input-file-type openapi \
  --output "$GENERATED_DIR/models.py" \
  --output-model-type pydantic_v2.BaseModel \
  --base-class src.shared._codegen_base.GeneratedBaseModel \
  --type-mappings string+byte=binary \
  --snake-case-field \
  --use-default \
  --use-annotated \
  --use-standard-collections \
  --use-union-operator \
  --use-double-quotes \
  --target-python-version 3.13 \
  --disable-timestamp)

echo "==> done"
