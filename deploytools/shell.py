import fabric.api as fabric

from .utils import requires_config, root_path


@fabric.task
@requires_config
def shell():
    """Start a django shell
    """
    pass


@fabric.task
@requires_config
def clearsessions():
    """clear the Django sessions
    """
    args = [root_path('bin/run'), "clearsessions"]
    fabric.run(" ".join(args))

@fabric.task
@requires_config
def invalidate():
    """Invalidate the caches
    """
    args = [root_path('bin/run'), "invalidate", "--all"]
    fabric.run(" ".join(args))



@fabric.task
@requires_config
def tail_log():
    """Tail application log
    """
    pass
