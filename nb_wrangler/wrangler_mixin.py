"""Shared mixin classes for wrangler components.

These mixins provide utility methods that are duplicated across
:class:`~nb_wrangler.wrangler.NotebookWrangler` and
:class:`~nb_wrangler.data_wrangler.DataWrangler`.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .spec_manager import SpecManager
    from .config import WranglerConfig
    from .logger import WranglerLogger
    from .environment import EnvironmentManager


class WranglerWorkflowMixin:
    """Mixin providing shared workflow and environment-variable methods.

    Classes using this mixin must also inherit from
    :class:`~nb_wrangler.config.WranglerConfigurable` and
    :class:`~nb_wrangler.logger.WranglerLoggable` so that
    ``self.config``, ``self.logger``, and ``self.spec_manager``
    are available.

    Subclasses must also provide:
    - ``self.resolved_environment_name`` (property): the environment name
      with python3→base mapping applied.
    - ``self.resolved_kname`` (property): the raw kernel name for display.
    - ``self.env_manager``: the environment manager instance.
    """

    # Declared for type-checking; provided at runtime by WranglerConfigurable
    # and WranglerLoggable.
    spec_manager: "SpecManager"
    config: "WranglerConfig"
    logger: "WranglerLogger"
    env_manager: "EnvironmentManager"

    # Declared for type-checking; provided at runtime by subclasses as
    # properties that return the appropriate name.
    @property
    def resolved_environment_name(self) -> str | None:
        """Environment name with python3→base mapping (provided by subclass)."""
        raise NotImplementedError

    @property
    def resolved_kname(self) -> str | None:
        """Raw kernel name for display (provided by subclass)."""
        raise NotImplementedError

    def run_workflow(
        self, name: str, steps: list, continue_on_failure: bool = False
    ) -> bool:
        """Run a sequence of *steps* as a named workflow.

        Each step is a no-argument callable returning ``True`` on success.
        When *continue_on_failure* is ``False`` (the default), the first
        failing step aborts the workflow and returns ``False``.  When
        ``True``, failures are logged but execution continues; the return
        value is ``False`` only if at least one step failed.
        """
        self.logger.info("Running", name, "workflow")
        overall_success = True
        for step in steps:
            self.logger.info(f"Step {step.__name__} of Workflow {name}.")
            if not step():
                if continue_on_failure:
                    self.logger.warning(f"FAILED Workflow {name} Step {step.__name__}.")
                    overall_success = False
                else:
                    return self.logger.error(
                        f"FAILED Workflow {name} Step {step.__name__}."
                    )
        if not overall_success:
            return self.logger.warning(f"Workflow {name} completed with errors.")
        return self.logger.info("Workflow", name, "completed.")

    def _get_environment_vars(self) -> dict:
        """Return the data environment variables for the current mode.

        Looks up the ``data`` section from the spec output and selects the
        ``<mode>_exports`` sub-dictionary, where *mode* is
        ``self.config.data_env_vars_mode``.
        Returns an empty dict when no data section exists or when
        ``data_env_vars_no_auto_add`` is set.
        """
        data = self.spec_manager.get_output_data("data")
        if data is not None and not self.config.data_env_vars_no_auto_add:
            mode = self.config.data_env_vars_mode
            return data.get(mode + "_exports", {})
        return {}

    def _register_environment(self) -> bool:
        """Register the target environment with Jupyter as a kernel.

        Uses ``resolved_environment_name`` (with python3→base mapping) as
        the environment name and ``resolved_kname`` for the display name.
        """
        if not self.resolved_environment_name:
            return self.logger.error("No environment name found to register.")
        env_vars = self._get_environment_vars()
        self.logger.debug(
            f"The resolved env vars for kernel '{self.resolved_environment_name}' are '{env_vars}'."
        )
        display_name = self.spec_manager.display_name or self.resolved_kname or ""
        if not self.env_manager.register_environment(
            self.resolved_environment_name, display_name, env_vars
        ):
            return False
        return True
