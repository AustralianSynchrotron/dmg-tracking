from flask import Flask

from .response import ApiResponse


class Service(Flask):

    def make_response(self, rv):
        if isinstance(rv, ApiResponse):
            return rv.to_flask_response()
        return Flask.make_response(self, rv)
