# AGENT.md - nb-curator Development Guide

## Commands
- **Lint**: `make lint` (includes flake8, mypy, black, bandit)
- **Test**: `make local-test` or `./local-test pytest` 
- **Coverage**: `make coverage`
- **Format**: `black nb_curator tests`
- **Run tool**: `python -m nb_curator spec.yaml [options]`

## Architecture
- **Core**: nb-curator orchestrates Jupyter notebook environment curation
- **Components**: curator.py (main), spec_manager.py (YAML specs), environment.py (micromamba/uv envs), compiler.py (deps), repository.py (git), notebook_tester.py (headless testing)
- **Dependencies**: micromamba, uv, papermill, jupyter, ruamel.yaml
- **Environments**: Creates isolated envs under ~/.nb-curator for notebook testing

## Code Style
- **Type hints**: Required for all functions (Python 3.11+)
- **Imports**: Absolute imports, group stdlib/third-party/local
- **Classes**: PascalCase, descriptive names (NotebookCurator, EnvironmentManager)
- **Methods**: snake_case with docstrings
- **Error handling**: CuratorLogger.error() returns False pattern, exceptions logged
- **Formatting**: black (120 char line length), flake8 linting
- **Dataclasses**: Used for config (CuratorConfig)
- **Logging**: Use self.logger.debug/info/warning/error consistently
