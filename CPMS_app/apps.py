from django.apps import AppConfig


class CpmsAppConfig(AppConfig):
    name = 'CPMS_app'

    def ready(self):
        import CPMS_app.signals

