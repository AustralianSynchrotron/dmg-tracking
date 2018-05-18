from mongoengine import (ListField, EmbeddedDocumentField, StringField, IntField,
                         BooleanField, DateTimeField, EmailField)

from app import db


class Organisation(db.EmbeddedDocument):
    id = IntField()
    name_short = StringField()
    name_long = StringField()


class PrincipalInvestigator(db.EmbeddedDocument):
    id = IntField()
    first_names = StringField()
    last_name = StringField()
    email = EmailField()
    org = EmbeddedDocumentField(Organisation, default=Organisation())


class VisitType(db.EmbeddedDocument):
    id = IntField()
    name_short = StringField()
    name_long = StringField()


class Visit(db.EmbeddedDocument):
    id = IntField()
    start_date = DateTimeField()
    end_date = DateTimeField()
    title = StringField()
    beamline = StringField()
    type = EmbeddedDocumentField(VisitType, default=VisitType())
    pi = EmbeddedDocumentField(PrincipalInvestigator, default=PrincipalInvestigator())


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


class Event(db.EmbeddedDocument):
    type = StringField()
    date = DateTimeField()
    user_id = IntField()
    user_name = StringField()
    comments = StringField()


class State(db.EmbeddedDocument):
    expiry_date = DateTimeField()
    to_delete = BooleanField()
    history = ListField(EmbeddedDocumentField(Event))


class Dataset(db.Document):
    epn = StringField(required=True, unique=True)
    notes = StringField()
    visit = EmbeddedDocumentField(Visit)
    storage = ListField(EmbeddedDocumentField(Storage))
    state = EmbeddedDocumentField(State)
