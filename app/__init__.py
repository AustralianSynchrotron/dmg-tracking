from werkzeug.utils import find_modules, import_string
from flask_mongoengine import MongoEngine
from flasgger import Swagger
from flask_cors import CORS

from config import Config
from toolset import StatusCode, ApiError, Service


db = MongoEngine()
cors = CORS()
swg = Swagger()


def register_apis(app):
    for name in find_modules('app.api'):
        mod = import_string(name)
        if hasattr(mod, 'api'):
            app.register_blueprint(mod.api)


def register_error_handlers(app):
    app.register_error_handler(ApiError, lambda err: err.to_flask_response())
    app.register_error_handler(StatusCode.NotFound,
                               lambda err: ApiError(
                                   StatusCode.NotFound,
                                   'The requested endpoint does not exist').
                               to_flask_response())
    app.register_error_handler(StatusCode.MethodNotAllowed,
                               lambda err: ApiError(
                                   StatusCode.MethodNotAllowed,
                                   'The HTTP method is not allowed for this endpoint').
                               to_flask_response())


def create_app(config_class=Config):
    app = Service(__name__)
    app.config.from_object(config_class)

    register_apis(app)
    register_error_handlers(app)

    db.init_app(app)
    cors.init_app(app)
    swg.init_app(app)

    return app
