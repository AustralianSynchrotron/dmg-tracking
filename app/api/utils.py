from pytz import timezone
from flask import current_app
from mongoengine.queryset.transform import MATCH_OPERATORS


def sanitize_keys(key):
    # Make sure all '.' are replaced with '__' and if the last field is a mongodb
    # operator append a '__'.
    tokens = key.split('.')
    if tokens[-1] in MATCH_OPERATORS:
        tokens[-1] += '__'
    return '__'.join(tokens)


def convert_dict_to_update(data_dict, root=None):
    """
    Convert a multi-level dictionary into a flat dictionary with the keys formatted for
    the update function of mongoengine.
    """
    result = {}
    for key, value in data_dict.items():
        new_root = '{}__{}'.format(root, key) if root is not None else key

        if isinstance(value, dict):
            result = {**result, **convert_dict_to_update(value, root=new_root)}
        else:
            # Make sure that if the last field is a mongodb operator append a '__'
            result['set__{}{}'.format(new_root, '__'
                   if key in MATCH_OPERATORS else '')] = value
    return result


def utc_to_local(utc_datetime):
    return utc_datetime.replace(tzinfo=timezone('UTC'))\
        .astimezone(current_app.config['TIMEZONE'])
