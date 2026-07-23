import json

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .actions import order_created
from .models import Order


@csrf_exempt
def handle_order_service_event(request):
    if request.headers.get("X-Internal-Token") != settings.ORDER_SERVICE_SHARED_SECRET:
        return HttpResponse(status=403)

    payload = json.loads(request.body)
    order = Order.objects.filter(pk=payload["order_id"]).first()
    if order is None:
        return HttpResponse(status=404)

    if payload["event_type"] == "order_created":
        order_created(order=order, user=order.user or AnonymousUser())

    return HttpResponse(status=204)
