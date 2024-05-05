import hashlib
import os
import uuid
from unittest.mock import patch, AsyncMock, ANY

import pytest
import tenacity
from boto3.exceptions import ResourceLoadException
from botocore.exceptions import EndpointConnectionError

from asyncflows.models.blob import Blob


@pytest.fixture
def blob_value():
    return b"Test blob value"


@pytest.fixture
def blob_key(blob_value):
    return hashlib.sha256(blob_value).hexdigest()


@pytest.fixture
def blob(blob_key):
    return Blob(id=blob_key)


@pytest.fixture
def blob_value_2():
    return b"Another test blob value"


async def test_save(log, blob_repo, blob, blob_value):
    saved_blob = await blob_repo.save(log, blob_value)
    assert saved_blob.id is not None
    assert saved_blob.file_extension is None


async def test_retrieve(log, blob_repo, blob, blob_value):
    saved_blob = await blob_repo.save(log, blob_value)
    retrieved_value = await blob_repo.retrieve(log, saved_blob)
    assert retrieved_value == blob_value


async def test_multi_retrieve(log, blob_repo, blob, blob_value):
    value_2 = b"Another value"
    saved_blob = await blob_repo.save(log, blob_value)
    saved_blob_2 = await blob_repo.save(log, value_2)
    retrieved_values = await blob_repo.multi_retrieve(log, [saved_blob, saved_blob_2])
    assert retrieved_values == [blob_value, value_2]


async def test_exists(log, blob_repo, blob, blob_value):
    saved_blob = await blob_repo.save(log, blob_value)
    exists = await blob_repo.exists(log, saved_blob)
    assert exists is True
    non_existent_blob = Blob(id="nonexistent")
    exists = await blob_repo.exists(log, non_existent_blob)
    assert exists is False


async def test_save_with_file_extension(log, blob_repo, blob_value):
    file_extension = "txt"
    saved_blob = await blob_repo.save(log, blob_value, file_extension=file_extension)
    assert saved_blob.id is not None
    assert saved_blob.file_extension == file_extension


async def test_download(log, blob_repo, blob, blob_value):
    saved_blob = await blob_repo.save(log, blob_value)
    download_path = await blob_repo.download(log, saved_blob)
    assert os.path.exists(download_path)
    with open(download_path, "rb") as file:
        downloaded_value = file.read()
    assert downloaded_value == blob_value
    os.remove(download_path)  # Clean up the file after test


async def test_delete(log, blob_repo, blob, blob_value):
    saved_blob = await blob_repo.save(log, blob_value)
    exists = await blob_repo.exists(log, saved_blob)
    assert exists is True

    await blob_repo.delete(log, saved_blob)
    exists = await blob_repo.exists(log, saved_blob)
    assert exists is False


async def test_retrieve_nonexistent_blob(log, blob_repo):
    # Using a random UUID so it's almost certain to not exist
    nonexistent_blob = Blob(id=str(uuid.uuid4()))
    retrieved_value = await blob_repo.retrieve(log, nonexistent_blob)
    assert retrieved_value is None


async def test_save_retrieve_with_namespace(log, blob_repo, blob_value):
    namespace = "test-namespace"
    saved_blob = await blob_repo.save(log, blob_value, namespace=namespace)
    assert saved_blob.id is not None
    retrieved_value = await blob_repo.retrieve(log, saved_blob, namespace=namespace)
    assert retrieved_value == blob_value


async def test_save_same_blob_id(log, blob_repo, blob_value):
    blob_1 = await blob_repo.save(log, blob_value)
    blob_2 = await blob_repo.save(log, blob_value)
    blob_3 = await blob_repo.save(log, blob_value)
    assert blob_1.id == blob_2.id == blob_3.id


async def test_save_retrieve_blob_id_collision(
    log, blob_repo, blob_value, blob_value_2
):
    saved_blob_1 = await blob_repo.save(log, blob_value)
    saved_blob_2 = await blob_repo.save(log, blob_value_2)
    assert saved_blob_1.id != saved_blob_2.id


@pytest.fixture()
async def s3(s3_blob_repo):
    async with s3_blob_repo._get_s3_resource() as s3_:
        yield s3_


@pytest.fixture()
async def s3_client(s3_blob_repo):
    async with s3_blob_repo._get_s3_client() as s3_:
        yield s3_


@pytest.mark.parametrize(
    "exc, event_text",
    [
        (
            None,
            "Retrying asyncflows.repos.blob_repo.S3BlobRepo._wrap_tenacity.<locals>._timeout in 0.0 seconds as it raised InvalidObjectState: An error occurred (000) when calling the mock operation: Unknown.",
        ),
        (
            EndpointConnectionError(endpoint_url="mock"),  # botocore exc
            'Retrying asyncflows.repos.blob_repo.S3BlobRepo._wrap_tenacity.<locals>._timeout in 0.0 seconds as it raised EndpointConnectionError: Could not connect to the endpoint URL: "mock".',
        ),
        (
            ResourceLoadException(),  # boto3 exc
            "Retrying asyncflows.repos.blob_repo.S3BlobRepo._wrap_tenacity.<locals>._timeout in 0.0 seconds as it raised ResourceLoadException: .",
        ),
    ],
)
async def test_s3_retrying(
    log,
    mock_tenacity,
    s3_blob_repo,
    s3_client,
    blob_value,
    log_history,
    exc,
    event_text,
):
    if exc is None:
        exc = s3_client.exceptions.InvalidObjectState(
            {
                "Error": {
                    "Code": "000",
                }
            },
            "mock",
        )

    def mock_throwing_s3_client():
        s3_client_mock = AsyncMock(wraps=s3_client)
        # pass through the exception classes
        s3_client_mock.exceptions = s3_client.exceptions
        s3_client_mock.head_object.side_effect = exc

        context_mock = AsyncMock()
        context_mock.__aenter__.return_value = s3_client_mock
        return context_mock

    with patch.object(s3_blob_repo, "_get_s3_client", mock_throwing_s3_client):
        with pytest.raises(tenacity.RetryError):
            # `save` calls `__exists` which calls `s3_client.head_object`
            await s3_blob_repo.save(log, blob_value)

    assert len(log_history) == 2
    for log_entry in log_history:
        assert log_entry == {
            "exc_info": exc,
            "event": event_text,
            "log_level": "warning",
            "func": s3_blob_repo._S3BlobRepo__exists,
        }


async def test_s3_blocking(
    log,
    s3_blob_repo,
    s3,
    s3_client,
    blob,
    log_history,
    mock_tenacity,
    mock_wait_for,
    blocking_func,
):
    def mock_get_s3_resource():
        s3_mock = AsyncMock(wraps=s3)
        # pass through the exception classes
        s3_mock.meta = s3.meta
        s3_mock.Object = blocking_func

        context_mock = AsyncMock()
        context_mock.__aenter__.return_value = s3_mock
        return context_mock

    with patch.object(s3_blob_repo, "_get_s3_resource", mock_get_s3_resource):
        with pytest.raises(tenacity.RetryError):
            await s3_blob_repo.retrieve(log, blob)

    assert len(log_history) == 2
    for log_entry in log_history:
        assert log_entry == {
            "event": "Retrying asyncflows.repos.blob_repo.S3BlobRepo._wrap_tenacity.<locals>._timeout in 0.0 seconds as it raised TimeoutError: .",
            "exc_info": ANY,
            "log_level": "warning",
            "func": s3_blob_repo._S3BlobRepo__retrieve,
        }


async def test_s3_client_blocking(
    log,
    s3_blob_repo,
    s3,
    s3_client,
    blob_value,
    log_history,
    mock_tenacity,
    mock_wait_for,
    blocking_func,
):
    def mock_get_s3_client():
        s3_client_mock = AsyncMock(wraps=s3_client)
        # pass through the exception classes
        s3_client_mock.exceptions = s3_client.exceptions
        s3_client_mock.head_object = blocking_func

        context_mock = AsyncMock()
        context_mock.__aenter__.return_value = s3_client_mock
        return context_mock

    with patch.object(s3_blob_repo, "_get_s3_client", mock_get_s3_client):
        with pytest.raises(tenacity.RetryError):
            # `save` calls `__exists` which calls `s3_client.head_object`
            await s3_blob_repo.save(log, blob_value)

    assert len(log_history) == 2
    for log_entry in log_history:
        assert log_entry == {
            "event": "Retrying asyncflows.repos.blob_repo.S3BlobRepo._wrap_tenacity.<locals>._timeout in 0.0 seconds as it raised TimeoutError: .",
            "exc_info": ANY,
            "log_level": "warning",
            "func": s3_blob_repo._S3BlobRepo__exists,
        }
