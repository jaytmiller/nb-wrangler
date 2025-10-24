"""
This module manages the central nb-wrangler persistent environtment store which has
a directory organization something like:

${NBW_PANTRY}/
  pantry.yaml
  shelves/
    spec-1-shelf/
      wrangler-spec.yaml
      archives/ (cans)
        env-1-tar
        repo-1-clone.tar.gz   ...
        data-1-clone.tar.gz   ...
      notebook_repos/  (unpacked notebooks)
        repo-clone-1/
        repo-clone-2/
      data/  (unpacked data)
        live-data-dir-1/
        live-data-dir-2/
        ...
    spec-2-shelf
        ...
    ...

A related live installation may or may not be located on persistent storage but is
kept separate to enable locating it on highly performant but ephemeral storage:

${NBW_ROOT}/
  mm/
    bin
    pkgs
    envs/
      env-1
  temps/
  cache/
  notebook_repos/
    shelf-1/
      repo-clone-1
      ...
  data/
    shelf-1/
      live-data-dir-1
      ...
"""

from pathlib import Path

from .logger import WranglerLogger
from .spec_manager import SpecManager
from .environment import EnvironmentManager


NBW_ARCHIVE = NBW_PANTRY / shelves /


class NbwPantry:
    def __init__(
        self,
        logger: WranglerLogger,
        spec_manager: SpecManager,
        env_manager: EnvironmentManager,
    ):
        """
        Initialize the NbwPantry with a logger, a spec manager, and an environment manager.

        The pantry is responsible for managing shelves, cans, and the overall environment store.
        """
        pass

    def create_pantry(self) -> Path:
        """
        Create the central environment store directory structure.
        This includes metadata, specs, shelves, and archives directories.
        Returns the path to the created pantry.
        """
        raise NotImplementedError("create_pantry not yet implemented")

    def create_shelf(self, spec_path: str | Path) -> Path:
        """
        Create a new shelf based on the provided specification.
        The shelf will have subdirectories for cans, notebooks, and data.
        Returns the path to the newly created shelf.
        """
        raise NotImplementedError("create_shelf not yet implemented")

    def delete_shelf(self, spec_path: str | Path) -> bool:
        """
        Delete an existing shelf.
        This operation should be cautious and may require confirmation.
        Returns True if deletion was successful, False otherwise.
        """
        raise NotImplementedError("delete_shelf not yet implemented")

    def install_shelf(self, spec_path: str | Path) -> bool:
        """
        Install a shelf from its specification, possibly by unpacking a tarball or cloning notebooks.
        Returns True if installation was successful, False otherwise.
        """
        raise NotImplementedError("install_shelf not yet implemented")

    def archive_shelf(self, spec_path: str | Path) -> Path:
        """
        Archive a shelf into a compressed file for backup or distribution.
        Returns the path to the archived file.
        """
        raise NotImplementedError("archive_shelf not yet implemented")

    def list_shelves(self) -> list[str]:
        """
        List all shelves present in the pantry.
        Returns a list of shelf names.
        """
        raise NotImplementedError("list_shelves not yet implemented")


class NbwShelf:
    """
    Represents a shelf in the environment store.

    A shelf is defined by a single wrangler spec,  which in turn defines a set of notebook
    repositories and notebooks,  and in turn defines set of refdata_dependencies.yaml files
    and requirements.txt files respectively.  The requirements.txt files and wrangler spec
    collectively define a single mamba environment.

    A shelf contains multiple cans (environments), notebook repositories, and data directories.
    This class may provide methods to manage the contents of a shelf.
    """


class NbwCan:
    """
    Represents a can (environment) within a shelf.

    A can is typically a tarball containing an environment, and may include notebooks and data.
    This class may provide methods to interact with the environment contained in the can.
    """
