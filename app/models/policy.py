from mongoengine import (StringField, IntField, ListField)

from app import db


class Policy(db.Document):
    beamline = StringField(required=True, unique=True)
    retention = IntField()
    quota = IntField()
    exclude = ListField(IntField())
    notes = StringField(default='')
