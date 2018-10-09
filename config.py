import os
import distutils.util
from tzlocal import get_localzone

from app.version import __version__


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', default='super-secret-phrase')
    TIMEZONE = get_localzone()

    PORTAL_SETTINGS = {
        'host': os.environ.get('PORTAL_HOST', default='localhost'),
        'client': os.environ.get('PORTAL_CLIENT', default=None),
        'password': os.environ.get('PORTAL_PASSWORD', default=None),
        'verify': distutils.util.strtobool(os.environ.get('PORTAL_VERIFY', default='True'))
    }

    MONGODB_SETTINGS = {
        'db': os.environ.get('MONGODB_DB', default='data_mgmt'),
        'host': os.environ.get('MONGODB_HOST', default='localhost'),
        'port': int(os.environ.get('MONGODB_PORT', default=27017)),
    }

    SWAGGER = {
        'specs_route': '/docs/',
        'title': 'dmg-tracking API Documentation',
        'uiversion': 3,
        'description': 'This page describes the RESTful API of the dmg-tracking '+
                       'microservice. All request parameters and the full response '+
                       'content for each endpoint is described.',
        'termsOfService': '',
        "version": __version__
    }
