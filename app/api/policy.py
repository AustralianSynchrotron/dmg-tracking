import json
from flask import Blueprint
from voluptuous import Schema, Required, Coerce, REMOVE_EXTRA
from mongoengine.errors import NotUniqueError, InvalidDocumentError

from .utils import sanitize_keys
from app.models import Policy
from toolset.decorators import dataschema
from toolset import ApiResponse, ApiError, StatusCode


api = Blueprint('policy', __name__, url_prefix='/policy')


@api.route('', methods=['POST'])
@dataschema(Schema({
    Required('beamline'): str,
    Required('retention'): Coerce(int),
    Required('quota'): Coerce(int),
    'notes': str
}, extra=REMOVE_EXTRA))
def create_policy(beamline, **kwargs):
    try:
        new_pl = Policy(beamline=beamline, **kwargs)
        new_pl.save()
        return ApiResponse({
            'beamline': beamline,
            'id': str(new_pl.id)
        })
    except NotUniqueError:
        raise ApiError(StatusCode.BadRequest,
                       'A policy for {} already exist'.format(beamline))


@api.route('/<beamline>', methods=['GET'])
def retrieve_policy(beamline):
    try:
        pl = Policy.objects(beamline=beamline).first()
        if pl is not None:
            return ApiResponse(json.loads(pl.to_json()))
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'A policy for {} does not exist'.format(beamline))
    except InvalidDocumentError:
        raise ApiError(
                StatusCode.InternalServerError,
                'The policy for {} seems to be damaged'.format(beamline))


@api.route('/<beamline>', methods=['PUT'])
@dataschema(Schema({
    'retention': Coerce(int),
    'quota': Coerce(int),
    'notes': str
}, extra=REMOVE_EXTRA))
def update_policy(beamline, **kwargs):
    try:
        pl = Policy.objects(beamline=beamline)
        if pl.first() is not None:
            update_dict = {'set__' + sanitize_keys(k): v for k, v in kwargs.items()}
            pl.update_one(**update_dict)

            return ApiResponse({
                'beamline': beamline,
                'id': str(pl.first().id)
            })
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'A policy for {} does not exist'.format(beamline))
    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The policy for {} seems to be damaged'.format(beamline))


@api.route('/<beamline>', methods=['DELETE'])
def delete_policy(beamline):
    pl = Policy.objects(beamline=beamline).first()
    if pl is not None:
        pl.delete()
        return ApiResponse({'beamline': beamline})
    else:
        raise ApiError(
            StatusCode.InternalServerError,
            'Policy for {} does not exist'.format(beamline))