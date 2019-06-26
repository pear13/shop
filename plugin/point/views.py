from django.shortcuts import render
from django.views import View

from lib import gen_resp

# Create your views here.


class PointView(View):

    def get(self, request):
        return gen_resp(10000, 'ashibbbb')