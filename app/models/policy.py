from mongoengine import (StringField, IntField)

from app import db


class Policy(db.Document):
    beamline = StringField(required=True, unique=True)
    retention = IntField()
    quota = IntField()
    notes = StringField(default='')
