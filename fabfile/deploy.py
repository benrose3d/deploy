import os
from fabric import colors
import fabric.api as fabric
from fabric.contrib.files import upload_template

from utils import get_prior_release
from utils import all_processes_sudo, dir_exists
from utils import friendly_release_dir, print_center
from utils import mkdir, ErrorCollector, requires_config
from utils import get_release_ref, get_release_dir, django_run
from utils.migrations import get_release_meta, MigrationRollback
from utils.migrations import get_release_manifest, parse_migrations


__all__ = ["setup", "check", "promote", "prune", "rollback", "info",
            "build_docs", "deploy", "recreate_virtualenv", "purge",
            "list_prior"]


# Dir name (relative to root) and mode
DIRECTORIES = [
    ("releases", None),
    (".pip_cache", None),
    ("shared/secrets", 700),
    ("shared/init", None),
    ("shared/log", None),
    ("shared/run", None),
]

DIST_PACKAGES = {
    "psycopg2": ["psycopg2", "psycopg2-*.egg-info"],
    "lxml": ["lxml", "lxml-*.egg-info"],
    "imaging": ["PIL", "PIL.pth"],
    "mysqldb": ["MySQLdb", "MySQL_python-*.egg-info", "_mysql*"],
}


@fabric.task
def create_directories():
    with fabric.cd(mkdir(fabric.env.cfg.root)):
        for directory, mode in DIRECTORIES:
            mkdir(directory)

            if mode:
                fabric.run("chmod {} {}".format(mode, directory))


@fabric.task
def create_virtualenv(recreate=False):
    python = fabric.env.cfg.python_version
    site_packages = fabric.env.cfg.get_bool("site_packages")
    pkgs_flag = "" if site_packages else "--no-site-packages"
    path = os.path.join(fabric.env.cfg.root, "shared", "system")
    test_path = os.path.join(path, "bin")

    exists = fabric.run("test -d {}".format(test_path),
            warn_only=True).succeeded

    if exists and recreate:
        fabric.run("rm -rf {}".format(path))

    if exists and not recreate:
        return

    fabric.run("virtualenv --python=python{python} {pkgs_flag} {path}".format(
                **locals()))

    fabric.execute(link_dist_packages)


@fabric.task
def create_upstart_configs():
    template = os.path.join(os.path.dirname(__file__), "templates",
            "upstart.cfg")

    default_processes = {
        "web": ("{root}/shared/system/bin/gunicorn "
                    "--settings={app_name}.settings {workers}"
                    "--error-logfile={root}/shared/system/logs/error.log "
                    "--pid={root}/shared/system/run/gunicorn.pid "
                    "--bind=unix:{root}/shared/system/run/gunicorn.sock "
                    "{app_name}.wsgi:application"),
    }

    processes = fabric.env.cfg.processes or default_processes
    workers = fabric.env.cfg.get("workers")

    args = {
        "user": fabric.env.user,
        "group": fabric.env.user,
        "path": fabric.env.cfg.root,
        "app_name": fabric.env.cfg.app_name,
        "root": fabric.env.cfg.root,
        "workers": "--workers={}".format(workers) if workers else "",
    }

    for process_name, command in processes.items():
        if process_name in default_processes and not command:
            command = default_processes[process_name]

        args.update({
            "description": "{} {}".format(fabric.env.cfg.app_name,
                process_name),
            "process_name": process_name,
            "process": command.format(**args),
        })

        upload_template(template,
                os.path.join(fabric.env.cfg.root, "shared", "init",
                    "{app_name}-{process_name}.cfg".format(**args)),
                args, backup=False)


@fabric.task
def update_code():
    repo_path = os.path.join(fabric.env.cfg.root, "shared", "repo")

    if not dir_exists(repo_path):
        fabric.run("git clone -nq {} {}".format(fabric.env.cfg.repo, repo_path))

    with fabric.cd(repo_path):
        fabric.run("git fetch origin")
        fabric.run("git fetch --tags origin")

        fabric.env.deployed_ref = get_release_ref()
        fabric.env.deployed_sha = fabric.run("git show-ref --hash {}".format(
            fabric.env.deployed_ref))

        mkdir(fabric.env.release_dir)

        fabric.run("git archive {} | tar -C {} -xf -".format(
            fabric.env.deployed_ref, fabric.env.release_dir))


@fabric.task
def configure_ssh():
    ret = fabric.run("grep 'Host github.com' ~/.ssh/config", warn_only=True,
            quiet=True)

    if ret.failed:
        fabric.run("echo 'Host github.com\n    StrictHostKeyChecking no' "
                ">> ~/.ssh/config")


@fabric.task
def link_release(release=None):
    if not release:
        release = fabric.env.release_dir

    with fabric.cd(fabric.env.cfg.root):
        fabric.run("rm current".format(fabric.env.release_dir), warn_only=True)
        fabric.run("ln -s {} current".format(release))


@fabric.task
def pip_install_requirements():
    env = {
        "PIP_DOWNLOAD_CACHE": os.path.join(fabric.env.cfg.root, ".pip_cache"),
        "PATH": os.path.join(fabric.env.cfg.root, "shared", "system", "bin"),
    }

    with fabric.shell_env(**env), fabric.cd(fabric.env.release_dir):
        fabric.run("pip install -q -r requirements.txt")


@fabric.task
def copy_upstart_config():
    if fabric.env.cfg.get_bool("copy_upstart_config") and fabric.env.can_sudo:
        return

    fabric.sudo("cp {}/system/init/* /etc/init/".format(fabric.env.cfg.root))


@fabric.task
def migrate():
    django_run("syncdb", "--noinput")
    django_run("migrate", "--no-initial-data")


@fabric.task
def precompile_assets():
    django_run("collectstatic", "--noinput", "-v 0")


@fabric.task
def write_release_manifest():
    output = os.path.join(fabric.env.cfg.root, "current", "manifest.cfg")
    migrations = parse_migrations(str(django_run("migrate", "--list",
        quiet=True)))
    manifest = get_release_manifest(migrations)
    fabric.put(manifest, output)


@fabric.task(default=True)
@requires_config
def deploy():
    """Run deployment
    """
    fabric.env.release_dir = get_release_dir()

    fabric.execute(setup)

    fabric.execute(configure_ssh)
    fabric.execute(update_code)
    fabric.execute(link_release)
    fabric.execute(pip_install_requirements)
    fabric.execute(precompile_assets)
    fabric.execute(build_docs)
    fabric.execute(migrate)
    fabric.execute(write_release_manifest)

    fabric.execute(restart)


@fabric.task
@requires_config
def recreate_virtualenv():
    """Purge the old virtualenv and recreate
    """
    fabric.execute(create_virtualenv, recreate=True)


@fabric.task
@requires_config
def setup():
    """Setup a new environment, no deployment
    """
    fabric.execute(create_directories)
    fabric.execute(create_virtualenv)
    fabric.execute(create_upstart_configs)
#    fabric.execute(copy_upstart_config)


@fabric.task
@requires_config
def purge():
    """Completely remove all app directories
    """
    with fabric.cd(fabric.env.cfg.root):
        for directory, _ in DIRECTORIES:
            fabric.run("rm -rf {}".format(directory))

    fabric.run("rm -rf shared")
    fabric.run("rm -rf current")


@fabric.task
@requires_config
def check():
    """Ensure server has all needed dependencies
    """
    error = ErrorCollector()

    error.test("which virtualenv", "Missing `virtualenv` executable")
    error.test("which git", "Missing `git` executable")
    error.test("which yui-compressor", "Missing `yui-compressor` executable")

    return error.value


@fabric.task
@requires_config
def start():
    all_processes_sudo("start")


@fabric.task
@requires_config
def stop():
    all_processes_sudo("stop")


@fabric.task
@requires_config
def restart():
    all_processes_sudo("restart")


@fabric.task
@requires_config
def promote(from_env):
    """Promote a release from one environment to the next
    """
    pass


@fabric.task
@requires_config
def prune(to_keep=5):
    """Remove old releases
    """
    with fabric.cd(os.path.join(fabric.env.cfg.root, "releases")):
        fabric.run("ls -t | tail -n $(( `ls -t | wc -l` - 5 )) | xargs rm -r")


@fabric.task
def link_dist_packages():
    # TODO: less of a shotgun approach
    dist_pkgs = "/usr/lib/python{}/dist-packages".format(
            fabric.env.cfg.python_version)

    site_pkgs = os.path.join(fabric.env.cfg.root, "shared", "system", "lib",
            "python{}".format(fabric.env.cfg.python_version), "site-packages")

    args = ["-name {!r}".format(glob) for value in DIST_PACKAGES.values() for
            glob in value]

    fabric.run("find {} {} | xargs -I % ln -s % {}".format(
        dist_pkgs, " -o ".join(args), site_pkgs), warn_only=True)


@fabric.task
def rollback_migrations(from_release, to_release):
    current = None # get current release manifest text
    prior = None # get prior release manifest text

    for app, version in MigrationRollback(current, prior):
        django_run("migrate", app, version)


@fabric.task
@requires_config
def rollback(to="previous"):
    """Rollback to a previous release
    """
    if to == "previous":
        to = get_prior_release()

    to_rel = os.path.join(fabric.env.cfg.root, "releases", to)
    fabric.execute(link_release, to_rel)
    fabric.execute(rollback_migrations)
    fabric.execute(restart)


@fabric.task
@requires_config
def list_prior():
    """List all prior releases on server
    """
    rel_dir = os.path.join(fabric.env.cfg.root, "releases")
    fabric.run("ls {} | sort -n".format(rel_dir))


@fabric.task
@requires_config
def info():
    """See what's currently deployed
    """
    manifest = os.path.join(fabric.env.cfg.root, "current", "manifest.cfg")
    value = fabric.run("cat {}".format(manifest), quiet=True)
    data = get_release_meta(str(value))

    print "=" * 80
    print_center("{} RELEASE MANIFEST", data["app"])
    print "=" * 80
    print colors.yellow("released:   "), data["date"]
    print colors.yellow("by:         "), colors.green(data["by"])
    print colors.yellow("ref:        "), colors.red(data["ref"])
    print colors.yellow("strategy:   "), data["type"]
    print colors.yellow("sha:        "), data["sha"]
    print colors.yellow("prior:      "), friendly_release_dir(
            get_prior_release())
    print "=" * 80


@fabric.task
@requires_config
def build_docs():
    """Build documentation
    """
    with fabric.cd(os.path.join(fabric.env.cfg.root, "current")):
        if not dir_exists("doc"):
            return

        fabric.run("pip freeze | grep -i sphinx || pip install sphinx")
        fabric.run("sphinx-build -b html -d doc/_build/doctrees "
                "doc/ doc/_build/html")
