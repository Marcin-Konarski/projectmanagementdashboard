from sqlmodel import SQLModel, create_engine

from ..core.config import config

engine = create_engine(config.db_url, echo=True)


def init_db():
    SQLModel.metadata.create_all(engine)
