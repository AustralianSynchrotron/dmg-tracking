from pytz import timezone
from flask import Blueprint, current_app
from datetime import datetime, timedelta
from portalapi import Authentication, PortalAPI
from portalapi.exceptions import AuthenticationFailed, RequestFailed
from voluptuous import Schema, Required, Coerce, Any, Boolean, Email, REMOVE_EXTRA
from mongoengine.errors import NotUniqueError, InvalidDocumentError

from .utils import sanitize_keys, convert_dict_to_update
from app.models import (Dataset, Visit, VisitType, PrincipalInvestigator,
                        Organisation, StorageEvent, LifecycleEvent, Policy)
from toolset.decorators import dataschema
from toolset import ApiResponse, ApiError, StatusCode


api = Blueprint('dataset', __name__, url_prefix='/dataset')


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Dataset API
# ---------------------------------------------------------------------------------------------------------------------
@api.route('', methods=['POST'])
@dataschema(Schema({
    Required('epn'): str
}, extra=REMOVE_EXTRA), format='json')
def create_dataset(epn):
    """
    Create a new, dataset for an EPN and a beamline.

    The visit information is being retrieved from the User Portal API.

    ---
    parameters:
      - name: epn
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
        new_ds = Dataset(epn=epn, notes='',
                         visit=_get_visit_from_portal(epn),
                         storage=[], state=State())
        new_ds.save()
        return ApiResponse({
            'id': str(new_ds.id),
            'epn': epn,
            'beamline': new_ds.visit.beamline,
            'pi': '{} {}'.format(new_ds.visit.pi.first_names, new_ds.visit.pi.last_name)
        })
    except NotUniqueError:
        raise ApiError(StatusCode.BadRequest,
                       'Dataset with EPN {} already exist'.format(epn))


@api.route('', methods=['GET'])
@dataschema(Schema({
    'epn': str,
    'beamline': str,
    'email': Email()
}, extra=REMOVE_EXTRA))
def search_datasets(**kwargs):
    params_map = {
        'beamline': 'visit.beamline',
        'email': 'visit.pi.email'
    }

    query = {sanitize_keys(params_map.get(k, k)): v for k, v in kwargs.items()}
    ds = Dataset.objects(**query)
    if ds is not None:
        return ApiResponse({'datasets': [_build_dataset_response(d) for d in ds]})
    else:
        raise ApiError(
            StatusCode.InternalServerError,
            'An error occured while searching for the dataset')


@api.route('/<epn>', methods=['GET'])
def retrieve_dataset(epn):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            # hand craft the response message in order to decouple the internal database
            # design from the interface
            return ApiResponse(_build_dataset_response(ds))
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
def update_visit(epn):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            ds.visit = _get_visit_from_portal(epn)
            ds.save()

            return ApiResponse({
                'epn': epn,
                'id': str(ds.id),
                'beamline': ds.visit.beamline,
                'pi': '{} {}'.format(ds.visit.pi.first_names,
                                     ds.visit.pi.last_name)
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
    Required('name'): str,
    Required('host'): str,
    Required('path'): str,
    Required('size'): Coerce(int),
    Required('count'): Coerce(int),
    Required('error'): str
}, extra=REMOVE_EXTRA), format='json')
def add_storage_event(epn, name, **kwargs):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            if name not in ds.storage:
                ds.storage[name] = []

            ds.storage[name].append(
                StorageEvent(created_at=datetime.now(tz=current_app.config['TIMEZONE']), **kwargs)
            )
            ds.save()

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


@api.route('/<epn>/storage', methods=['GET'])
def retrieve_storage_details(epn):
    """ Retrieve all storage entries with their full history"""
    pass


@api.route('/<epn>/storage/last', methods=['GET'])
def retrieve_storage_last(epn):
    """ Retrieve all storage entries with their most recent history entry"""
    pass


@api.route('/<epn>/lifecycle', methods=['POST'])
@dataschema(Schema({
    Required('type'): Any('normal', 'expired', 'renewed', 'deleted'), # build schema in which renewed requires an extension time in days and if not given uses policy
    Required('user_id'): Coerce(int),
    Required('user_name'): str,
    Required('notes'): str
}, extra=REMOVE_EXTRA), format='json')
def add_lifecycle_event(epn, name, **kwargs):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            ds.lifecycle.append(
                LifecycleEvent(created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                               **kwargs)
            )
            ds.save()

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


@api.route('/<epn>/lifecycle', methods=['GET'])
def retrieve_lifecycle_details(epn):
    """ Retrieve all lifecycle events"""
    pass


@api.route('/<epn>/lifecycle/last', methods=['GET'])
def retrieve_lifecycle_last(epn):
    """ Retrieve most recent lifecycle event"""
    pass


# ---------------------------------------------------------------------------------------------------------------------
#                                             Private Functions
# ---------------------------------------------------------------------------------------------------------------------
def _get_visit_from_portal(epn):
    """ Get the visit information from the User Portal and return a MongoDB visit object.

    :return:
    """
    try:
        auth = Authentication(
            client_name=current_app.config['PORTAL_SETTINGS']['client'],
            client_password=current_app.config['PORTAL_SETTINGS']['password'],
            url=current_app.config['PORTAL_SETTINGS']['host']
        )
        auth.login()
    except AuthenticationFailed as e:
        raise ApiError(StatusCode.BadRequest,
                       'Could not connect to the User Portal: {}'.format(e))

    # get visit information for the specified EPN
    api = PortalAPI(auth)

    try:
        vp = api.get_visit(epn, is_epn=True)
        equipment = api.get_equipment(vp.equipment_id)

    except RequestFailed as e:
        raise ApiError(StatusCode.BadRequest,
                       'An error occurred when contacting the User Portal: {}'.format(e))

    # create a MongoDB Engine Visit object
    return Visit(
        id=vp.id,
        start_date=vp.start_time,
        end_date=vp.end_time,
        title=vp.proposal.title,
        beamline=equipment.name_short,
        type=VisitType(
            id=vp.proposal.type.id,
            name_short=vp.proposal.type.name_short,
            name_long=vp.proposal.type.name_long
        ),
        pi=PrincipalInvestigator(
            id=vp.principal_scientist.id,
            first_names=vp.principal_scientist.first_names,
            last_name=vp.principal_scientist.last_name,
            email=vp.principal_scientist.email,
            org=Organisation(
                id=vp.principal_scientist.organisation.id,
                name_short=vp.principal_scientist.organisation.name_short,
                name_long=vp.principal_scientist.organisation.name_long
            )
        )
    )


def _build_dataset_response(dataset):
    # build the dictionary for all named storage items with their most recent history entry
    storage_dict = {}
    for name, event in dataset.storage.items():
        last_event = event[-1]
        storage_dict[name] = {
            'available': (last_event.size is not None) and (last_event.count is not None) and
                         ((not last_event.error) or (last_event.error is not None)),
            'host': last_event.host,
            'path': last_event.path,
            'size': last_event.size,
            'count': last_event.count,
            'error': last_event.error
        }

    # build the dictionary for the most recent lifecycle event
    if len(dataset.lifecycle) > 0:
        last_event = dataset.lifecycle[-1]
        lifecycle_dict = {
            'type': last_event.type,
            'expires_on': last_event.expires_on.replace(tzinfo=timezone('UTC'))
                          .astimezone(current_app.config['TIMEZONE']).isoformat(),
            'user_id': last_event.user_id,
            'user_name': last_event.user_name,
            'notes': last_event.notes
        }
    else:
        lifecycle_dict = {}

    return {
        'epn': dataset.epn,
        'beamline': dataset.visit.beamline,

        #'state': state of most recent lifecycle item
        #'expires_on': of most recent lifecycle item

        #'available': all storage items must be available
        #'size': total size of all storage items
        #'count': total size of all storage items

        'type': dataset.visit.type.name_short,
        'email': dataset.visit.pi.email,
        'org': dataset.visit.pi.org.name_short,

        'notes': dataset.notes,
        'visit': {
            'id': dataset.visit.id,
            'start': dataset.visit.start_date.replace(tzinfo=timezone('UTC'))
                     .astimezone(current_app.config['TIMEZONE']).isoformat(),
            'end': dataset.visit.end_date.replace(tzinfo=timezone('UTC'))
                   .astimezone(current_app.config['TIMEZONE']).isoformat(),
            'title': dataset.visit.title,
            'type': {
                'id': dataset.visit.type.id,
                'name': dataset.visit.type.name_long
            },
            'pi': {
                'id': dataset.visit.pi.id,
                'first_names': dataset.visit.pi.first_names,
                'last_name': dataset.visit.pi.last_name,
                'org': {
                    'id': dataset.visit.pi.org.id,
                    'name': dataset.visit.pi.org.name_long
                }
            }
        }
    }
