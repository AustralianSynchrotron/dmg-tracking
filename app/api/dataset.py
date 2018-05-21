from flask import Blueprint, current_app
from datetime import datetime, timedelta
from portalapi import Authentication, PortalAPI
from portalapi.exceptions import AuthenticationFailed, RequestFailed
from voluptuous import Schema, Required, Optional, Coerce, Email, REMOVE_EXTRA
from mongoengine.errors import NotUniqueError, InvalidDocumentError

from .utils import sanitize_keys, utc_to_local
from .const import LifecycleStateType
from app.models import (Dataset, Visit, VisitType, PrincipalInvestigator,
                        Organisation, StorageEvent, LifecycleState, Policy)
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
        visit = _get_visit_from_portal(epn)
        pl = Policy.objects(beamline=visit.beamline).first()

        if pl is None:
            raise ApiError(
                StatusCode.InternalServerError,
                'A policy for the {} beamline does not exist'.format(visit.beamline))

        new_ds = Dataset(epn=epn, notes='',
                         visit=visit,
                         storage={},
                         lifecycle=[LifecycleState(
                             type=LifecycleStateType.NORMAL,
                             created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                             expires_on=visit.start_date + timedelta(days=pl.retention),
                             user_id=None,
                             user_name='auto',
                             notes='auto generated during dataset creation')
                         ])
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


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Visit API
# ---------------------------------------------------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Storage API
# ---------------------------------------------------------------------------------------------------------------------
@api.route('/<epn>/storage', methods=['POST'])
@dataschema(Schema({
    Required('name'): str,
    Required('host'): str,
    Required('path'): str,
    Required('size'): Coerce(int),
    Required('count'): Coerce(int),
    Optional('error', default=''): str
}, extra=REMOVE_EXTRA), format='json')
def add_storage_event(epn, name, **kwargs):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            if name not in ds.storage:
                ds.storage[name] = []

            ds.storage[name].append(
                StorageEvent(created_at=datetime.now(tz=current_app.config['TIMEZONE']),
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


@api.route('/<epn>/storage', methods=['GET'])
def retrieve_storage_details(epn):
    """ Retrieve all storage entries with their full history"""
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            response = {}
            for name, events in ds.storage.items():
                response[name] = [_build_storage_event_response(e) for e in events]

            return ApiResponse({'storage': response})
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))

    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The dataset for EPN {} seems to be damaged'.format(epn))


@api.route('/<epn>/storage/last', methods=['GET'])
def retrieve_storage_last(epn):
    """ Retrieve all storage entries with their most recent history entry"""
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            response = {}
            for name, events in ds.storage.items():
                response[name] = _build_storage_event_response(events[-1])\
                    if len(events) > 0 else {}

            return ApiResponse({'storage': response})
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))

    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The dataset for EPN {} seems to be damaged'.format(epn))


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Lifecycle API
# ---------------------------------------------------------------------------------------------------------------------
@api.route('/<epn>/lifecycle', methods=['POST'])
@dataschema(Schema({
    Optional('days', default=-1): Coerce(int),
    Required('user_id'): Coerce(int),
    Required('user_name'): str,
    Required('notes'): str
}, extra=REMOVE_EXTRA), format='json')
def add_lifecycle_renew_state(epn, days, **kwargs):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:

            # check that the dataset is in a state in which it can be renewed
            if len(ds.lifecycle) == 0:
                raise ApiError(
                    StatusCode.InternalServerError,
                    'Cannot renew a dataset that has no lifecycle state yet')

            current_state = ds.lifecycle[-1]
            if current_state.type not in [LifecycleStateType.NORMAL,
                                          LifecycleStateType.EXPIRED,
                                          LifecycleStateType.RENEWED]:
                raise ApiError(
                    StatusCode.InternalServerError,
                    'The dataset is in the wrong state and cannot be renewed')

            # if a number of days was not provided, extend expiry date by the policy
            if days < 0:
                pl = Policy.objects(beamline=ds.visit.beamline).first()
                if pl is None:
                    raise ApiError(
                        StatusCode.InternalServerError,
                        'A policy for the {} beamline does not exist'.format(
                            ds.visit.beamline))
                days = pl.retention

            ds.lifecycle.append(
                LifecycleState(
                    type=LifecycleStateType.RENEWED,
                    created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                    expires_on=utc_to_local(current_state.expires_on) +
                               timedelta(days=days),
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


@api.route('/<epn>/lifecycle', methods=['DELETE'])
@dataschema(Schema({
    Required('user_id'): Coerce(int),
    Required('user_name'): str,
    Optional('notes', default=''): str
}, extra=REMOVE_EXTRA), format='json')
def add_lifecycle_delete_state(epn, **kwargs):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            if len(ds.lifecycle) > 0:
                current_state = ds.lifecycle[-1]
            else:
                current_state = None

            # check that the dataset is in a state in which it can be deleted
            if (current_state is not None) and\
                    (current_state.type == LifecycleStateType.DELETED):
                raise ApiError(
                    StatusCode.InternalServerError,
                    'The dataset has already been marked as deleted')

            ds.lifecycle.append(
                LifecycleState(
                    type=LifecycleStateType.DELETED,
                    created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                    expires_on=None,
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


@api.route('/<epn>/lifecycle', methods=['PUT'])
def update_lifecycle_expiry_state(epn):
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:

            if len(ds.lifecycle) == 0:
                raise ApiError(
                    StatusCode.InternalServerError,
                    'Cannot renew a dataset that has no lifecycle state yet')

            current_state = ds.lifecycle[-1]

            # check that the dataset is in the correct state
            if current_state.type in [LifecycleStateType.NORMAL,
                                      LifecycleStateType.RENEWED]:

                # check whether it has expired
                if datetime.now(tz=current_app.config['TIMEZONE']) > \
                        utc_to_local(current_state.expires_on):

                    ds.lifecycle.append(
                        LifecycleState(
                            type=LifecycleStateType.EXPIRED,
                            created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                            expires_on=utc_to_local(current_state.expires_on),
                            user_id=None,
                            user_name='auto',
                            notes='auto generated during expiry date update')
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
    """ Retrieve all lifecycle state"""
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            return ApiResponse({
                'lifecycle': [_build_lifecycle_state_response(ls)
                              for ls in ds.lifecycle][::-1]
            })
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))

    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The dataset for EPN {} seems to be damaged'.format(epn))


@api.route('/<epn>/lifecycle/last', methods=['GET'])
def retrieve_lifecycle_last(epn):
    """ Retrieve most recent lifecycle state"""
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            return ApiResponse(_build_lifecycle_state_response(ds.lifecycle[-1])
                               if len(ds.lifecycle) > 0 else {})
        else:
            raise ApiError(
                StatusCode.InternalServerError,
                'Dataset with EPN {} does not exist'.format(epn))

    except InvalidDocumentError:
        raise ApiError(
            StatusCode.InternalServerError,
            'The dataset for EPN {} seems to be damaged'.format(epn))


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
    storage_items = []
    for name, event in dataset.storage.items():
        last_event = event[-1]
        storage_items.append({
            'available': (last_event.size is not None) and
                         (last_event.count is not None) and
                         ((not last_event.error) or
                          (last_event.error is not None)),
            'size': last_event.size,
            'count': last_event.count,
        })

    last_lifecycle_state = dataset.lifecycle[-1]
    return {
        'epn': dataset.epn,
        'beamline': dataset.visit.beamline,
        'state': last_lifecycle_state.type,
        'expires_on': utc_to_local(last_lifecycle_state.expires_on).isoformat()
                      if last_lifecycle_state.expires_on is not None else None,
        'available':
            all([item['available'] for item in storage_items])
            if len(storage_items) > 0 else False,
        'size': sum([item['size'] for item in storage_items]),
        'count': sum([item['count'] for item in storage_items]),
        'type': dataset.visit.type.name_short,
        'email': dataset.visit.pi.email,
        'org': dataset.visit.pi.org.name_short,
        'notes': dataset.notes,
        'visit': {
            'id': dataset.visit.id,
            'start': utc_to_local(dataset.visit.start_date).isoformat(),
            'end': utc_to_local(dataset.visit.end_date).isoformat(),
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


def _build_storage_event_response(event):
    return {
        'created_at': utc_to_local(event.created_at).isoformat(),
        'host': event.host,
        'path': event.path,
        'size': event.size,
        'count': event.count,
        'error': event.error
    }


def _build_lifecycle_state_response(state):
    return {
        'type': state.type,
        'created_at': utc_to_local(state.created_at).isoformat(),
        'expires_on': utc_to_local(state.expires_on).isoformat()
                      if state.expires_on is not None else None,
        'user_id': state.user_id,
        'user_name': state.user_name,
        'notes': state.notes
    }
