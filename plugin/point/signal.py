from django.db.models import signals
from main.models import Order, OrderSku, User
from django.dispatch import receiver

from django.core.signals import request_finished

from lib.signals import signal_pay


@receiver(request_finished)
def after_req(sender, **kwargs):
    # print('signal-------', sender, kwargs)
    pass


@receiver(signals.post_save, sender=User)
def after_save(sender, instance, created, update_fields, **kwargs):
    print('user signal-------', kwargs)
    print('user----', instance.avatar, created, update_fields)


# @receiver(signal_pay)
# def after_pay(sender, user_id, order_id, **kwargs):
#     """
#     支付成功后需要做积分处理
#     """
#     print('after pay---', user_id, order_id, kwargs)


