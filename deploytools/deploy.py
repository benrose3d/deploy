from fabric import colors
import fabric.api as fabric
from fabric.contrib.files import upload_template

from .utils import (local_path, root_path, get_prior_release,
        all_processes_sudo, dir_exists, friendly_release_dir, print_center,
        mkdir, requires_config, get_release_ref, get_release_dir, django_run,
        pip_run)

from .utils.migrations import (get_release_meta, MigrationRollback,
        get_release_manifest, parse_migrations)


__all__ = ["promote", "prune", "rollback", "info", "build_docs", "deploy"]


@fabric.task
@requires_config
def build_docs():
    """Build documentation
    """
    with fabric.cd(root_path("current")):
        if not dir_exists("doc"):
            return

        fabric.run("pip freeze | grep -i sphinx || pip install sphinx")
        fabric.run("sphinx-build -b html -d doc/_build/doctrees "
                "doc/ doc/_build/html")


@fabric.task
def update_code():
    """Clone (or fetch from) a git repo and export a copy

    Clones the git repo if it doesn't exist and then exports the release ref to
    the release directory.
    """
    repo_path = root_path("shared/repo")

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
def link_release(release=None):
    """Link current release directory to current release
    """
    if not release:
        release = fabric.env.release_dir

    with fabric.cd(fabric.env.cfg.root):
        fabric.run("rm current".format(fabric.env.release_dir), warn_only=True,
                quiet=True)
        fabric.run("ln -s {} current".format(release))


@fabric.task
def pip_install_requirements():
    """Install pip requirements
    """
    pip_run("install", "-q", "-r", "requirements.txt")


@fabric.task
def migrate():
    """Migrate the database
    """
    if not fabric.env.cfg.skip_syncdb:
        django_run("syncdb", "--noinput")

    django_run("migrate", "--no-initial-data")


@fabric.task
def precompile_assets():
    """Precompile assets using Django collectstatic
    """
    django_run("collectstatic", "--noinput", "-v 0")


@fabric.task
def write_release_manifest():
    migrations = parse_migrations(str(django_run("migrate", "--list",
        quiet=True)))
    manifest = get_release_manifest(migrations)
    fabric.put(manifest, root_path("current/manifest.cfg"))


@fabric.task
def casexpert_hack():
    template = local_path("templates/casexpert_settings.py")
    upload_template(template,
            root_path("current/settings_local.py"), {}, backup=False)

    pip_run("install",
            "--find-links", "http://packages.finiteloopsoftware.com/eggs/",
            "finiteloop")


@fabric.task(default=True)
@requires_config
def deploy():
    """Run deployment
    """
    fabric.env.release_dir = get_release_dir()

    fabric.execute('setup.setup')

    fabric.execute(update_code)
    fabric.execute(link_release)
    fabric.execute(pip_install_requirements)
    fabric.execute(casexpert_hack)
    fabric.execute(precompile_assets)
    fabric.execute(build_docs)
    fabric.execute(migrate)
    fabric.execute(write_release_manifest)

    fabric.execute(restart)


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
    with fabric.cd(root_path("releases")):
        fabric.run("ls -t | tail -n $(( `ls -t | wc -l` - 5 )) | xargs rm -r")


@fabric.task
@requires_config
def print_rollback_options():
    """List release directory and print rollback options
    """
    print colors.red("No rollback release specified. Options are:")
    res = fabric.run("ls {} | sort -n".format(root_path("releases")),
            quiet=True)

    options = ["previous"]
    options.extend(res.split("\r\n"))
    print colors.yellow("\n".join(" * {}".format(i) for i in options))


@fabric.task
@requires_config
def rollback(to=None):
    """Rollback to a previous release
    """
    if not to:
        return fabric.execute(print_rollback_options)

    fabric.execute(link_release, root_path("releases", to))

    # TODO: Load current and prior from release config
    for app, version in MigrationRollback(current, prior):
        django_run("migrate", app, version)

    fabric.execute(restart)


@fabric.task
@requires_config
def info():
    """See what's currently deployed
    """
    value = fabric.run("cat {}".format(root_path("current/manifest.cfg")),
            quiet=True)
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
