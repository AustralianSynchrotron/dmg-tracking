from mongoengine import (EmbeddedDocumentField, ListField, MapField, StringField, IntField,
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


class StorageEvent(db.EmbeddedDocument):
    created_at = DateTimeField()
    host = StringField()
    path = StringField()
    size = IntField()
    count = IntField()
    error = StringField()


class LifecycleEvent(db.EmbeddedDocument):
    type = StringField()
    created_at = DateTimeField()
    expires_on = DateTimeField()
    user_id = IntField()
    user_name = StringField()
    notes = StringField()


class Dataset(db.Document):
    epn = StringField(required=True, unique=True)
    notes = StringField()
    visit = EmbeddedDocumentField(Visit)
    storage = MapField(ListField(EmbeddedDocumentField(StorageEvent)))  # map the name of a storage to a list of events
    lifecycle = ListField(EmbeddedDocumentField(LifecycleEvent))
