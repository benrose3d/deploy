import fabric.api as fabric

from utils import get_config

import deploy
import shell


@fabric.task
@fabric.runs_once
@fabric.hosts("localhost")
def env(project, env_name):
    """Set environment name and load config
    """
    cfg = get_config(env_name, "config/{}.cfg".format(project))

    fabric.env.port = int(cfg.get("port", 22))
    fabric.env.cfg = cfg
    fabric.env.cfg["env_name"] = env_name
    fabric.env.environment_name = env_name
    fabric.env.hosts = cfg.server_list
    fabric.env.user = cfg.user
    fabric.env.can_sudo = cfg.get_bool("can_sudo")
