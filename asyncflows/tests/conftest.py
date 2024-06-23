import asyncio
import logging
import os
import uuid
from tempfile import TemporaryDirectory
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
import tenacity
import yaml
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from asyncflows.utils.action_utils import get_actions_dict
from asyncflows.actions.prompt import Outputs as PromptOutputs, Prompt
from asyncflows.actions.transformer import (
    BaseTransformerInputs as TransformerInputs,
    Outputs as TransformerOutputs,
    Retrieve,
    Rerank,
)
from asyncflows.log_config import configure_logging, get_logger
from asyncflows.models.blob import Blob
from asyncflows.models.config.flow import build_hinted_action_config
from asyncflows.repos.blob_repo import (
    InMemoryBlobRepo,
    RedisBlobRepo,
    FilesystemBlobRepo,
    S3BlobRepo,
)
from asyncflows.repos.cache_repo import ShelveCacheRepo

from aioresponses import aioresponses

from asyncflows.services.action_service import ActionService
from asyncflows.utils.async_utils import LagMonitor

_log_history = []


def capture_processor(logger, method_name, event_dict):
    if method_name == "debug" and event_dict["event"] != "Yielding outputs":
        return event_dict
    dict_copy = event_dict.copy()
    dict_copy["log_level"] = method_name
    _log_history.append(dict_copy)
    return event_dict


@pytest.fixture(scope="session", autouse=True)
def configure_logs():
    configure_logging(
        pretty=True, level=logging.DEBUG, additional_processors=[capture_processor]
    )


@pytest.fixture(scope="function")
def log_history():
    yield _log_history
    _log_history.clear()


@pytest.fixture(scope="function")
def log(log_history):
    return get_logger()


@pytest.fixture(scope="function")
def temp_dir():
    temp_dir = TemporaryDirectory()
    yield temp_dir.name
    temp_dir.cleanup()


@pytest.fixture(scope="session")
def mock_boto():
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(port=0)
    server.start()
    port = server._server.socket.getsockname()[1]  # type: ignore
    yield f"http://127.0.0.1:{port}"
    server.stop()


@pytest.fixture(scope="function")
async def in_memory_blob_repo(temp_dir):
    repo = InMemoryBlobRepo(temp_dir=temp_dir)
    yield repo
    repo._store.clear()


@pytest.fixture(scope="function")
async def blob_repo(request: pytest.FixtureRequest, temp_dir: str, log):
    if isinstance(request.param, tuple):
        repo_type, should_mock_boto = request.param
    else:
        repo_type = request.param
        should_mock_boto = False
    sentinel = aws_endpoint_url_bak = object()
    if repo_type == S3BlobRepo:
        if should_mock_boto:
            endpoint_url = request.getfixturevalue("mock_boto")
            aws_endpoint_url_bak = os.environ.get("AWS_ENDPOINT_URL")
            os.environ["AWS_ENDPOINT_URL"] = endpoint_url

            blob_repo = repo_type(
                temp_dir=temp_dir,
                endpoint_url=None,
                bucket_name="test",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            )
        else:
            blob_repo = repo_type(
                temp_dir=temp_dir,
            )
    else:
        blob_repo = repo_type(
            temp_dir=temp_dir,
        )
    await blob_repo.on_startup(log)
    yield blob_repo
    if aws_endpoint_url_bak is not sentinel:
        if aws_endpoint_url_bak is None:
            del os.environ["AWS_ENDPOINT_URL"]
        else:
            assert isinstance(aws_endpoint_url_bak, str)
            os.environ["AWS_ENDPOINT_URL"] = aws_endpoint_url_bak
    if isinstance(blob_repo, InMemoryBlobRepo):
        blob_repo._store.clear()
    await blob_repo.close()


@pytest.fixture(scope="function")
def s3_blob_repo(blob_repo):
    # see pytest_generate_tests
    # this only lets through s3 parameterized blob repos
    return blob_repo


@pytest.fixture
async def in_memory_blob(log, in_memory_blob_repo) -> Blob:
    return await in_memory_blob_repo.save(log, b"test_blob", file_extension="txt")


@pytest.fixture
async def blob(log, blob_repo) -> Blob:
    return await blob_repo.save(log, b"test_blob", file_extension="txt")


@pytest.fixture
def mock_aioresponse():
    with aioresponses(passthrough=["http://localhost", "http://127.0.0.1"]) as m:
        yield m


@pytest.fixture
def cache_repo(temp_dir):
    # TODO rainbow this like blob_repo
    return ShelveCacheRepo(
        temp_dir=temp_dir,
    )


@pytest.fixture
def mock_wait_for():
    orig_wait_for = asyncio.wait_for

    def mock_wait_for(*args, timeout, **kwargs):
        return orig_wait_for(timeout=0.1, *args, **kwargs)

    with mock.patch("asyncio.wait_for", mock_wait_for):
        yield


@pytest.fixture
def mock_tenacity():
    original_retry = tenacity.retry

    def mock_tenacity(wait, **kwargs):
        return original_retry(
            wait=tenacity.wait_fixed(0),
            **kwargs,
        )

    with patch("tenacity.retry", mock_tenacity):
        yield


Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    fullname = Column(String)
    nickname = Column(String)

    def __repr__(self):
        return f"<User(name={self.name}, fullname={self.fullname}, nickname={self.nickname})>"


@pytest.fixture
def dummy_sqlite_engine():
    engine = create_engine("sqlite:///:memory:", echo=True, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ed_user = User(name="ed", fullname="Ed Jones", nickname="edsnickname")
    session.add(ed_user)
    session.commit()
    return engine


@pytest.fixture
def mock_sqlite_engine(dummy_sqlite_engine):
    with patch(
        "sqlalchemy.create_engine",
        return_value=dummy_sqlite_engine,
    ):
        yield


@pytest.fixture
async def dummy_async_sqlite_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        ed_user = User(name="ed", fullname="Ed Jones", nickname="edsnickname")
        session.add(ed_user)
        await session.commit()

    return engine


@pytest.fixture
def mock_async_sqlite_engine(dummy_async_sqlite_engine):
    with patch(
        "sqlalchemy.ext.asyncio.create_async_engine",
        return_value=dummy_async_sqlite_engine,
    ):
        yield


@pytest.fixture
def blocking_func():
    async def block(*args, **kwargs):
        await asyncio.sleep(1)
        return MagicMock()

    return block


@pytest.fixture(scope="session")
def testing_actions_type():
    # TODO assert tests not imported before this line
    import asyncflows.tests.resources.actions  # noqa

    testing_action_names = list(get_actions_dict().keys())

    return build_hinted_action_config(
        action_names=testing_action_names,
    )


@pytest.fixture()
def testing_actions(testing_actions_type):
    with open("asyncflows/tests/resources/testing_actions.yaml") as f:
        return testing_actions_type.model_validate(yaml.safe_load(f))


@pytest.fixture
def simple_flow(testing_flows):
    return testing_flows.subflows["chat_and_react_flow"]


@pytest.fixture
def in_memory_action_service(
    temp_dir, cache_repo, in_memory_blob_repo, testing_actions
):
    return ActionService(
        temp_dir=temp_dir,
        use_cache=True,
        cache_repo=cache_repo,
        blob_repo=in_memory_blob_repo,
        config=testing_actions,
    )


@pytest.fixture
def action_service(temp_dir, cache_repo, blob_repo, testing_actions):
    return ActionService(
        temp_dir=temp_dir,
        use_cache=True,
        cache_repo=cache_repo,
        blob_repo=blob_repo,
        config=testing_actions,
    )


@pytest.fixture
def mock_trace_id():
    return str(uuid.uuid4())


@pytest.fixture
async def lag_monitor(log):
    monitor = LagMonitor(
        log,
        interval=0.1,
        lag_threshold=0.01,
    )
    monitor.start()  # this will show 3s of lag because of pytest setup
    yield monitor
    monitor.stop()


@pytest.fixture(autouse=True)
def gracefully_cancel_tasks(event_loop):
    yield
    tasks = asyncio.all_tasks(event_loop)
    if not tasks:
        return
    for task in tasks:
        task.cancel()
    event_loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))


@pytest.fixture
def mock_prompt_result():
    # TODO define mocks per action instance, not globally
    return "mock result prompt <summary> my summary </summary> <sql> select * from users </sql>"


@pytest.fixture()
def mock_prompt_action(mock_prompt_result):
    # TODO mock the prompt for each example separately
    outputs = PromptOutputs(
        result=mock_prompt_result,
        response=mock_prompt_result,
        data={
            "action_items": ["a", "b"],
        },
    )

    async def outputs_iter(*args, **kwargs):
        yield outputs

    with patch.object(Prompt, "run", new=outputs_iter):
        yield


@pytest.fixture()
def mock_transformer_action():
    async def outputs_ret(self, inputs: TransformerInputs):
        return TransformerOutputs(
            result=inputs.documents,
        )

    with patch.object(Retrieve, "run", new=outputs_ret), patch.object(
        Rerank, "run", new=outputs_ret
    ):
        yield


@pytest.fixture
def assert_no_errors(log_history):
    yield
    assert all(log_line["log_level"] != "error" for log_line in log_history)


@pytest.fixture
def main_entrypoint_mocked_trace_id(mock_trace_id, discord_entrypoint):
    with mock.patch(
        "asyncflows.deploy.entrypoint.EntrypointBase.initialize_logger"
    ) as _initialize_logger:
        _initialize_logger.return_value = get_logger().bind(trace_id=mock_trace_id)
        yield discord_entrypoint


def pytest_generate_tests(metafunc):
    if "blob_repo" in metafunc.fixturenames:
        params = [
            # the True/False here mean `should_mock_boto`
            pytest.param(
                (S3BlobRepo, True),
                marks=[
                    pytest.mark.slow,
                ],
            ),
            pytest.param(
                (S3BlobRepo, False),
                marks=[
                    pytest.mark.slow,
                    pytest.mark.skipif(
                        "AWS_ENDPOINT_URL" not in os.environ
                        or not os.environ["AWS_ENDPOINT_URL"],
                        reason="AWS_ENDPOINT_URL not set in the environment or empty",
                    ),
                ],
            ),
        ]
        # some tests only want s3
        if "s3_blob_repo" not in metafunc.fixturenames:
            params += [
                InMemoryBlobRepo,
                FilesystemBlobRepo,
                pytest.param(
                    RedisBlobRepo,
                    marks=pytest.mark.skipif(
                        "REDIS_HOST" not in os.environ or not os.environ["REDIS_HOST"],
                        reason="REDIS_HOST not set in the environment or empty",
                    ),
                ),
            ]
        metafunc.parametrize(
            "blob_repo",
            params,
            indirect=True,
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()

    if not item.config.getoption("--disallow-skip"):
        return
    if item.get_closest_marker("allow_skip"):
        return
    if rep.skipped:
        rep.outcome = "failed"
        r = call.excinfo._getreprcrash()
        rep.longrepr = f"Test should not have skipped: {r.path}:{r.lineno}: {r.message}"


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--disallow-skip",
        action="store_true",
        default=False,
    )
