from django.apps import AppConfig


class PointConfig(AppConfig):
    """积分系统"""
    name = 'plugin.point'
    verbose_name = '会员积分'

    def ready(self):
        import plugin.point.signal
