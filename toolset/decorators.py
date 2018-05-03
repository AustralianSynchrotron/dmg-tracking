from functools import wraps
from voluptuous import Invalid
from flask import request
from datetime import datetime

from .response import StatusCode, ApiError


def DateField(fmt='%d/%m/%Y %H:%M:%S'):
    return lambda v: datetime.strptime(v, fmt)


def dataschema(schema, format='form'):
    """ Decorator for input validation of endpoints. """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                if format == 'form':
                    kwargs.update(schema(request.values.to_dict()))
                elif format == 'json':
                    body = request.get_json()
                    if body is not None:
                        kwargs.update(schema(body))
                    else:
                        raise ApiError(StatusCode.BadRequest,
                                       'No JSON found in the request body')
                else:
                    raise RuntimeError('format has to be either form or json')
            except Invalid as err:
                raise ApiError(StatusCode.BadRequest,
                               'Invalid data: {} ({})'.format(err.msg, str(err.path)))
            return fn(*args, **kwargs)
        return wrapper
    return decorator
