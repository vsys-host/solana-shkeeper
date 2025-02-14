import flask_sqlalchemy
from sqlalchemy.pool import NullPool

db = flask_sqlalchemy.SQLAlchemy(
    engine_options={ 'connect_args': { 'connect_timeout': 60 }, 'isolation_level': "READ COMMITTED", "poolclass": NullPool}
)

