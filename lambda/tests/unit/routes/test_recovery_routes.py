"""Unit tests for recovery route handlers."""

import hashlib
import json
import time

from src.entrypoint.api import lambda_handler


class TestGenerateRecoveryCodesRoute:
    def test_generate_recovery_codes_success(self, mock_service_provider, dynamodb_stubber):
        """Should generate 10 recovery codes and store them in DynamoDB."""

        # Stub 10 PutItem calls (one for each recovery code)
        # We can't predict the exact hash, so we use a more flexible approach
        for _ in range(10):
            dynamodb_stubber.add_response(
                "put_item",
                {},
            )

        event = {
            "resource": "/v1/recovery/codes",
            "path": "/v1/recovery/codes",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "recovery_codes" in body
        assert "generated_at" in body
        assert len(body["recovery_codes"]) == 10

        # Verify code format (XXXX-XXXX-XXXX-XXXX)
        for code in body["recovery_codes"]:
            assert len(code) == 19  # 16 chars + 3 dashes
            assert code.count("-") == 3


class TestValidateRecoveryCodeRoute:
    def test_validate_recovery_code_success(
        self, mock_service_provider, dynamodb_stubber, recovery_table_name
    ):
        """Should validate a recovery code and mark it as used."""
        # Prepare test data
        user_id = "user-123"
        recovery_code = "ABCD-EFGH-IJKL-MNOP"
        normalized_code = recovery_code.replace("-", "").upper()
        code_hash = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()
        timestamp = int(time.time())

        # Stub GetItem response (code exists and is valid)
        # Note: boto3 Table resource sends keys without type descriptors
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"RECOVERY#{code_hash}"},
                    "user_id": {"S": user_id},
                    "code_hash": {"S": code_hash},
                    "created_at": {"N": str(timestamp)},
                    "used_at": {"NULL": True},
                    "is_valid": {"BOOL": True},
                }
            },
            expected_params={
                "TableName": recovery_table_name,
                "Key": {
                    "PK": f"USER#{user_id}",  # Table resource sends plain values
                    "SK": f"RECOVERY#{code_hash}",
                },
            },
        )

        # Stub UpdateItem response (mark code as used)
        # We can't predict the exact timestamp, so we don't validate it
        dynamodb_stubber.add_response(
            "update_item",
            {},
        )

        event = {
            "resource": "/v1/recovery/validate",
            "path": "/v1/recovery/validate",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"recovery_code": recovery_code}),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["valid"] is True
        assert body["user_id"] == user_id
