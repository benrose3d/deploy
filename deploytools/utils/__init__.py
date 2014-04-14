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

    def as_dict(self):
        # This is a hack around doing ** expansion for kwargs since I'm not
        # sure what to do to override that.
        return dict((k, self.get(k)) for k in self.keys())

    def items(self):
        return [(k, self.get(k)) for k in self.keys()]

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

    __getitem__ = get
    __getattr__ = get

    def __iter__(self):
        for key in self.keys():
            yield self.get(key)


class ErrorCollector(object):

    def __init__(self):
        self.value = 0

    def test(self, cmd, if_missing):
        if not test_cmd(cmd):
            print(colors.red(if_missing))
            self.value = 0


def test_cmd(cmd):
    return fabric.run(cmd, warn_only=True, quiet=True).succeeded


def mkdir(path):
    fabric.run("test -d {path} || mkdir -p {path}".format(path=path))
    return path


def dir_exists(path):
    return test_cmd("test -d {}".format(path))


def requires_config(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not fabric.env.get("cfg", None):
            fabric.abort(colors.red(
                "No env configured, call env:<project>,<env_name> first"))

        return func(*args, **kwargs)

    return wrapper


def local_config_path(filename):
    paths = [
        os.path.join(os.getenv('DEPLOY_CONFIGS', 'deploy_config'), filename),
        os.path.join(os.getenv('HOME', ''), '.deploy_config', filename),
    ]

    for path in paths:
        if os.path.exists(path):
            return path
    else:
        raise Exception("No config file found - {}".format(filename))


def get_config(env_name, filename="project.cfg"):
    cfg = SafeConfigParser()
    cfg.read(local_config_path(filename))
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

    if method not in ("deploy_tag", "deploy_branch", "deploy_rev"):
        raise Exception("Invalid deployment strategy {!r}".format(method))

    if method == "deploy_tag":
        name = fabric.run("git tag -l '{}-*' | sort -nr | head -n1".format(
            name))

    if not name.strip():
        raise Exception("No valid rev was found for {!r}".format(name))

    return name

def get_release_dir():
    return os.path.join(fabric.env.cfg.root, "releases",
            datetime.now().strftime("%Y%m%d%H%M%S"))


def friendly_date(date, format):
    return datetime.strptime(date, format).strftime("%a, %b %d, %Y %H:%M:%S %Z")


def friendly_release_dir(name):
    return friendly_date(name, "%Y%m%d%H%M%S")


def django_run(cmd, *args, **kwargs):
    command = [root_path("bin/run"), cmd] + list(args)
    return fabric.run(" ".join(command), **kwargs)


def pip_run(cmd, *args, **kwargs):
    env = {
        "PIP_DOWNLOAD_CACHE": root_path(".pip_cache"),
        "PATH": root_path("shared/system/bin"),
    }

    with fabric.shell_env(**env), fabric.cd(fabric.env.release_dir):
        cmd = ["pip", cmd] + list(args)
        return fabric.run(" ".join(cmd))


def print_center(string, *args):
    l = len(string)
    left = 80 / 2 - l + 1
    print " " * left, string.format(*args).upper()


def get_prior_release():
    with fabric.cd(os.path.join(fabric.env.cfg.root, "releases")):
        return fabric.run("ls -t | head -n 2 | tail -n 1", quiet=True)


def _rooted_path(root, *args):
    parts = []
    for arg in args:
        parts.extend(arg.split("/"))

    return os.path.join(root, *parts)


def root_path(*args):
    return _rooted_path(fabric.env.cfg.root, *args)


def local_path(*args):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return _rooted_path(path, *args)
