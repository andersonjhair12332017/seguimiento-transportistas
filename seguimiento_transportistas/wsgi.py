import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "seguimiento_transportistas.settings")

application = get_wsgi_application()
app = application
