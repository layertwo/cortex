"""Base class for smithy-generated pydantic models.

Wired in via `--base-class` in `lambda/scripts/codegen.sh`. Keeps generated
files free of project-specific config while ensuring every generated model
accepts both wire (camelCase alias) and Python (snake_case) field names on
input. FastAPI serializes responses by_alias, so the wire stays camelCase —
matching the Smithy/OpenAPI contract the web client targets.
"""

from pydantic import BaseModel, ConfigDict


class GeneratedBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
