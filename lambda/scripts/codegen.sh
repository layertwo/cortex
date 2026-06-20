#!/usr/bin/env bash
# Regenerate pydantic models from the Smithy/OpenAPI contract.
#
# Smithy is the single source of truth. This emits snake_case pydantic v2 models
# with camelCase aliases (baked in by datamodel-codegen) onto GeneratedBaseModel,
# so the backend honors the camelCase wire contract the web client targets.
#
# Requires: smithy CLI (brew install smithy-cli) and `uv sync --group dev`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SMITHY_DIR="$REPO_ROOT/smithy"
OPENAPI="$SMITHY_DIR/build/smithy/openapi/openapi/Cortex.openapi.json"
GENERATED_DIR="$REPO_ROOT/lambda/src/shared/generated"

# Rebuild the OpenAPI from Smithy if it's stale/absent.
if [ ! -f "$OPENAPI" ] || [ "${SMITHY_BUILD:-1}" = "1" ]; then
  command -v smithy >/dev/null || {
    echo "smithy CLI not found (brew install smithy-cli) and no prebuilt $OPENAPI"
    exit 1
  }
  echo "==> smithy build"
  (cd "$SMITHY_DIR" && rm -rf build && smithy build)
fi

rm -rf "$GENERATED_DIR"
mkdir -p "$GENERATED_DIR"
touch "$GENERATED_DIR/__init__.py"

echo "==> codegen: $OPENAPI -> $GENERATED_DIR/models.py"
(cd "$REPO_ROOT/lambda" && uv run --quiet datamodel-codegen \
  --input "$OPENAPI" \
  --input-file-type openapi \
  --output "$GENERATED_DIR/models.py" \
  --output-model-type pydantic_v2.BaseModel \
  --base-class src.shared._codegen_base.GeneratedBaseModel \
  --snake-case-field \
  --use-default \
  --use-annotated \
  --use-standard-collections \
  --use-union-operator \
  --use-double-quotes \
  --target-python-version 3.13 \
  --disable-timestamp)

echo "==> done"
