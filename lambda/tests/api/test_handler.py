from src.api.handler import lambda_handler


def test_api_handler_happy_path():
    response = lambda_handler(None, None)
    assert response["statusCode"] == 200
