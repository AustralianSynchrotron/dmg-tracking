import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-phrase'

    MONGODB_SETTINGS = {
        'db': 'data_mgmt',
        'host': 'localhost',
        'port': 27017
    }

    SWAGGER = {
        'specs_route': '/docs/'
    }
