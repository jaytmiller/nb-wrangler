.PHONY: clean clean-pyc clean-test coverage dist docs help install lint lint/flake8 lint/black lint/mypy
.DEFAULT_GOAL := help

define PROJECT
nb_wrangler
endef
export PROJECT

define BROWSER_PYSCRIPT
import os, webbrowser, sys

from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

define TEST_OUTPUTS
output
references
endef
export TEST_OUTPUTS

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

setup:
	pip install .[dev]

# ==========================================================================================================

functional: fnc-preclean fnc-bootstrap functional-develop functional-tests functional-reinstall functional-misc

functional-develop: fnc-curate

functional-reinstall: fnc-reinstall

functional-tests:  fnc-test fnc-test-imports fnc-test-notebooks

functional-misc: fnc-compact fnc-pack-env fnc-uninstall fnc-unpack-env \
	fnc-unregister-env	fnc-register-env fnc-delete-env fnc-reset-spec


fnc-preclean:
	rm -rf ${HOME}/.nbw-live  ./references

fnc-bootstrap: fnc-preclean
	# curl https://raw.githubusercontent.com/spacetelescope/nb-wrangler/refs/heads/main/nb-wrangler >nb-wrangler
	# chmod +x nb-wrangler
	./nb-wrangler bootstrap

fnc-curate:
	./nb-wrangler  fnc-test-spec.yaml --curate

fnc-reinstall:
	./nb-wrangler  fnc-test-spec.yaml --reinstall

fnc-uninstall: fnc-curate
	./nb-wrangler  fnc-test-spec.yaml --uninstall

fnc-install: fnc-curate fnc-uninstall
	./nb-wrangler   fnc-test-spec.yaml --install

fnc-pack-env: fnc-install
	./nb-wrangler   fnc-test-spec.yaml --pack-env

fnc-unpack-env:  fnc-uninstall
	./nb-wrangler   fnc-test-spec.yaml --unpack-env

fnc-test-imports: fnc-install
	./nb-wrangler   fnc-test-spec.yaml --test-imports

fnc-test-notebooks: fnc-install
	./nb-wrangler   fnc-test-spec.yaml --test-notebooks

fnc-test: fnc-install
	./nb-wrangler   fnc-test-spec.yaml -t

fnc-compact: fnc-install
	./nb-wrangler   fnc-test-spec.yaml --compact

fnc-compile: fnc-clone
	./nb-wrangler   fnc-test-spec.yaml --compile

fnc-clone:
	./nb-wrangler   fnc-test-spec.yaml --clone

fnc-init-env: fnc-compile
	./nb-wrangler   fnc-test-spec.yaml --init-env

fnc-delete-env: fnc-init-env
	./nb-wrangler   fnc-test-spec.yaml --delete-env

fnc-register-env: fnc-init-env
	./nb-wrangler   fnc-test-spec.yaml --register-env

fnc-unregister-env: fnc-init-env
	./nb-wrangler   fnc-test-spec.yaml --unregister-env

fnc-reset-spec: fnc-compile
	./nb-wrangler   fnc-test-spec.yaml --reset-spec

fnc-validate-spec: fnc-compile
	./nb-wrangler   fnc-test-spec.yaml --validate-spec
	git checkout -- fnc-test-spec.yaml


# ==========================================================================================================

clean: clean-build clean-pyc clean-test clean-other ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -fr .pytest_cache
	rm -fr $$TEST_OUTPUTS

clean-other:
	rm -rf prof
	rm -f .coverage
	rm -fr htmlcov/
	rm -rf .mypy_cache

lint/flake8: ## check style with flake8
	find ${PROJECT} tests -name '*.py' | xargs flake8  --max-line-length 120 \
	  --ignore E302,E203,E305,W291,W503,W504,W391,E501,E226 --count  --statistics

lint/black: ## check style with black
	black --check ${PROJECT} tests

lint/bandit: ## check security with bandit
	find ${PROJECT} tests -name '*.py' | xargs bandit -v -ll -ii --format txt

lint/mypy:
	mypy --install-types  --non-interactive  ${PROJECT}

lint: lint/flake8  lint/mypy  lint/black  lint/bandit ## check style, type annotations, whitespace


test-all: setup lint local-test

test: local-test

test-bootstrap: test-bootstrap-only test-bootstrap-spec

test-bootstrap-only:
	rm -rf $NBW_ROOT
	make clean
	./nb-wrangler bootstrap

test-bootstrap-spec:
	rm -rf $NBW_ROOT
	make clean
	./nb-wrangler bootstrap ./fnc-test-spec.yaml

local-test:  clean-test   ## run tests quickly with the default Python
	./local-test pytest

coverage: clean-test ## check code coverage quickly with the default Python
	./local-test coverage
	$(BROWSER) htmlcov/index.html

dist: clean ## builds source and wheel package
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

install: clean ## install the package to the active Python's site-packages
	python setup.py install
