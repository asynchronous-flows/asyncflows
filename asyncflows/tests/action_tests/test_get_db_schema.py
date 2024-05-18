from unittest.mock import patch

import pytest

from asyncflows.actions.get_db_schema import Inputs, Outputs, GetDBSchema


@pytest.fixture
def action(log, temp_dir):
    return GetDBSchema(log=log, temp_dir=temp_dir)


@pytest.fixture
def dummy_sqlite_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import Column, Integer, String

    Base = declarative_base()

    class User(Base):
        __tablename__ = "users"

        id = Column(Integer, primary_key=True)
        name = Column(String)
        fullname = Column(String)
        nickname = Column(String)

        def __repr__(self):
            return f"<User(name={self.name}, fullname={self.fullname}, nickname={self.nickname})>"

    engine = create_engine("sqlite:///:memory:", echo=True, future=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    ed_user = User(name="ed", fullname="Ed Jones", nickname="edsnickname")
    session.add(ed_user)
    session.commit()

    return engine


@pytest.mark.parametrize(
    "inputs, expected_outputs",
    [
        (
            Inputs(database_url="DUMMY"),
            Outputs(
                schema_text="""
CREATE TABLE users (
\tid INTEGER NOT NULL, 
\tname VARCHAR, 
\tfullname VARCHAR, 
\tnickname VARCHAR, 
\tPRIMARY KEY (id)
)

"""
            ),
        ),
    ],
)
async def test_get_db_schema(dummy_sqlite_engine, action, inputs, expected_outputs):
    with patch(
        "asyncflows.actions.get_db_schema.create_engine",
        return_value=dummy_sqlite_engine,
    ):
        outputs = await action.run(inputs)
    assert outputs == expected_outputs
