from django.urls import path

from .views import *

urlpatterns = [
    path('point', PointView.as_view())
]


