import logging
from flask import json, Response


class StatusCode:
    Ok = 200
    BadRequest = 400
    Unauthorized = 401
    NotFound = 404
    MethodNotAllowed = 405
    UnprocessableEntity = 422
    InternalServerError = 500


class ApiResponse:

    def __init__(self, value, status=StatusCode.Ok):
        self._value = value
        self._status = status

    def to_flask_response(self):
        return Response(json.dumps(self._value),
                        status=self._status,
                        mimetype='application/json')


class ApiError(RuntimeError):

    def __init__(self, status, message):
        self._status = status
        self._message = message

    def to_flask_response(self):
        logger = logging.getLogger(__name__)
        logger.error(self._message)
        return ApiResponse({'error': self._message},
                           status=self._status)
