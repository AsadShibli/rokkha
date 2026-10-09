from enum import StrEnum

from sqlalchemy import Enum


def str_enum(enum: type[StrEnum], length: int) -> Enum:
    """varchar column holding enum values; the CHECK constraint is declared on the table.

    Not a native Postgres enum: adding a value later is a plain CHECK swap in a migration.
    """
    return Enum(
        enum,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )
