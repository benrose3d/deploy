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
