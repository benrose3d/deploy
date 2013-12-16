#!/bin/bash

export PYTHONPATH="%(root)s/current:%(root)s/current/%(app_name)s"
export PATH="%(root)s/shared/system/bin:%(root)s/bin:%(root)s:/usr/bin:/bin"

COMMAND="$1"
shift

[[ -z "$COMMAND" ]] && COMMAND="help"

%(runner)s $COMMAND --settings=%(app_name)s.settings $@
