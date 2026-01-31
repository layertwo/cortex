from base64 import b64encode

from boto3.dynamodb.types import Binary


def _encode_binary(value: bytes | Binary | None) -> str | None:
    """
    Encode binary data to base64 string.

    Handles both raw bytes and boto3 Binary type from DynamoDB.

    Args:
        value: Binary data (bytes or Binary type) or None

    Returns:
        Base64-encoded string or None
    """
    if value is None:  # pragma: nocover
        return None
    if isinstance(value, Binary):
        return b64encode(bytes(value)).decode("utf-8")
    return b64encode(value).decode("utf-8")


def _decode_binary(value: bytes | Binary) -> str:
    """
    Decode binary data to base64 string.

    Handles both raw bytes and boto3 Binary type from DynamoDB.

    Args:
        value: Binary data (bytes or Binary type)

    Returns:
        Base64-encoded string
    """
    if isinstance(value, Binary):
        return bytes(value).decode()
    return value.decode()
