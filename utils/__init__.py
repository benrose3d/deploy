import os
from functools import wraps
from datetime import datetime
from ConfigParser import SafeConfigParser, NoSectionError

import fabric.api as fabric
from fabric import colors


class AttrDict(dict):

    DEFAULTS = {
        "skip_syncdb": "false",
        "python_version": "2.7",
        "site_packages": "false",
        "copy_upstart_config": "true",
        "can_sudo": "false",
        "workers": None,
        "checkout_strategy": "deploy_branch:origin/master",
        "root": "/home/{user}",
    }

    SENTINEL = object()

    def get_bool(self, key, default=SENTINEL):
        return self.get(key, default).lower() == "true"

    def get(self, attr, default=SENTINEL):
        value = dict.get(self, attr, default)

        if value is self.SENTINEL:
            value = self.DEFAULTS[attr]

        if hasattr(value, "format"):
            value = value.format(**self)

        if attr.endswith("_list"):
            return [i.strip() for i in value.split(",")]

        return value

    def __getattr__(self, attr):
        return self.get(attr)


class ErrorCollector(object):

    def __init__(self):
        self.value = 0

    def test(self, cmd, if_missing):
        if not self.checked_run(cmd):
            print(colors.red(if_missing))
            self.value = 0

    def checked_run(self, cmd):
        return fabric.run(cmd, quiet=True, warn_only=True).succeeded


def mkdir(path):
    fabric.run("test -d {path} || mkdir -p {path}".format(path=path))
    return path


def dir_exists(path):
    return fabric.run("test -d {}".format(path), warn_only=True).succeeded


def requires_config(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not fabric.env.get("cfg", None):
            fabric.abort(colors.red(
                "No env configured, call env:<project>,<env_name> first"))

        return func(*args, **kwargs)

    return wrapper


def get_config(env_name, filename="project.cfg"):
    cfg = SafeConfigParser()
    cfg.read(filename)
    app_cfg = AttrDict(cfg.items("ALL_ENVIRONMENTS"))

    try:
        app_cfg.update(cfg.items(env_name))
    except NoSectionError:
        pass

    try:
        app_cfg["processes"] = dict(cfg.items("{}:processes".format(env_name)))
    except NoSectionError:
        app_cfg["processes"] = {}

    return app_cfg



def all_processes_sudo(cmd):
    for process in fabric.env.cfg.processes:
        fabric.sudo("/sbin/{} {}-{}".format(cmd, fabric.env.cfg.app_name,
            process))


def get_release_ref():
    method, name = fabric.env.cfg.checkout_strategy.split(":", 1)

    if method == "deploy_tag":
        return fabric.run("git tag -l '{}-*' | sort -nr | head -n1".format(
            name))
    elif method == "deploy_branch":
        return name
    elif method == "deploy_rev":
        return name
    else:
        raise Exception("Invalid deployment strategy {!r}".format(name))


def get_release_dir():
    return os.path.join(fabric.env.cfg.root, "releases",
            datetime.now().strftime("%Y%m%d%H%M%S"))


def friendly_date(date, format):
    return datetime.strptime(date, format).strftime("%a, %b %d, %Y %H:%M:%S %Z")


def friendly_release_dir(name):
    return friendly_date(name, "%Y%m%d%H%M%S")


def django_run(cmd, *args, **kwargs):
    manage = os.path.join(fabric.env.cfg.root, "shared", "system", "bin",
            "django-admin.py")
    release_dir = os.path.join(fabric.env.cfg.root, "current")

    pythonpath = ":".join([
        release_dir,
        os.path.join(release_dir, fabric.env.cfg.app_name),
    ])

    with fabric.shell_env(PYTHONPATH=pythonpath):
        return fabric.run("{} {} --settings={}.settings {}".format(manage, cmd,
            fabric.env.cfg.app_name, " ".join(args)), **kwargs)


def print_center(string, *args):
    l = len(string)
    left = 80 / 2 - l + 1
    print " " * left, string.format(*args).upper()


def get_prior_release():
    with fabric.cd(os.path.join(fabric.env.cfg.root, "releases")):
        return fabric.run("ls -t | head -n 2 | tail -n 1", quiet=True)
