import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set")


class Config(BaseSettings):
    app_name: str = "Project management dashboard"
    db_host: str
    db_port: int = 5432
    db_user: str
    db_password: str
    db_name: str
    aws_access_key_id: str # Validate variables types
    aws_secret_access_key: str
    aws_default_region: str = "us-east-1"
    s3_bucket_name: str
    max_file_size: int = 104857600 # 100 MB as MiB
    max_docs: int = 50
    max_projects: int = 10

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


config = Config()


# TODO: ADD THIS TO CONFIG!
# JWT related:
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
