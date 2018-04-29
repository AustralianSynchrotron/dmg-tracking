from mongoengine import (ListField, EmbeddedDocumentField, StringField, IntField,
                         BooleanField, DateTimeField, EmailField)

from app import db


class PrincipalInvestigator(db.EmbeddedDocument):
    id = IntField()
    first_names = StringField()
    last_name = StringField()
    email = EmailField()


class Visit(db.EmbeddedDocument):
    id = IntField()
    start_date = DateTimeField()
    end_date = DateTimeField()
    type = StringField()
    pi = EmbeddedDocumentField(PrincipalInvestigator)


class Storage(db.EmbeddedDocument):
    last_modified = DateTimeField()
    available = BooleanField()
    name = StringField()
    host = StringField()
    path = StringField()
    size = IntField()
    size_error = StringField()
    count = IntField()
    count_error = StringField()


class State(db.EmbeddedDocument):
    expiry_date = DateTimeField()
    intention = StringField()
    reason = StringField()


class Dataset(db.Document):
    epn = StringField(required=True, unique=True)
    beamline = StringField(required=True)
    notes = StringField()
    visit = EmbeddedDocumentField(Visit)
    storage = ListField(EmbeddedDocumentField(Storage))
    state = EmbeddedDocumentField(State)
