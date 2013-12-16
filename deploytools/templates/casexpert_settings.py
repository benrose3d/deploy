from finiteloop.djangotools.settings import *

DATABASES = { 'default': get_database_url() }
RAVEN_CONFIG = get_raven_config()

CACHES = {
    'default': get_cache_url('DEFAULT_CACHE_URL'),
    'note_storage': get_cache_url('NOTES_STORAGE_CACHE_URL'),
}
