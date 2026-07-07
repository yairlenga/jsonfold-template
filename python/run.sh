#! /bin/sh

ME=$(readlink -f $0)
DIR=${ME%/*}
exec python3 $DIR/scripts/jf_template.py "$@"
