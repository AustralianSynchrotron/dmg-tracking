from functools import wraps
from voluptuous import Invalid
from flask import request
from datetime import datetime

from .response import StatusCode, ApiError


def DateField(fmt='%d/%m/%Y %H:%M:%S'):
    return lambda v: datetime.strptime(v, fmt)


def dataschema(schema):
    """ Decorator for input validation of endpoints. """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                kwargs.update(schema(request.values.to_dict()))
            except Invalid as err:
                raise ApiError(StatusCode.BadRequest,
                               'Invalid data: {} ({})'.format(err.msg, str(err.path)))
            return fn(*args, **kwargs)
        return wrapper
    return decorator
