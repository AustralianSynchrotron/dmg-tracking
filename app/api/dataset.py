from flask import Blueprint, current_app
from datetime import datetime, timedelta
from dateutil import parser
from distutils.util import strtobool
from portalapi import Authentication, PortalAPI
from portalapi.exceptions import AuthenticationFailed, RequestFailed
from voluptuous import (Schema, Required, Optional, Coerce, Any, Datetime, Boolean,
                        REMOVE_EXTRA)
from mongoengine.queryset.visitor import Q
from mongoengine.errors import NotUniqueError, InvalidDocumentError

from .utils import utc_to_local
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
    Create a new dataset for an existing visit

    This endpoint creates a new dataset from an EPN. It requires a policy for the
    The visit information is being retrieved from the User Portal API.

    ---
    tags:
     - Dataset
    consumes:
     - application/json
    produces:
     - application/json
    parameters:
     - name: body
       in: body
       description: Blablabla
       schema:
         type: object
         properties:
           epn:
             type: string
         required: ['epn']
         additionalProperties: false
    responses:
     200:
       description: The EPN and the id of the newly created dataset
       schema:
         properties:
           epn:
             type: string
           id:
             type: string
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

        # Excluded experiment types don't expire
        if _is_dataset_excluded(visit, pl):
            expiry_date = None
        else:
            expiry_date = visit.start_date + timedelta(days=pl.retention)

        new_ds = Dataset(epn=epn, notes='',
                         policy=pl,
                         visit=visit,
                         storage={},
                         lifecycle=[LifecycleState(
                             type=LifecycleStateType.NORMAL,
                             created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                             expires_on=expiry_date,
                             user_id=None,
                             user_name='auto',
                             notes='auto generated during dataset creation')
                         ])
        new_ds.save()
        return ApiResponse(_build_dataset_response(new_ds))
    except NotUniqueError:
        raise ApiError(StatusCode.BadRequest,
                       'Dataset with EPN {} already exist'.format(epn))


@api.route('', methods=['GET'])
@dataschema(Schema({
    'epn': str,
    'beamline': str,
    'pi_name': str,
    'pi_email': str,
    'pi_org': str,
    'status': Any(LifecycleStateType.NORMAL, LifecycleStateType.EXPIRED,
                  LifecycleStateType.RENEWED, LifecycleStateType.DROPPED,
                  LifecycleStateType.DELETED),
    'type': str,
    'excluded': str
}, extra=REMOVE_EXTRA))
def search_datasets(**kwargs):
    """
    Search for datasets

    ---
    tags:
     - Dataset
    consumes:
     - application/json
    produces:
     - application/json
    """
    query = Q()
    if 'epn' in kwargs:
        query = query & Q(epn__icontains=kwargs['epn'])

    if 'beamline' in kwargs:
        query = query & Q(visit__beamline__iexact=kwargs['beamline'])

    if 'pi_name' in kwargs:
        query = query & (Q(visit__pi__first_names__icontains=kwargs['pi_name']) |
                         Q(visit__pi__last_name__icontains=kwargs['pi_name']))

    if 'pi_email' in kwargs:
        query = query & Q(visit__pi__email__icontains=kwargs['pi_email'])

    if 'pi_org' in kwargs:
        query = query & (Q(visit__pi__org__name_short__icontains=kwargs['pi_org']) |
                         Q(visit__pi__org__name_long__icontains=kwargs['pi_org']))

    if 'status' in kwargs:
        query = query & Q(lifecycle__0__type__exact=kwargs['status'])

    if 'type' in kwargs:
        query = query & (Q(visit__type__name_short__icontains=kwargs['type']) |
                         Q(visit__type__name_long__icontains=kwargs['type']))

    ds = Dataset.objects(query)

    if ds is not None:
        # mongoDB doesn't do joins, so we have to perform the search manually
        if 'excluded' in kwargs:
            excluded = bool(strtobool(kwargs['excluded']))
            datasets = []
            for d in ds.select_related():
                if _is_dataset_excluded(d.visit, d.policy) == excluded:
                    datasets.append(d)
        else:
            datasets = ds

        return ApiResponse({'datasets': [_build_dataset_response(d) for d in datasets]})
    else:
        raise ApiError(
            StatusCode.InternalServerError,
            'An error occured while searching for the dataset')


@api.route('/<epn>', methods=['GET'])
def retrieve_dataset(epn):
    """
    Retrieve the basic information of a dataset

    More information here
    ---
    tags:
     - Dataset
    consumes:
     - application/json
    produces:
     - application/json
    parameters:
     - name: epn
       in: path
       required: true
       type: string
       description: The EPN of the experiment for which the dataset should be returned.
    responses:
      200:
        description: The EPN and the id of the newly created dataset
        examples:
          epn: 1234a
          id: 5ae30aa3aaaa2f4d8096f575
    """
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
    """
    Delete a dataset

    ---
    tags:
     - Dataset
    consumes:
     - application/json
    produces:
     - application/json
    """
    ds = Dataset.objects(epn=epn).first()
    if ds is not None:
        ds.delete()
        return ApiResponse({
            'deleted': True,
            'epn': epn
        })
    else:
        raise ApiError(
            StatusCode.InternalServerError,
            'Dataset with EPN {} does not exist'.format(epn))


# ---------------------------------------------------------------------------------------------------------------------
#                                                 Visit API
# ---------------------------------------------------------------------------------------------------------------------
@api.route('/<epn>/visit', methods=['PUT'])
def update_visit(epn):
    """
    Update the visit information of a dataset

    ---
    tags:
     - Visit
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            ds.visit = _get_visit_from_portal(epn)
            ds.save()

            return ApiResponse(_build_dataset_response(ds))
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
    """
    Add a new entry to the history of a storage item

    ---
    tags:
     - Storage
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            if name not in ds.storage:
                ds.storage[name] = []

            ds.storage[name].insert(
                0,
                StorageEvent(created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                             **kwargs)
            )
            ds.save()

            return ApiResponse(_build_storage_event_response(ds.storage[name][0]))
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
    """
    Retrieve all storage items with their full history

    ---
    tags:
     - Storage
    consumes:
     - application/json
    produces:
     - application/json
    """
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
    """
    Retrieve all storage items with their most recent history entry

    ---
    tags:
     - Storage
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            response = {}
            for name, events in ds.storage.items():
                response[name] = _build_storage_event_response(events[0])\
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
    Optional('days'): Coerce(int),
    Optional('expiry_date'): Datetime(format='%Y-%m-%dT%H:%M:%S'),
    Required('user_id'): str,
    Required('user_name'): str,
    Required('notes'): str
}, extra=REMOVE_EXTRA), format='json')
def add_lifecycle_renew_state(epn, days=None, expiry_date=None, **kwargs):
    """
    Transition a dataset to the renew state

    ---
    tags:
     - Lifecycle
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:

            # check that the dataset is not excluded from the policy
            if _is_dataset_excluded(ds.visit, ds.policy):
                raise ApiError(
                    StatusCode.InternalServerError,
                    'The policy does not allow the dataset to be renewed')

            # check that the dataset is in a state in which it can be renewed
            if len(ds.lifecycle) == 0:
                raise ApiError(
                    StatusCode.InternalServerError,
                    'Cannot renew a dataset that has no lifecycle state yet')

            current_state = ds.lifecycle[0]
            if current_state.type not in [LifecycleStateType.NORMAL,
                                          LifecycleStateType.EXPIRED,
                                          LifecycleStateType.RENEWED]:
                raise ApiError(
                    StatusCode.InternalServerError,
                    'The dataset is in the wrong state and cannot be renewed')

            # if neither a number of days was provided nor an expiry date,
            # extend the expiry date by the retention days given in the policy
            if (days is None) and (expiry_date is None):
                expires_on = utc_to_local(current_state.expires_on) +\
                             timedelta(days=ds.policy.retention)

            # if a number of days is not given but an expiry date, use the expiry date
            elif (days is None) and (expiry_date is not None):
                expires_on = current_app.config['TIMEZONE'].localize(
                    parser.parse(expiry_date))

            else:
                expires_on = utc_to_local(current_state.expires_on) + timedelta(days=days)

            ds.lifecycle.insert(
                0,
                LifecycleState(
                    type=LifecycleStateType.RENEWED,
                    created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                    expires_on=expires_on,
                    **kwargs)
            )
            ds.save()

            return ApiResponse(_build_lifecycle_state_response(ds.lifecycle[0]))
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
    Optional('removed', default=False): Boolean(),
    Required('user_id'): str,
    Required('user_name'): str,
    Optional('notes', default=''): str
}, extra=REMOVE_EXTRA), format='json')
def add_lifecycle_delete_state(epn, removed, **kwargs):
    """
    Transition a dataset to the dropped or delete state

    ---
    tags:
     - Lifecycle
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            if len(ds.lifecycle) > 0:
                current_state = ds.lifecycle[0]
            else:
                raise ApiError(
                    StatusCode.InternalServerError,
                    'The dataset is not in a valid lifecycle state')

            # check the current status of the dataset
            if removed:
                state_type = LifecycleStateType.DELETED
                if current_state.type != LifecycleStateType.DROPPED:
                    raise ApiError(
                        StatusCode.InternalServerError,
                        'The dataset has to be in the {} state before it can be deleted'
                        .format(LifecycleStateType.DROPPED))
            else:
                state_type = LifecycleStateType.DROPPED
                if current_state.type == LifecycleStateType.DROPPED:
                    raise ApiError(
                        StatusCode.InternalServerError,
                        'The dataset has already been marked for deletion')

            ds.lifecycle.insert(
                0,
                LifecycleState(
                    type=state_type,
                    created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                    expires_on=utc_to_local(current_state.expires_on)
                    if current_state is not None else None,
                    **kwargs)
            )
            ds.save()

            return ApiResponse(_build_lifecycle_state_response(ds.lifecycle[0]))
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
    """
    Transition to the expired state if the expiry date has passed

    ---
    tags:
     - Lifecycle
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            # check that the dataset is in a state in which it can be expired
            if len(ds.lifecycle) == 0:
                raise ApiError(
                    StatusCode.InternalServerError,
                    'Cannot expire a dataset that has no lifecycle state yet')

            current_state = ds.lifecycle[0]

            # check that the dataset is not excluded and in the correct state
            changed_to_expired = False
            if (not _is_dataset_excluded(ds.visit, ds.policy)) and\
                    (current_state.type in [LifecycleStateType.NORMAL,
                                            LifecycleStateType.RENEWED]):

                # check whether it has expired
                if datetime.now(tz=current_app.config['TIMEZONE']) > \
                        utc_to_local(current_state.expires_on):

                    changed_to_expired = True
                    ds.lifecycle.insert(
                        0,
                        LifecycleState(
                            type=LifecycleStateType.EXPIRED,
                            created_at=datetime.now(tz=current_app.config['TIMEZONE']),
                            expires_on=utc_to_local(current_state.expires_on),
                            user_id=None,
                            user_name='auto',
                            notes='auto generated during expiry date update')
                    )
                    ds.save()

            return ApiResponse({**_build_lifecycle_state_response(ds.lifecycle[0]),
                                **{'changed': changed_to_expired}})
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
    """
    Retrieve all lifecycle states

    ---
    tags:
     - Lifecycle
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            return ApiResponse({
                'lifecycle': [_build_lifecycle_state_response(ls) for ls in ds.lifecycle]
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
    """
    Retrieve most recent lifecycle state

    ---
    tags:
     - Lifecycle
    consumes:
     - application/json
    produces:
     - application/json
    """
    try:
        ds = Dataset.objects(epn=epn).first()
        if ds is not None:
            return ApiResponse(_build_lifecycle_state_response(ds.lifecycle[0])
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
            url=current_app.config['PORTAL_SETTINGS']['host'],
            verify=current_app.config['PORTAL_SETTINGS']['verify']
        )
        auth.login()
    except AuthenticationFailed as e:
        raise ApiError(StatusCode.BadRequest,
                       'Could not connect to the User Portal: {}'.format(e))

    # get visit information for the specified EPN
    portal_api = PortalAPI(auth)

    try:
        vp = portal_api.get_visit(epn, is_epn=True)
        equipment = portal_api.get_equipment(vp.equipment_id)

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


def _is_dataset_excluded(visit, policy):
    return (visit.type.id in policy.exclude_type) or\
           (visit.pi.org.id in policy.exclude_org)


def _build_dataset_response(dataset):
    storage_items = []
    for name, event in dataset.storage.items():
        last_event = event[0]
        storage_items.append({
            'available': (last_event.size is not None) and
                         (last_event.count is not None) and
                         ((not last_event.error) or
                          (last_event.error is not None)),
            'size': last_event.size,
            'count': last_event.count,
        })

    last_lifecycle_state = dataset.lifecycle[0]
    return {
        'epn': dataset.epn,
        'beamline': dataset.visit.beamline,
        'status': last_lifecycle_state.type,
        'excluded': _is_dataset_excluded(dataset.visit, dataset.policy),
        'expires_on':
            utc_to_local(last_lifecycle_state.expires_on).isoformat()
            if last_lifecycle_state.expires_on is not None else None,
        'available':
            all([item['available'] for item in storage_items])
            if len(storage_items) > 0 else False,
        'size': sum([item['size'] for item in storage_items]),
        'count': sum([item['count'] for item in storage_items]),
        'contact': dataset.visit.pi.email,
        'notes': dataset.notes,
        'visit': {
            'id': dataset.visit.id,
            'start': utc_to_local(dataset.visit.start_date).isoformat(),
            'end': utc_to_local(dataset.visit.end_date).isoformat(),
            'title': dataset.visit.title
            },
        'type': {
            'id': dataset.visit.type.id,
            'name_short': dataset.visit.type.name_short,
            'name_long': dataset.visit.type.name_long
            },
        'pi': {
            'id': dataset.visit.pi.id,
            'first_names': dataset.visit.pi.first_names,
            'last_name': dataset.visit.pi.last_name,
            'email': dataset.visit.pi.email,
            'org': {
                'id': dataset.visit.pi.org.id,
                'name_short': dataset.visit.pi.org.name_short,
                'name_long': dataset.visit.pi.org.name_long
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
        'expires_on':
            utc_to_local(state.expires_on).isoformat()
            if state.expires_on is not None else None,
        'user_id': state.user_id,
        'user_name': state.user_name,
        'notes': state.notes
    }
