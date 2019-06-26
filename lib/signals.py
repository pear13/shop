# import os
# import django
#
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shop.settings")  # project_name 项目名称
# django.setup()

import logging

from django.dispatch import Signal

log = logging.getLogger()

# 支付成功后发送信号，计算积分或其他，主要是为了分离
signal_pay = Signal()

# 下单信号
signal_first_order = Signal()

# 首次进入
signal_first_visit = Signal()

# 退货信号
signal_refund = Signal()
