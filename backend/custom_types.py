from typing import Annotated
from pydantic import Field

Name = Annotated[str, Field(min_length=3, max_length=50)]


# TODO: consider implementing DI: https://fastapi.tiangolo.com/tutorial/dependencies/

# test changes to backend
