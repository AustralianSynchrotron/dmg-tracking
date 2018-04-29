from mongoengine.queryset.transform import MATCH_OPERATORS


def sanitize_keys(key):
    # Make sure all '.' are replaced with '__' and if the last field is a mongodb
    # operator append a '__'.
    tokens = key.split('.')
    if tokens[-1] in MATCH_OPERATORS:
        tokens[-1] += '__'
    return '__'.join(tokens)
