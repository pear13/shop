from django.apps import AppConfig


class InviteConfig(AppConfig):
    name = 'plugin.invite'
    verbose_name = '分销1'

    def ready(self):
        import plugin.invite.signal
