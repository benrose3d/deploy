import socket
import getpass
import fabric.api as fabric
from datetime import datetime
from cStringIO import StringIO
from ConfigParser import ConfigParser, SafeConfigParser

from utils import friendly_date


def parse_migrations(data):
    package = None

    if not hasattr(data, "readline"):
        data = StringIO(data)

    for line in data:
        line = line.strip()

        if not line:
            continue
        elif line.startswith("("):
            state, name = line.split(" ", 1)
            installed = state == "(*)"
            yield package, name, installed
        else:
            package = line


def generate_release_manifest(migrations):
    cfg = ConfigParser()

    cfg.add_section("release")

    cfg.set("release", "app", fabric.env.cfg.app_name)
    cfg.set("release", "ref", fabric.env.deployed_ref)
    cfg.set("release", "sha", fabric.env.deployed_sha)
    cfg.set("release", "date", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
    cfg.set("release", "type", fabric.env.cfg.checkout_strategy.split(":")[0])
    cfg.set("release", "by", "{}@{}".format(getpass.getuser(),
        socket.gethostname()))

    for app, name, is_installed in migrations:
        sect_name = "migrations:{}".format(app)

        if not cfg.has_section(sect_name):
            cfg.add_section(sect_name)

        cfg.set(sect_name, name, str(is_installed).lower())

    return cfg


def get_release_manifest(migrations):
    manifest = generate_release_manifest(migrations)
    output = StringIO()
    manifest.write(output)
    output.seek(0)
    return output


def get_release_meta(data):
    if not hasattr(data, "readline"):
        data = StringIO(data)

    cfg = SafeConfigParser()
    cfg.readfp(data)

    data = dict(cfg.items("release"))
    data["date"] = friendly_date(data["date"], "%Y-%m-%dT%H:%M:%SZ")

    return data
