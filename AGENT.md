# AGENT.md - nb-wrangler Development Guide

## Commands
- **Lint**: `make lint` (includes flake8, mypy, black, bandit)
- **Test**:`make test-functional` 
- **Coverage**: `make coverage`
- **Format**: `black nb_wrangler tests`
- **Run tool**: `python -m nb_wrangler spec.yaml [options]`

## Architecture
- **Core**: nb-wrangler orchestrates Jupyter notebook environment and data curation
- **Components**: wrangler.py (main), spec_manager.py (YAML specs), environment.py (micromamba/uv envs), compiler.py (deps), repository.py (git), notebook_tester.py (headless testing)
- **Dependencies**: micromamba, uv, papermill, jupyter, ruamel.yaml
- **Environments**: Creates isolated envs under ~/.nbw-live and ~/.nbw-pantry for notebook testing

## Code Style
- **Type hints**: Required for all functions (Python 3.11+)
- **Imports**: Absolute imports, group stdlib/third-party/local
- **Classes**: PascalCase, descriptive names (NotebookWrangler, EnvironmentManager)
- **Methods**: snake_case with docstrings
- **Error handling**: WranglerLogger.error() returns False pattern, exceptions logged
- **Formatting**: black (120 char line length), flake8 linting
- **Dataclasses**: Used for config (WranglerConfig)
- **Logging**: Use self.logger.debug/info/warning/error consistently
