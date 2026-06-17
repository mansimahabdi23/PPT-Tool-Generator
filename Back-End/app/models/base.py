"""Shared base model that serialises to camelCase JSON — mirroring the TypeScript contract."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """All wire models inherit this to get camelCase aliases automatically.

    ``populate_by_name=True`` allows constructing models with snake_case field
    names in Python (e.g. tests, fixtures) while still serialising as camelCase.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
