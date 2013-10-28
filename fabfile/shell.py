import fabric.api as fabric

from utils import requires_config


@fabric.task
@requires_config
def shell():
    """Start a django shell
    """
    pass


@fabric.task
@requires_config
def invoke(command, *args):
    """Run a Django management command
    """
    pass


@fabric.task
@requires_config
def tail_log():
    """Tail application log
    """
    pass
