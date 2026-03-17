"""Unit tests for recovery route handlers."""

import hashlib
import time


class TestGenerateRecoveryCodesRoute:
    def test_generate_recovery_codes_success(self, client, dynamodb_stubber):
        """Should generate 10 recovery codes and store them in DynamoDB."""
        # Stub 10 PutItem calls (one for each recovery code)
        for _ in range(10):
            dynamodb_stubber.add_response(
                "put_item",
                {},
            )

        response = client.post("/v1/recovery/codes", json={})

        assert response.status_code == 200
        body = response.json()
        assert "recovery_codes" in body
        assert "generated_at" in body
        assert len(body["recovery_codes"]) == 10

        # Verify code format (XXXX-XXXX-XXXX-XXXX)
        for code in body["recovery_codes"]:
            assert len(code) == 19  # 16 chars + 3 dashes
            assert code.count("-") == 3


class TestValidateRecoveryCodeRoute:
    def test_validate_recovery_code_success(self, client, dynamodb_stubber, recovery_table_name):
        """Should validate a recovery code and mark it as used."""
        user_id = "test-user-id"
        recovery_code = "ABCD-EFGH-IJKL-MNOP"
        normalized_code = recovery_code.replace("-", "").upper()
        code_hash = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()
        timestamp = int(time.time())

        # Stub GetItem response (code exists and is valid)
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
                    "PK": f"USER#{user_id}",
                    "SK": f"RECOVERY#{code_hash}",
                },
            },
        )

        # Stub UpdateItem response (mark code as used)
        dynamodb_stubber.add_response(
            "update_item",
            {},
        )

        response = client.post(
            "/v1/recovery/validate",
            json={"recovery_code": recovery_code},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is True
        assert body["user_id"] == user_id
