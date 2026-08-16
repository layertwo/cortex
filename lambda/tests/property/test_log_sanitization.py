"""
Property-Based Tests for Zero-Knowledge Log Sanitization (issue #47).

Feature: cortex, Property 29: Logs contain no PII

The backend must NEVER log `user_id` (Cognito sub), S3 object keys, or full
request context. These tests enforce the zero-knowledge logging policy two ways:

1. **Static source scan**: every ``logger.*(...)`` call under ``src/`` is parsed
   and checked for banned field names. This catches violations at test time
   without needing to exercise every code path.
2. **Runtime capture**: key service operations are run against botocore stubs
   and the emitted structlog JSON is parsed to assert no banned field appears.

Validates: issue #47 acceptance criterion (tests verifying no PII in logs)
"""

import ast
import json
from pathlib import Path

import pytest
from botocore.stub import ANY

from src.shared.generated.models import (
    CreateCollectionRequestContent,
    CreateItemRequestContent,
    InitiateItemUploadRequestContent,
)
from src.shared.models import ItemType

SRC_DIR = Path(__file__).resolve().parents[2] / "src"

# Fields that MUST NEVER appear as a kwarg or **dict key in a logger.* call.
# Match on the key name only (``user_id``, ``s3_key``, etc.), not the value.
BANNED_LOG_FIELDS = {
    "user_id",
    "s3_key",
    "object_key",
    "request_context",
    "principalId",
    "item_user_id",
    "collection_user_id",
}

# Logger method names that emit log entries.
LOGGER_METHODS = {"info", "warning", "error", "debug", "exception", "critical"}

# A log message string may legitimately contain a banned word (e.g.
# "user_id_not_found"). Only flag banned words used as **kwarg names** or
# **dict keys**, not as substrings of the message string or of variable names
# that happen to share a prefix.


def _find_logger_calls(tree: ast.AST, filepath: str):
    """Yield (node, filepath) for every ``logger.<method>(...)`` call in ``tree``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # logger.info(...)  ->  func is ast.Attribute, .attr is the method
        if isinstance(func, ast.Attribute) and func.attr in LOGGER_METHODS:
            # The receiver must be a simple Name like ``logger`` (or ``_logger``).
            if isinstance(func.value, ast.Name) and func.value.id in ("logger", "_logger"):
                yield node, filepath


def _extract_kwargs(call: ast.Call):
    """Return the set of keyword argument names and **dict keys in ``call``.

    Handles both ``logger.info("msg", user_id=x)`` and
    ``logger.info("msg", **{"user_id": x})`` forms.
    """
    names = set()
    for kw in call.keywords:
        # logger.info("msg", user_id=user_id)  ->  kw.arg == "user_id"
        if kw.arg is not None:
            names.add(kw.arg)
        # logger.info("msg", **{"user_id": user_id})  ->  kw.arg is None,
        # kw.value is a Dict literal; collect its key strings
        elif isinstance(kw.value, ast.Dict):
            for key in kw.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names.add(key.value)
    return names


class TestStaticSourceScan:
    """
    Property 29 (static): no ``logger.*(...)`` call under ``src/`` passes a
    banned field name as a kwarg or ``**dict`` key.
    """

    @staticmethod
    def _all_python_files():
        """Every .py file under ``src/`` (excluding generated code)."""
        files = []
        for path in sorted(SRC_DIR.rglob("*.py")):
            # Skip generated code (codegen output, not hand-edited).
            if "generated" in path.parts:
                continue
            files.append(path)
        assert files, "no .py files found under src/ -- check SRC_DIR"
        return files

    def test_finds_python_files(self):
        """Non-vacuity: there are .py files to scan."""
        files = self._all_python_files()
        assert len(files) >= 20, f"expected >=20 .py files, got {len(files)}"

    @pytest.mark.parametrize("filepath", _all_python_files(), ids=lambda p: p.name)
    def test_no_banned_field_in_logger_calls(self, filepath):
        """No ``logger.*(...)`` call in this file passes a banned field name."""
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))

        violations = []
        for call, _ in _find_logger_calls(tree, str(filepath)):
            kwargs = _extract_kwargs(call)
            leaked = kwargs & BANNED_LOG_FIELDS
            if leaked:
                violations.append(
                    f"  line {call.lineno}: logger.{call.func.attr}(...) " f"leaks {sorted(leaked)}"
                )

        assert (
            not violations
        ), f"{filepath}: {len(violations)} logger call(s) leak banned fields:\n" + "\n".join(
            violations
        )


class TestRuntimeLogCapture:
    """
    Property 29 (runtime): exercising real service operations emits structlog
    JSON whose keys never include a banned field.
    """

    @staticmethod
    def _capture_log_entries(capsys):
        """Parse every line on stdout as a structlog JSON entry."""
        captured = capsys.readouterr()
        entries = []
        for line in captured.out.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                # Non-JSON output (e.g. pytest progress) -- skip.
                continue
        return entries

    @staticmethod
    def _assert_no_banned_fields(entries, operation_label):
        """Assert no entry in ``entries`` has a banned top-level key."""
        for entry in entries:
            leaked = set(entry.keys()) & BANNED_LOG_FIELDS
            if leaked:
                raise AssertionError(
                    f"{operation_label}: log entry leaked banned fields "
                    f"{sorted(leaked)} in {json.dumps(entry)}"
                )

    VAULTS_TABLE = "test-vaults-table"
    ITEMS_TABLE = "test-items-table"
    COLLECTIONS_TABLE = "test-collections-table"
    SHARES_TABLE = "test-shares-table"

    def test_vault_service_create_vault_log_has_no_user_id(
        self, vault_service, dynamodb_stubber, capsys
    ):
        """create_vault logs vault_id + salt_length, never user_id."""
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": self.VAULTS_TABLE,
                "Item": ANY,
                "ConditionExpression": ANY,
            },
        )
        vault_service.create_vault("user-abc-123")

        entries = self._capture_log_entries(capsys)
        self._assert_no_banned_fields(entries, "create_vault")

    def test_item_service_create_item_log_has_no_user_id(
        self, item_service, dynamodb_stubber, capsys
    ):
        """create_item logs vault_id + item_id + item_type, never user_id."""
        import base64

        request = CreateItemRequestContent(
            vault_id="vault-456",
            item_type=ItemType.NOTE,
            encrypted_content=base64.b64encode(b"opaque"),
            encrypted_metadata=base64.b64encode(b"opaque"),
        )
        dynamodb_stubber.add_response("put_item", {}, {"TableName": self.ITEMS_TABLE, "Item": ANY})
        item_service.create_item("user-abc-123", request)

        entries = self._capture_log_entries(capsys)
        self._assert_no_banned_fields(entries, "create_item")

    def test_item_service_initiate_upload_log_has_no_user_id(
        self, item_service, dynamodb_stubber, capsys
    ):
        """initiate_upload logs item_id + size_bytes, never user_id or s3_key."""
        import base64

        request = InitiateItemUploadRequestContent(
            vault_id="vault-456",
            encrypted_metadata=base64.b64encode(b"opaque"),
            size_bytes=1024,
            wrapped_dek=base64.b64encode(bytes(range(97))),
            dek_version=1,
        )
        # Small file -> single presigned PUT (generate_presigned_url is
        # client-side, no S3 API call, so no s3_stubber needed).
        dynamodb_stubber.add_response("put_item", {}, {"TableName": self.ITEMS_TABLE, "Item": ANY})

        item_service.initiate_upload("user-abc-123", request)

        entries = self._capture_log_entries(capsys)
        self._assert_no_banned_fields(entries, "initiate_upload")

    def test_collection_service_create_collection_log_has_no_user_id(
        self, collection_service, dynamodb_stubber, capsys
    ):
        """create_collection logs vault_id + collection_id, never user_id."""
        import base64

        request = CreateCollectionRequestContent(
            vault_id="vault-789",
            encrypted_metadata=base64.b64encode(b"opaque"),
        )
        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": self.COLLECTIONS_TABLE, "Item": ANY}
        )
        collection_service.create_collection("user-abc-123", request)

        entries = self._capture_log_entries(capsys)
        self._assert_no_banned_fields(entries, "create_collection")

    def test_share_service_create_share_log_has_no_user_id(
        self, share_service, dynamodb_stubber, capsys
    ):
        """create_share logs share_id + item_id, never user_id."""
        item_id = "item-1"
        user_id = "user-abc-123"

        # Stub get_item for items table (verify ownership) -- match the unit test style.
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": "vault-1"},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/vault-1/files/{item_id}/blob"},
                    "encrypted_metadata": {"B": b"opaque"},
                }
            },
            {"TableName": self.ITEMS_TABLE, "Key": {"PK": f"ITEM#{item_id}"}},
        )
        # Stub put_item for shares table.
        dynamodb_stubber.add_response("put_item", {}, {"TableName": self.SHARES_TABLE, "Item": ANY})

        from src.shared.models import CreateShareRequest

        request = CreateShareRequest(item_id=item_id)
        share_service.create_share(user_id, request)

        entries = self._capture_log_entries(capsys)
        self._assert_no_banned_fields(entries, "create_share")
