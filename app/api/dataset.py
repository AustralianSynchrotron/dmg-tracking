import json
from datetime import datetime, timedelta
from flask import Blueprint
from voluptuous import Schema, Required, Coerce, Boolean, Email, REMOVE_EXTRA
from mongoengine.errors import NotUniqueError, InvalidDocumentError

from .utils import sanitize_keys
from app.models import Dataset, Visit, PrincipalInvestigator, Storage, State, Policy
from toolset.decorators import dataschema, DateField
from toolset import ApiResponse, ApiError, StatusCode


api = Blueprint('dataset', __name__, url_prefix='/dataset')


@api.route('', methods=['POST'])
@dataschema(Schema({
    Required('epn'): str,
    Required('beamline'): str
}, extra=REMOVE_EXTRA))
def create_dataset(epn, beamline):
    """
    Create a new, empty dataset for an EPN and a beamline.
    ---
    parameters:
      - name: epn
        in: query
        type: string
        required: true
      - name: beamline
        in: query
        type: string
        required: true
    responses:
      200:
        description: The EPN and the id of the newly created dataset
        examples:
          epn: 1234a
          id: 5ae30aa3aaaa2f4d8096f575
    """
    try:
        new_ds = Dataset(epn=epn, beamline=beamline, notes='',
                         visit=Visit(), storage=[], state=State())
        new_ds.save()
        return ApiResponse({
            'epn': epn,
            'beamline': beamline,
            'id': str(new_ds.id)
        })
    except NotUniqueError:
        raise ApiError(StatusCode.BadRequest,
                       'Dataset with EPN {} already exist'.format(epn))


@api.route('', methods=['GET'])
@dataschema(Schema({
    'epn': str,
    'beamline': str,
    'visit.pi.email': Email()
}, extra=REMOVE_EXTRA))
def search_dataset(**kwargs):
    query = {sanitize_keys(k): v for k, v in kwargs.items()}
    ds = Dataset.objects(**query)
    if ds is not None:
        return ApiResponse({'datasets': json.loads(ds.to_json())})
    else:
        raise ApiError(
            StatusCode.InternalServerError,
            'An error occured while searching for the dataset')


@api.route('/<epn>', methods=['GET'])
def retrieve_dataset(epn):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            return ApiResponse(json.loads(ds.to_json()))
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))
    except InvalidDocumentError:
        raise ApiError(
                StatusCode.InternalServerError,
                'The dataset for EPN {} seems to be damaged'.format(epn))


@api.route('/<epn>', methods=['DELETE'])
def delete_dataset(epn):
    ds = Dataset.objects(epn=epn).first()
    if ds is not None:
        ds.delete()
        return ApiResponse({'epn': epn})
    else:
        raise ApiError(
            StatusCode.InternalServerError,
            'Dataset with EPN {} does not exist'.format(epn))


@api.route('/<epn>/visit', methods=['PUT'])
@dataschema(Schema({
    'id': Coerce(int),
    'start_date': DateField(),
    'end_date': DateField(),
    'type': str,
    'pi.id': Coerce(int),
    'pi.first_names': str,
    'pi.last_name': str,
    'pi.email': Email(),
    'pi.org.id': Coerce(int),
    'pi.org.name': str,
}, extra=REMOVE_EXTRA))
def update_visit(epn, **kwargs):
    try:
        ds_query = Dataset.objects(epn=epn)
        ds = ds_query.first()
        if ds is not None:

            # update the visit information
            update_dict = {
                'set__visit__' + sanitize_keys(k): v for k, v in kwargs.items()
            }
            ds_query.update_one(**update_dict)

            # if the visit start date is being set and the expiry date
            # hasn't been set yet, set it based on the beamline policy
            pl = Policy.objects(beamline=ds.beamline).first()
            if ('start_date' in kwargs) and (ds.state.expiry_date is None) \
                    and (pl is not None):
                ds_query.update_one(set__state__expiry_date=kwargs['start_date'] +
                                    timedelta(days=pl.retention))

            return ApiResponse({
                'epn': epn,
                'id': str(ds.id)
            })
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))
    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The dataset for EPN {} seems to be damaged'.format(epn))


@api.route('/<epn>/storage', methods=['POST'])
@dataschema(Schema({
    Required('available'): Boolean(),
    Required('name'): str,
    Required('host'): str,
    Required('path'): str,
    Required('size'): Coerce(int),
    Required('size_error'): str,
    Required('count'): Coerce(int),
    Required('count_error'): str
}, extra=REMOVE_EXTRA))
def add_storage(epn, **kwargs):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            ds.storage.append(Storage(last_modified=datetime.now(), **kwargs))
            ds.save()
            return ApiResponse({
                'epn': epn,
                'id': str(ds.id),
                'index': len(ds.storage) - 1
            })
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))
    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The dataset for EPN {} seems to be damaged'.format(epn))


@api.route('/<epn>/storage/<int:index>', methods=['PUT'])
@dataschema(Schema({
    'available': Boolean(),
    'name': str,
    'host': str,
    'path': str,
    'size': Coerce(int),
    'size_error': str,
    'count': Coerce(int),
    'count_error': str
}, extra=REMOVE_EXTRA))
def update_storage(epn, index, **kwargs):
    try:
        ds = Dataset.objects(epn=epn)
        if ds.first() is not None:
            if (index < 0) or (index >= len(ds.first().storage)):
                raise ApiError(
                    StatusCode.InternalServerError,
                    'The storage index {} is not valid'.format(index))

            kwargs['last_modified'] = datetime.now()

            update_dict = {
                'set__storage__{}__{}'.format(index, sanitize_keys(k)):
                    v for k, v in kwargs.items()
            }
            ds.update_one(**update_dict)

            return ApiResponse({
                'epn': epn,
                'id': str(ds.first().id)
            })
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))
    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The dataset for EPN {} seems to be damaged'.format(epn))
