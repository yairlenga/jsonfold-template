#!/bin/bash -ue

root=$(readlink -m $0/../..)
mode=
name=

case "${1-}" in
	-mpython | -mpy ) shift ; mode=python ; JSONFOLD="$root/python/run.sh" ;;
esac


read_args() {
    # print every line that starts with '--' or lines with args=...
    sed -n -e '/^--/p' -e 's/^args=//p' "$1"
}

passed=0
failed=0
skipped=0


[ "$*" ] || set -- *.gold

echo "Testing mode=${name:-$mode}, $# tests in $(pwd), Using: JSONFOLD=${JSONFOLD?No JSONFOLD}" >&2
for arg ;
do
    base=${arg%.json}
    base=${base%.jftl}
    base=${base%.arg}
    base=${base%.gold}
    gold="$base.gold"
    jftl="$base.jftl.json"
    out="$base.out"
    args="$base.args"

    if [ ! -r "$gold" ] ; then
	echo "Uknown test: $arg (missing gold '$gold')" >&2
	continue
    elif [ ! -r "$jftl" ] ; then
	echo "Uknown test: $arg (missing template '$jftl')" >&2
	continue
    else
        label=$base
	[ -r "$args" ] || args=/dev/null
	skip=$(grep "^skip.$mode=" $args || true)
	if [ "$skip" ] ; then
	    echo "SKIP $label ($mode): ${skip#*=}"
            skipped=$((skipped+1))
	    continue
	fi

        ARGS=$(read_args "$arg")
	if [ "$mode" -a -f "$base.$mode.gold" ] ; then
	    gold="$base.$mode.gold"
	    label="$base ($mode)"
        fi

	shopt -s nullglob
	files=($base.*.inp.json)
	shopt -u nullglob
        $JSONFOLD $jftl "${files[@]}" > "$out"

        if diff -u "$gold" "$out"
        then
            echo "OK $label"
            passed=$((passed+1))
        else
            failed=$((failed+1))
            echo "FAIL $label" >&2
        fi
    fi
done

echo "Passed: $passed, failed: $failed, skiped: $skipped" >&2
[ $failed = 0 ]
