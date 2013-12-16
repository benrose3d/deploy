DIRECTORIES = [
    ("releases", None, None),
    (".pip_cache", None, None),
    ("bin", None, None),
    ("shared/secrets", 700, None),
    ("shared/init", None, None),
    ("shared/log", 770, "{user}:www-data"),
    ("shared/run", None, None),
    ("shared/config", None, None),
]

DIST_PACKAGES = {
    "psycopg2": ["psycopg2", "psycopg2-*.egg-info"],
    "lxml": ["lxml", "lxml-*.egg-info"],
    "imaging": ["PIL", "PIL.pth"],
    "mysqldb": ["MySQLdb", "MySQL_python-*.egg-info", "_mysql*"],
}

UPSTART_RUNNER = (
    "{root}/shared/system/bin/envrun "
    "{root}/shared/secrets/environ.cfg {command}")

DEFAULT_PROCESSES = {
    "web": ("gunicorn "
            "--settings={app_name}.settings {workers}"
            "--error-logfile={shared}/log/error.log "
            "--pid={shared}/run/gunicorn.pid "
            "--bind=unix:{shared}/run/gunicorn.sock "
            "{app_name}.wsgi:application"),
}

BINSTUB_RUNNER = (
    "{root}/shared/system/bin/envrun "
    "{root}/shared/secrets/environ.cfg "
    "{root}/shared/system/bin/django-admin.py ")

VIRTUALENV_CMD = "virtualenv --python=python{python} {pkgs_flag} {path}"
