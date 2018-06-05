from pytz import timezone
from flask import current_app


def utc_to_local(utc_datetime):
    return utc_datetime.replace(tzinfo=timezone('UTC'))\
        .astimezone(current_app.config['TIMEZONE'])
