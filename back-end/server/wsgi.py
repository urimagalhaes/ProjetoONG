import os
import sys
from pathlib import Path

# Na Vercel o processo começa na raiz do repositório, fora de back-end/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from django.core.wsgi import get_wsgi_application  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')

application = get_wsgi_application()
