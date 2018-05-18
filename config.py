import os
from tzlocal import get_localzone


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-phrase'
    TIMEZONE = get_localzone()

    PORTAL_SETTINGS = {
        'host': os.environ.get('PORTAL_HOST') or 'localhost',
        'client': os.environ.get('PORTAL_CLIENT') or None,
        'password': os.environ.get('PORTAL_PASSWORD') or None,
    }

    MONGODB_SETTINGS = {
        'db': os.environ.get('MONGODB_DB') or 'data_mgmt',
        'host': os.environ.get('MONGODB_HOST') or 'localhost',
        'port': os.environ.get('MONGODB_PORT') or 27017,
    }

    SWAGGER = {
        'specs_route': '/docs/'
    }
