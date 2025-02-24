#!/bin/bash
#set -x
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)

pids=$(pgrep -f "python $SCRIPT_DIR/$SERVICE_NAME.py")
if [[ -n $pids ]]; then
  echo "restart: kill $pids"
  kill $pids
else
  echo "no restart: $SERVICE_NAME.py not running"
fi
