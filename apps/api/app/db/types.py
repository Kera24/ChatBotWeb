from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import UserDefinedType


class PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        return f"vector({self.dimensions})"


@compiles(PgVector, "sqlite")
def compile_pgvector_sqlite(type_: PgVector, compiler: object, **kw: object) -> str:
    return "TEXT"


@compiles(PgVector, "postgresql")
def compile_pgvector_postgresql(type_: PgVector, compiler: object, **kw: object) -> str:
    return f"vector({type_.dimensions})"
