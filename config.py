import os
from tzlocal import get_localzone


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', default='super-secret-phrase')
    TIMEZONE = get_localzone()

    PORTAL_SETTINGS = {
        'host': os.environ.get('PORTAL_HOST', default='localhost'),
        'client': os.environ.get('PORTAL_CLIENT', default=None),
        'password': os.environ.get('PORTAL_PASSWORD', default=None),
    }

    MONGODB_SETTINGS = {
        'db': os.environ.get('MONGODB_DB', default='data_mgmt'),
        'host': os.environ.get('MONGODB_HOST', default='localhost'),
        'port': int(os.environ.get('MONGODB_PORT', default=27017)),
    }

    SWAGGER = {
        'specs_route': '/docs/'
    }
