import os
import fabric.api as fabric
from fabric.contrib.files import upload_template, append as append_to_file

from config import (UPSTART_RUNNER, DEFAULT_PROCESSES, DIRECTORIES,
        DIST_PACKAGES, BINSTUB_RUNNER, VIRTUALENV_CMD)

from .utils import (local_path, root_path, test_cmd, dir_exists, mkdir,
        ErrorCollector, requires_config)


__all__ = [
    "setup", "check", "recreate_virtualenv", "purge", "put_secrets",
    "configure_server"
]


@fabric.task
def create_directories():
    """Create initial directory layout and ensure permissions
    """
    with fabric.cd(mkdir(fabric.env.cfg.root)):
        for directory, mode, owner in DIRECTORIES:
            mkdir(directory)

            if mode:
                fabric.run("chmod {} {}".format(mode, directory))

            if owner:
                fabric.run("chown {} {}".format(
                    owner.format(**fabric.env.cfg.as_dict()), directory))


@fabric.task
@requires_config
def create_binstubs():
    """Create binstub for django-admin.py

    Creates $ROOT/bin/run that is a shortcut to django-admin.py with
    appropriate environment setup.
    """
    output = root_path("bin/run")

    args = {
        "app_name": fabric.env.cfg.app_name,
        "root": fabric.env.cfg.root,
        "env_name": fabric.env.environment_name,
    }

    args["runner"] = BINSTUB_RUNNER.format(**args)

    upload_template(local_path("templates/run.sh"), output, args, backup=False)
    fabric.run("chmod +x {}".format(output))


@fabric.task
def create_virtualenv(recreate=False):
    """Create or recreate virtual environment
    """
    args = {
        "python": fabric.env.cfg.python_version,
        "pkgs_flag": ("" if fabric.env.cfg.get_bool("site_packages")
            else "--no-site-packages"),
        "path": root_path("shared/system"),
    }

    exists = dir_exists(root_path("shared/system/bin"))

    if exists and recreate:
        fabric.run("rm -rf {}".format(args["path"]))

    if exists and not recreate:
        return

    fabric.run(VIRTUALENV_CMD.format(**args))


@fabric.task
def create_nginx_config():
    """Create nginx configuration files for HTTP and HTTPS
    """
    http_template = local_path("templates/nginx.cfg")
    https_template = local_path("templates/nginx_ssl.cfg")

    args = {
        "app_name": fabric.env.cfg.app_name,
        "root": fabric.env.cfg.root,
        "shared": root_path("shared"),
        "server_name": fabric.env.cfg.server_name,
        "env_name": fabric.env.environment_name,
    }

    upload_template(http_template,
            root_path("shared/config", "{app_name}-{env_name}".format(**args)),
            args, backup=False)

    upload_template(https_template,
            root_path("shared/config",
                "{app_name}-{env_name}-ssl".format(**args)),
            args, backup=False)


@fabric.task
def create_upstart_configs():
    """Generate Upstart configuration files
    """
    template = local_path("templates/upstart.cfg")
    processes = fabric.env.cfg.processes or DEFAULT_PROCESSES
    workers = fabric.env.cfg.get("workers")

    args = {
        "user": fabric.env.user,
        "group": fabric.env.user,
        "path": fabric.env.cfg.root,
        "app_name": fabric.env.cfg.app_name,
        "root": fabric.env.cfg.root,
        "shared": root_path("shared"),
        "server_name": fabric.env.cfg.server_name,
        "env_name": fabric.env.environment_name,
        "workers": "--workers={}".format(workers) if workers else "",
    }

    for process_name, base_command in processes.items():
        if process_name in DEFAULT_PROCESSES and not base_command:
            base_command = DEFAULT_PROCESSES[process_name]

        args.update({
            "description": "{} {}".format(fabric.env.cfg.app_name,
                process_name),
            "process_name": process_name,
            "process": UPSTART_RUNNER.format(root=fabric.env.cfg.root,
                command=base_command.format(**args)),
        })

        upload_template(template,
                root_path("shared/init",
                    "{app_name}-{env_name}-{process_name}.conf".format(**args)),
                args, backup=False)


@fabric.task
def configure_ssh():
    """Disable strict host checking for GitHub
    """
    if not test_cmd("grep 'Host github.com' ~/.ssh/config"):
        fabric.run("echo 'Host github.com\n    StrictHostKeyChecking no' "
                ">> ~/.ssh/config")


@fabric.task
def link_dist_packages():
    # TODO: less of a shotgun approach
    dist_pkgs = "/usr/lib/python{}/dist-packages".format(
            fabric.env.cfg.python_version)

    site_pkgs = root_path("shared/system/lib",
            "python{}".format(fabric.env.cfg.python_version), "site-packages")

    args = ["-name {!r}".format(glob) for value in DIST_PACKAGES.values()
            for glob in value]

    fabric.run("find {} {} | xargs -I % ln -s % {}".format(
        dist_pkgs, " -o ".join(args), site_pkgs), warn_only=True)


@fabric.task
@requires_config
def setup():
    """Setup a new environment, no deployment
    """
    fabric.execute(configure_ssh)
    fabric.execute(create_directories)
    fabric.execute(create_virtualenv)
    fabric.execute(link_dist_packages)
    fabric.execute(create_upstart_configs)
    fabric.execute(create_nginx_config)
    fabric.execute(create_binstubs)


@fabric.task
@requires_config
def recreate_virtualenv():
    """Purge the old virtualenv and recreate
    """
    fabric.execute(create_virtualenv, recreate=True)
    fabric.execute(link_dist_packages)


@fabric.task
@requires_config
def purge():
    """Completely remove all app directories
    """
    with fabric.cd(fabric.env.cfg.root):
        for directory, _, _ in DIRECTORIES:
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
    error.test("groups | grep www-data", "User not in the `www-data` group")

    return error.value


@fabric.task
@requires_config
def configure_server(as_user):
    """Do one-time configuration of server
    """
    cfg_dict = fabric.env.cfg.as_dict()
    group_check = "groups {} | cut -d: -f2 | grep www-data"
    cp_upstart = "cp {root}/shared/init/{app_name}-{env_name}-* /etc/init"

    template = local_path("templates/sudoers")
    with open(template) as fp:
        sudoers_template = fp.read()

    with fabric.settings(user=as_user):
        if not test_cmd(group_check.format(fabric.env.cfg.user)):
            fabric.sudo("usermod -a -G www-data {}".format(fabric.env.cfg.user))

        append_to_file("/etc/sudoers",
                sudoers_template.format(**cfg_dict), use_sudo=True)

    fabric.execute(setup)

    with fabric.settings(user=as_user):
        fabric.sudo(cp_upstart.format(**cfg_dict))

    fabric.execute(put_secrets)

    # Don't do this since puppet manages this
    #"cp {root}/shared/config/{app_name}-{env_name} /etc/nginx/sites-enabled"


@fabric.task
@requires_config
def put_secrets():
    """Push secret configs to server and set permissions
    """
    secret_file = root_path("shared/secrets/environ.cfg")
    secrets = os.path.join("config", "secrets", fabric.env.cfg.app_name,
            "{}.cfg".format(fabric.env.environment_name))

    fabric.put(secrets, secret_file)
    fabric.run("chmod 600 {}".format(secret_file))
