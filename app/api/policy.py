from flask import Blueprint
from voluptuous import Schema, Required, Optional, Coerce, REMOVE_EXTRA
from mongoengine.errors import NotUniqueError, InvalidDocumentError, OperationError

from app.models import Policy
from toolset.decorators import dataschema
from toolset import ApiResponse, ApiError, StatusCode


api = Blueprint('policy', __name__, url_prefix='/policy')


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Policy API
# ---------------------------------------------------------------------------------------------------------------------
@api.route('', methods=['POST'])
@dataschema(Schema({
    Required('beamline'): str,
    Required('retention'): Coerce(int),
    Required('quota'): Coerce(int),
    Optional('exclude', default=[]): list([int]),
    Optional('notes', default=''): str
}, extra=REMOVE_EXTRA), format='json')
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
            return ApiResponse(_build_policy_response(pl))
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
    'exclude': list([int]),
    'notes': str
}, extra=REMOVE_EXTRA), format='json')
def update_policy(beamline, **kwargs):
    try:
        pl = Policy.objects(beamline=beamline).first()
        if pl is not None:
            for key, value in kwargs.items():
                setattr(pl, key, value)

            pl.save()

            return ApiResponse({
                'beamline': beamline,
                'id': str(pl.id)
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
        try:
            pl.delete()
        except OperationError:
            raise ApiError(
                StatusCode.InternalServerError,
                'Cannot delete policy, a dataset is still using it')

        return ApiResponse({'beamline': beamline})
    else:
        raise ApiError(
            StatusCode.InternalServerError,
            'Policy for {} does not exist'.format(beamline))


# ---------------------------------------------------------------------------------------------------------------------
#                                             Private Functions
# ---------------------------------------------------------------------------------------------------------------------
def _build_policy_response(policy):
    return {
        'beamline': policy.beamline,
        'retention': policy.retention,
        'quota': policy.quota,
        'exclude': policy.exclude,
        'notes': policy.notes
    }
