#!/bin/bash
#
# test_pack.sh — extract JQ/INPUT/EXPECTED/JFTL sections from a test file
# in the [ID] / KEY = {{{ ... }}} format, run jq for each case, and write
# <ID>.jq.out (plus <ID>.jq.err on failure) into the output directory.
#
# Usage: ./run_jq_tests.sh <testfile> [outdir]
 
set -uo pipefail
 
OUTDIR=tmp
KEEP=
while getopts T: opt ; do
	case "$opt" in
		T) OUTDIR=$OPTARG ;;
		K) KEEP=YES ;;
	esac
done

shift $((OPTIND-1))
input='(stdin)'
if [ "${1-}" ] ; then
	if [ "$1" != "-" ] ; then
		exec < $1
		input="$1"
	fi
	shift
fi

command -v jq >/dev/null 2>&1 || { echo "jq not found on PATH" >&2; exit 1; }

echo "Reading: $input ..." >&2
 
 
# --- 1. split the test file into per-ID, per-section files -----------------
#
# [ID]                       -> starts a new test case
# KEY = {{{  ... }}}         -> KEY's content, written verbatim to $OUTDIR/ID.key
# anything else outside a block (blank lines, '#' comments, single-line
# KEY=value headers) is ignored by this script.
#

ID_RE='[a-zA-Z0-9][a-zA-Z0-9._-]+'
SECTION_RE="^\[($ID_RE)\]$"
KEY_VAL_RE="^ *($ID_RE) *= *(.*)$"
BLOCK_START_RE="^ *($ID_RE) *= *\{\{\{ *$"
BLOCK_END_RE="}}}"

declare -A data
id=
in_block=
id_list=()

while read line ; do
	if [[ "$in_block" ]] ; then
		if [[ "$line" =~ $BLOCK_END_RE ]] ; then
			in_block=""
		else
			[ "$id" ] && data[$in_block]+=$line$'\n'
		fi

	# Outside Block
	elif [[ "$line" =~ $SECTION_RE ]] ; then
		# New Section
		[ "$id" ]
		id=${BASH_REMATCH[1]}
		id_list+=($id)
	elif [[ "$line" =~ $BLOCK_START_RE ]] ; then
		key=${BASH_REMATCH[1]}
		in_block="$id.$key"
	elif [[ "$line" =~ $KEY_VAL_RE ]] ; then
		key=${BASH_REMATCH[1]}
		value=${BASH_REMATCH[2]}
		[ "$id" ] && data["$id.$key"]=$value
	fi
done
mkdir -p "$OUTDIR"

if [ ! "$*" ] ; then
	set -- "${id_list[@]}"
	ALL=
fi
echo "Found ${#id_list[@]} tests, Running $#, using OUTDIR=$OUTDIR" >&2

# Execute Tests
pass=0
fail=0
skip=0
for id ; do
	base="$OUTDIR/$id"
	rm -f $base.input $base.jq $base.jq.out $base.jq.err
	skip_msg=${data["$id.SKIP"]-}
	jq_filter=${data["$id.JQ"]-}
	input=${data["$id.INPUT"]-}
	jftl=${data["$id.JFTL"]-}
	gold=${data["$id.EXPECTED"]-}
	input_file=$base.input
	jq_file=$base.jq
	gold_file=$base.gold
	jq_out=$base.jq.out
	err_file=$base.err
	jf_file=$base.jftl
	jf_out=$base.jf.out
	# Run from memory
	error=
	rm -f $OUTDIR/$id.{input,gold,jq.out,jf.out,err,diff}
	rm -f $err_file
	if [ "$skip_msg" ] ; then
		error=SKIP
	elif [ ! "$jq_filter" ] ; then
		error="No JQ Filter"
	elif [ ! "$jftl" ] ; then
		error="No JFTL"
	elif [ ! "$gold" ] ; then
		error="No GOLD"
	else
		echo "$jq_filter" > "$jq_file"
		echo "$jftl" > "$jf_file"
		echo "$gold" | json_pp > "$gold_file"
		if [ "$input" ] ; then
			echo "$input" > $input_file
		else
			input_file=
		fi

		echo "=== jq:" >> $err_file
		if ! jq -f $jq_file < ${input_file:-/dev/null} > "$jq_out" 2>> "$err_file" ; then
			error=${error+, }"JQ Fail"
		else
			echo "=== jq-diff:" >> $err_file
			if ! diff <(json_pp <$jq_out) "$gold_file" >> $base.diff ; then
				error+=${error+, }"JQDIFF"
			fi
		fi

		echo "=== jf_template:" >> $err_file
		if ! ../../python/run.sh $jf_file $input_file > "$jf_out" 2>> "$err_file" ; then
			error+=${error+, }"JF fail"
		else
			echo "=== jf-diff:" >> $err_file
			if ! diff <(json_pp <$jq_out) "$gold_file" >> $base.diff ; then
				error+=${error+, }"JFDiff"
			fi
		fi
	fi

	if [ "$skip_msg" ] ; then
		echo "SKIP $id ($skip)" >&2
		skip=$((skip+1))
	elif [ "$error" ]; then
		echo "FAIL $id ($error) see $err_file" >&2
		fail=$((fail+1))
	else
		echo "OK $id"
        	pass=$((pass+1))
		[ "$KEEP" ] || rm -f $OUTDIR/$id.{input,jq,jftl,gold,jq.out,err,jf.out,err,diff}
	fi
done
 
echo "---"
echo "Completed: $((pass+fail+skip)), ok: $pass, fail: $fail, skipped: $skip" >&2
[ "$fail" = 0 ]
