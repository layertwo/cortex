"""Unit tests for S3Repository multipart completion (botocore Stubber, not moto)."""

import pytest

from src.shared.repository import S3Repository


@pytest.fixture
def s3_repo(boto_session, files_bucket_name):
    return S3Repository(boto_session, files_bucket_name)


class TestCompleteMultipartUpload:
    def test_completes_with_ordered_parts(self, s3_repo, s3_stubber, files_bucket_name):
        s3_stubber.add_response(
            "complete_multipart_upload",
            {"Bucket": files_bucket_name, "Key": "vault/item", "ETag": '"final-etag"'},
            {
                "Bucket": files_bucket_name,
                "Key": "vault/item",
                "UploadId": "u1",
                "MultipartUpload": {
                    "Parts": [
                        {"PartNumber": 1, "ETag": '"e1"'},
                        {"PartNumber": 2, "ETag": '"e2"'},
                    ]
                },
            },
        )

        s3_repo.complete_multipart_upload(
            "vault/item", "u1", [{"PartNumber": 1, "ETag": '"e1"'}, {"PartNumber": 2, "ETag": '"e2"'}]
        )
        s3_stubber.assert_no_pending_responses()

    def test_raises_on_s3_error(self, s3_repo, s3_stubber):
        s3_stubber.add_client_error("complete_multipart_upload", service_error_code="NoSuchUpload")
        with pytest.raises(Exception):
            s3_repo.complete_multipart_upload("vault/item", "bad", [{"PartNumber": 1, "ETag": '"e1"'}])
