from decimal import Decimal
from functools import wraps
from werkzeug.routing import BaseConverter

from .logging import logger



class DecimalConverter(BaseConverter):

    def to_python(self, value):
        return Decimal(value)

    def to_url(self, value):
        return BaseConverter.to_url(value)


def skip_if_running(f):
    task_name = f'{f.__module__}.{f.__name__}'

    @wraps(f)
    def wrapped(self, *args, **kwargs):
        workers = self.app.control.inspect().active()

        for worker, tasks in workers.items():
            for task in tasks:
                if (task_name == task['name'] and
                        tuple(args) == tuple(task['args']) and
                        kwargs == task['kwargs'] and
                        self.request.id != task['id']):
                    logger.debug(f'task {task_name} ({args}, {kwargs}) is running on {worker}, skipping')

                    return None
        logger.debug(f'task {task_name} ({args}, {kwargs}) is allowed to run')
        return f(self, *args, **kwargs)

    return wrapped
