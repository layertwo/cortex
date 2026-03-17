"""Unit tests for authentication route handlers."""


class TestLoginRoute:
    def test_login_route_handler_success(self, client):
        """Test login route handler returns expected response structure."""
        response = client.post(
            "/v1/auth/login",
            json={"email": "test@example.com", "password": "testpassword123"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "message" in body, "Response should include message"
        assert "auth_type" in body, "Response should include auth_type"

        assert isinstance(body["message"], str), "message should be a string"
        assert isinstance(body["auth_type"], str), "auth_type should be a string"
        assert (
            body["auth_type"] == "cognito"
        ), f"auth_type should be 'cognito', got {body['auth_type']}"

    def test_login_route_handler_missing_email(self, client):
        """Test login route handler returns error when email is missing."""
        response = client.post(
            "/v1/auth/login",
            json={"password": "testpassword123"},
        )

        # FastAPI returns 422 for Pydantic validation errors
        assert response.status_code == 422

    def test_login_route_handler_missing_password(self, client):
        """Test login route handler returns error when password is missing."""
        response = client.post(
            "/v1/auth/login",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 422


class TestRefreshRoute:
    def test_refresh_route_handler_success(self, client):
        """Test refresh route handler returns expected response structure."""
        response = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": "test-refresh-token"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "message" in body, "Response should include message"
        assert "auth_type" in body, "Response should include auth_type"

        assert isinstance(body["message"], str), "message should be a string"
        assert isinstance(body["auth_type"], str), "auth_type should be a string"
        assert (
            body["auth_type"] == "cognito"
        ), f"auth_type should be 'cognito', got {body['auth_type']}"

    def test_refresh_route_handler_missing_token(self, client):
        """Test refresh route handler returns error when refresh_token is missing."""
        response = client.post(
            "/v1/auth/refresh",
            json={},
        )

        assert response.status_code == 422


class TestRecoverRoute:
    def test_recover_route_handler_success(self, client):
        """Test recover route handler returns expected response structure."""
        response = client.post(
            "/v1/auth/recover",
            json={"email": "test@example.com", "recovery_code": "ABCD-EFGH-IJKL-MNOP"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "message" in body, "Response should include message"
        assert "recovery_type" in body, "Response should include recovery_type"

        assert isinstance(body["message"], str), "message should be a string"
        assert isinstance(body["recovery_type"], str), "recovery_type should be a string"
        assert (
            body["recovery_type"] == "account_password"
        ), f"recovery_type should be 'account_password', got {body['recovery_type']}"

    def test_recover_route_handler_missing_email(self, client):
        """Test recover route handler returns error when email is missing."""
        response = client.post(
            "/v1/auth/recover",
            json={"recovery_code": "ABCD-EFGH-IJKL-MNOP"},
        )

        assert response.status_code == 422

    def test_recover_route_handler_missing_recovery_code(self, client):
        """Test recover route handler returns error when recovery_code is missing."""
        response = client.post(
            "/v1/auth/recover",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 422
