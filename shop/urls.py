"""shop URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static

from shop import settings
from main.views import *


urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('', index),
    path('tes', tes),
    # path('login', login),
    path('login', login),
    path('openid', getOpenid),
    path('user', UserView.as_view()),
    path('homeImg', homeImg),
    path('homeCate', homeCate),
    path('related', related),
    path('homeTag', homeTag),
    path('search', search),
    path('cate', cate),
    path('spuDetail', spuDetail),
    path('cart', CartView.as_view()),
    path('acToken', AccessToken),
    # test
    path('shareData', shareData),
    path('qrCode', qrCode),
    path('myShare', myShare),

    path('district', district),
    path('coupon', coupon),
    path('address', Address.as_view()),
    path('order', OrderData.as_view()),
    path('favor', FavorView.as_view()),
    path('orderPay', orderPay),
    path('orderCancel', orderCancel),
    path('spuCmt', SpuCmtView.as_view()),
    path('orderConfirm', orderConfirm),
    path('orderSkuRefund', orderSkuRefund),
    path('orderStatus', orderStatus),
    path('payNoti', payNoti),
    path('qiniuToken', qiniuToken),
    path('shipFee', shipFee),
    path('tagCmt', tagCmt),
] + static(settings.QRCODE_URL, document_root=settings.QRCODE_ROOT)

# debug_toolbar组件需要
if settings.DEBUG:
    import debug_toolbar
    urlpatterns.append(path('__debug__/', include(debug_toolbar.urls)))


admin.site.site_header = '商城header'
admin.site.site_title = '商城title'
