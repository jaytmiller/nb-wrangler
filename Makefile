.PHONY: clean clean-pyc clean-test coverage dist docs help install lint lint/flake8 lint/black lint/mypy
.DEFAULT_GOAL := help

SHELL := /bin/bash

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

test-functional: setup functional data-functional data-clean


functional: fnc-preclean fnc-bootstrap functional-develop functional-tests functional-reinstall functional-misc

functional-develop: fnc-curate

functional-reinstall: fnc-reinstall

functional-tests:  fnc-test fnc-test-imports fnc-test-notebooks

functional-misc: fnc-compact fnc-env-pack fnc-packages-uninstall fnc-env-unpack \
	fnc-env-unregister	fnc-env-register fnc-env-delete fnc-spec-reset fnc-packages-compile


fnc-preclean:
	rm -rf ${NBW_ROOT} ./references

fnc-bootstrap: fnc-preclean
	# curl https://raw.githubusercontent.com/spacetelescope/nb-wrangler/refs/heads/main/nb-wrangler >nb-wrangler
	# chmod +x nb-wrangler
	./nb-wrangler bootstrap

fnc-curate:
	./nb-wrangler  fnc-test-spec.yaml --curate

fnc-reinstall:
	./nb-wrangler  fnc-test-spec.yaml --reinstall

fnc-packages-uninstall: fnc-curate
	./nb-wrangler  fnc-test-spec.yaml --packages-uninstall

fnc-packages-install: fnc-curate fnc-packages-uninstall
	./nb-wrangler   fnc-test-spec.yaml --packages-install

fnc-env-pack: fnc-packages-install
	./nb-wrangler   fnc-test-spec.yaml --env-pack

fnc-env-unpack:  fnc-packages-uninstall
	./nb-wrangler   fnc-test-spec.yaml --env-unpack

fnc-test-imports: fnc-packages-install
	./nb-wrangler   fnc-test-spec.yaml --test-imports

fnc-test-notebooks: fnc-packages-install
	./nb-wrangler   fnc-test-spec.yaml --test-notebooks

fnc-test: fnc-packages-install
	./nb-wrangler   fnc-test-spec.yaml -t

fnc-compact: fnc-packages-install
	./nb-wrangler   fnc-test-spec.yaml --env-compact

fnc-packages-compile: fnc-clone-repos
	./nb-wrangler   fnc-test-spec.yaml --packages-compile

fnc-clone-repos:
	./nb-wrangler   fnc-test-spec.yaml --clone-repos

fnc-env-init: fnc-packages-compile
	./nb-wrangler   fnc-test-spec.yaml --env-init

fnc-env-delete: fnc-env-init
	./nb-wrangler   fnc-test-spec.yaml --env-delete

fnc-env-register: fnc-env-init
	./nb-wrangler   fnc-test-spec.yaml --env-register

fnc-env-unregister: fnc-env-init
	./nb-wrangler   fnc-test-spec.yaml --env-unregister

fnc-spec-reset: fnc-packages-compile
	./nb-wrangler   fnc-test-spec.yaml --spec-reset
	git checkout -- fnc-test-spec.yaml

fnc-spec-validate: fnc-packages-compile
	./nb-wrangler   fnc-test-spec.yaml --spec-validate
	git checkout -- fnc-test-spec.yaml


# ==========================================================================================================

DATA_STEPS = data-collect data-validate data-download data-update data-unpack data-pack \
	data-list data-delete data-select

DATA_WORKFLOWS =  wrangler-spec-curate data-test-curate data-test-reinstall

DATA_SELECTED = 'pandeia|stpsf|other-spectra_multi_v2_sed'

data-clean:
	source ./nb-wrangler environment  &&  \
	cd tests/data-functional && \
	rm -rf ${NBW_PANTRY} && \
	rm -rf references && \
	git checkout -- data-test-spec.yaml

data-functional: data-clean wrangler-spec-curate data-test-workflows # data-test-steps

wrangler-spec-curate:
	source ./nb-wrangler environment  &&  \
	cd tests/data-functional && \
	../../nb-wrangler data-test-spec.yaml --spec-reset && \
	../../nb-wrangler data-test-spec.yaml --curate

data-test-workflows: data-clean ${DATA_WORKFLOWS}

data-test-curate:
	. ./nb-wrangler environment  &&  \
	cd tests/data-functional && \
	../../nb-wrangler data-test-spec.yaml --data-reset-spec && \
	../../nb-wrangler data-test-spec.yaml --data-curate --data-select ${DATA_SELECTED}

data-test-reinstall:
	. ./nb-wrangler environment  &&  \
	cd tests/data-functional && \
	../../nb-wrangler data-test-spec.yaml --data-reinstall --data-select ${DATA_SELECTED}

# data-test-steps: ${DATA_STEPS}


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
	pip install .
