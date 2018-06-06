from mongoengine import (EmbeddedDocumentField, ReferenceField, ListField, MapField,
                         StringField, IntField, DateTimeField, EmailField, DENY)

from app import db
from app.models.policy import Policy


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


class LifecycleState(db.EmbeddedDocument):
    type = StringField()
    created_at = DateTimeField()
    expires_on = DateTimeField()
    user_id = IntField()
    user_name = StringField()
    notes = StringField()


class Dataset(db.Document):
    epn = StringField(required=True, unique=True)
    notes = StringField()
    policy = ReferenceField(Policy, dbref=True, reverse_delete_rule=DENY)
    visit = EmbeddedDocumentField(Visit)
    storage = MapField(ListField(EmbeddedDocumentField(StorageEvent)))
    lifecycle = ListField(EmbeddedDocumentField(LifecycleState))
