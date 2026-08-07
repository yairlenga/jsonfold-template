#! /bin/bash -ue

rm -f benchmark.out jf_tepmlate.py.lprof jf_template.py.prof
rm -rf prof nytprof
mkdir prof

ME=$(readlink -f $0)
DIR=${ME%/*}
CODE=$DIR/scripts/jf_template.py

function run () {
	echo "Base Run"
	python3 "$CODE" "$@" > benchmark.out
#	python3 -m trace --count --coverdir=prof "$CODE" "$@" > prof/count.out
	echo "Running cProfile"
	python3 -m cProfile -o prof/cprof.prof "$CODE" "$@"
	printf "sort tottime\nstats 30\nquit\n" | python3 -m pstats prof/cprof.prof > prof/cprof-tot.out
	printf "sort cumtime\nstats 40\nquit\n" | python3 -m pstats prof/cprof.prof > prof/cprof-cum.out
	printf "sort ncalls\nstats 30\nquit\n" | python3 -m pstats prof/cprof.prof > prof/cprof-ncalls.out
	echo "Function Profile"
	kernprof -z -b -v "$CODE" "$@" > prof/kern_prof.out
	echo "Line Profile Profile"
	kernprof -z -b -l -v -u0.001 "$CODE" "$@" > prof/line_prof.out
#	python3 -m scalene --cli --cpu-only --profile-only jsonfold "$CODE" "${@-100}" > prof/prof-scalene.out
}

function report () {
awk '
/function calls.*in.*/ && $NF == "seconds" { total = $(NF-1) }
NF >= 6 && $1 == "ncalls" && +total > 0 { filter = 1 ; header = $0  }
filter && NF >=6 && !/ncalls/ && +$1<=10 && +$2 < total*0.01 && +$4 < total*0.01 { next ; }
filter && NF >=6 && +$2 > total*0.005 {
	if ( length($1) > 8 ) $0 = sprintf("%8d*", +$1) substr($0, length($1)+1)
	top[++n_top] = $0;
	pct[n_top] = 100*$2/total
}
{ print }
END {
	if ( n_top ) {
		asorti(pct, idx, "@val_num_desc")
		print "Top Functions (self time)", n_top
		print "Percent", header
		for (i=1 ; i<=n_top ; i++ ) print sprintf("%7.1f", pct[idx[i]]), top[idx[i]]
		print "---"
	}
}
'
}
run "$@"
report < prof/kern_prof.out > prof/func_prof.out
