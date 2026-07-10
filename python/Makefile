default: build

PYTHON = python3

config:
	sudo apt install pipx
	sudo apt install pytest
	pipx install twine

VERSION := $(shell cat ../VERSION)
setup:
	@echo "Updating pyproject.toml to $(VERSION)"
	sed -i -E 's/^(version *= *")[^"]*(")/\1$(VERSION)\2/' pyproject.toml

SRCS = src/core.py src/engine.py src/logic.py src/runtime.py src/template.py src/py_expr.py src/py_run.py

%.py.check: %.py
	$(PYTHON) -m py_compile $<

build: $(SRCS:=.check)

.PHONY: %.t

TESTS = $(wildcard tests/test_*.py)

run-test:
	pytest
	(cd ../tests/basic && ../run_tests.sh -mpython)
	(cd ../tests/pyrun && ../run_tests.sh -mpyrun)

test:
	$(MAKE) run-test | tee test.log

package:
	rm -f dist/jsonfold-$(VERSION)[.-]*
	$(PYTHON) -m build
	twine check dist/jsonfold-$(VERSION)[.-]*

T=tmp
setup-verify:
	rm -rf $T
	mkdir -p $T
	python3 -m pip install --no-deps --target $T dist/jsonfold-*.whl

R=run
run-verify:
	rm -rf $R
	mkdir -p $R
	cd $R && python3 -S -c 'import runpy ; import os ; runpy.run_path("${CURDIR}/api_test.py", run_name="__main__")'
	cd $R && python3 -S -m runpy jsonfold --demo
	cd $R && python3 -S -m runpy cli --demo
	cd $R && python3 -S -c 'import runpy ; import os ; runpy.run_path("${CURDIR}/benchmark.py", run_name="__main__")' 10

verify:
	$(MAKE) setup-verify
	PYTHONPATH=$(CURDIR)/$T $(MAKE) run-verify > verify.log
	wc verify.log
	echo "Passed: $@"

publish:
	twine upload dist/jsonfold-$(VERSION)[.-]*

benchmark:
	./run_benchmark.sh

clean:
	rm -rf dist *.egg-info

realclean: clean
	rm -f *.out  *.prof *.lprof *.cover
	rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov .venv

world:
	make realclean
	make setup
	make build
	make test
	make benchmark
	make package
	make verify
