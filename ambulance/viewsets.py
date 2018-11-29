from django.http import Http404
from rest_framework import status
from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination

from emstrack.mixins import BasePermissionMixin, \
    CreateModelUpdateByMixin, UpdateModelUpdateByMixin
from login.viewsets import IsCreateByAdminOrSuper

from .models import Location, Ambulance, LocationType, Call, AmbulanceUpdate

from .serializers import LocationSerializer, AmbulanceSerializer, AmbulanceUpdateSerializer, CallSerializer

import logging
logger = logging.getLogger(__name__)


# Django REST Framework Viewsets

class AmbulancePageNumberPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    # page_size = 25
    max_page_size = 1000


class AmbulanceLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 100
    max_limit = 1000


# Ambulance viewset

class AmbulanceViewSet(mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       CreateModelUpdateByMixin,
                       UpdateModelUpdateByMixin,
                       BasePermissionMixin,
                       viewsets.GenericViewSet):
    """
    API endpoint for manipulating ambulances.

    list:
    Retrieve list of ambulances.

    retrieve:
    Retrieve an existing ambulance instance.

    create:
    Create new ambulance instance.
    
    update:
    Update existing ambulance instance.

    partial_update:
    Partially update existing ambulance instance.
    """

    filter_field = 'id'
    profile_field = 'ambulances'
    queryset = Ambulance.objects.all()

    serializer_class = AmbulanceSerializer

    @detail_route(methods=['get', 'post'], pagination_class=AmbulancePageNumberPagination)
    def updates(self, request, pk=None, **kwargs):

        if request.method == 'GET':
            # list updates
            return self.updates_get(request, pk, **kwargs)

        elif request.method == 'POST':
            # put updates
            return self.updates_put(request, pk, updated_by=self.request.user, **kwargs)

    def updates_get(self, request, pk=None, **kwargs):
        """
        Retrieve and paginate ambulance updates.
        Use ?page=10&page_size=100 to control pagination.
        Use ?call_id=x to retrieve updates to call x.
        """

        # retrieve updates
        ambulance = self.get_object()
        ambulance_updates = ambulance.ambulanceupdate_set

        # retrieve only call updates
        call_id = self.request.query_params.get('call_id', None)
        if call_id is not None:
            try:
                # TODO: filter call based on active intervals.
                #       go back to AmbulanceCallHistory and select active intervals:
                #       between Ongoing and Suspended or Completed

                #       If there is a available history, user the following code:

                ambulance_history = ambulance.ambulancecallhistory
                    # available_zone = []
                    # for time in ambulance_updates:



                #       If no history is available, use the following code:
                call = Call.objects.get(id=call_id)
                if call.ended_at is not None:
                    ambulance_updates = ambulance_updates.filter(timestamp__range=(call.started_at, call.ended_at))
                elif call.started_at is not None:
                    logger.debug('HERE')
                    ambulance_updates = ambulance_updates.filter(timestamp__gte=call.started_at)
                else:
                    # call hasn't started yet, return none
                    ambulance_updates = AmbulanceUpdate.objects.none()

            except Call.DoesNotExist as e:
                raise Http404("Call with id '{}' does not exist.".format(call_id))

        # order records
        ambulance_updates = ambulance_updates.order_by('-timestamp')

        # paginate
        page = self.paginate_queryset(ambulance_updates)

        if page is not None:
            serializer = AmbulanceUpdateSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # return all if not paginated
        serializer = AmbulanceUpdateSerializer(ambulance_updates, many=True)
        return Response(serializer.data)

    def updates_put(self, request, pk=None, **kwargs):
        """
        Bulk ambulance updates.
        """

        # retrieve ambulance
        ambulance = self.get_object()

        # retrieve user
        updated_by = kwargs.pop('updated_by')

        # update all serializers
        serializer = AmbulanceUpdateSerializer(data=request.data,
                                               many=True)
        if serializer.is_valid():
            serializer.save(ambulance=ambulance, updated_by=updated_by)
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Location viewset

class LocationViewSet(mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    """
    API endpoint for manipulating locations.

    list:
    Retrieve list of locations.
    """
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


class LocationTypeViewSet(mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    """
    API endpoint for manipulating locations.

    list:
    Retrieve list of locations by type.
    """
    serializer_class = LocationSerializer

    def get_queryset(self):
        try:
            type = LocationType(self.kwargs['type']).name
        except ValueError:
            type = ''

        return Location.objects.filter(type=type)


# Call ViewSet

class CallViewSet(mixins.ListModelMixin,
                  CreateModelUpdateByMixin,
                  BasePermissionMixin,
                  viewsets.GenericViewSet):
    """
    API endpoint for manipulating Calls.

    list:
    Retrieve list of calls.

    create:
    Create new call instance.
    """

    permission_classes = (IsAuthenticated,
                          IsCreateByAdminOrSuper)

    filter_field = 'ambulancecall__ambulance_id'
    profile_field = 'ambulances'
    queryset = Call.objects.all()

    serializer_class = CallSerializer
