# from contextlib import asynccontextmanager
from fastapi import FastAPI

# from .db.database import init_db
from .core.config import config
from .routers import users, projects


# Init database before the app runs. Only use if Alembic migrations are not used
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     init_db()
#     yield

# app = FastAPI(title=config.app_name, lifespan=lifespan)
app = FastAPI(title=config.app_name)


app.include_router(users.router)
app.include_router(projects.router)


@app.get("/")
async def root():
    return {"message": "This is a Project Management Dashboard Application"}
