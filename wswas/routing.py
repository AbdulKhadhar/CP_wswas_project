from django.urls import re_path
from safety_app import consumers

websocket_urlpatterns = [
    re_path(r'ws/alert/$', consumers.AlertConsumer.as_asgi()),
    re_path(r'ws/monitor/(?P<alert_id>[0-9a-f-]+)/$', consumers.MonitorConsumer.as_asgi()),
]
