"""
This module manages the central nb-curator environtment store which has
a directory organization something like:

${NBC_PANTRY}/
  metadata/
  specs/
    shelf-1-spec.yaml
    shelf-1-spec.yaml
    ...
  shelves/
    shelf-1/
      curator-spec.yaml
      cans/
        env-1-tar.xz
        env-1-tar.xz
        ...
      notebook_repos/
        repo-clone-1/
        repo-clone-2/
        ...
      data/
        live-data-dir-1/
        live-data-dir-2/
        ...
    shelf-2
        ...
  archives:
    shelf-1.tar.xz
    ...

In addition to the environment specification, creation, and test functions
the curator was initially designed for,  the NbcPantry class
"""

class NbcPantry:
    def __init__(self, logger: CuratorLogger, spec_manager: SpecManager, env_manager: EnvironmentManager):
        """
        Initialize the NbcPantry with a logger and a spec manager.
        The pantry is responsible for managing shelves, cans, and the overall environment store.
        """
        pass
    
    def create_pantry(self) -> Path:
        """
        Create the central environment store directory structure.
        This includes metadata, specs, shelves, and archives directories.
        Returns the path to the created pantry.
        """
        pass

    def create_shelf(self, spec_path: str|Path) -> Path:
        """
        Create a new shelf based on the provided specification.
        The shelf will have subdirectories for cans, notebooks, and data.
        Returns the path to the newly created shelf.
        """
        pass

    def delete_shelf(self, spec_path: str|Path) -> bool:
        """
        Delete an existing shelf.
        This operation should be cautious and may require confirmation.
        Returns True if deletion was successful, False otherwise.
        """
        pass

    def install_shelf(self, spec_path: str|Path) -> bool:
        """
        Install a shelf from its specification, possibly by unpacking a tarball or cloning notebooks.
        Returns True if installation was successful, False otherwise.
        """
        pass

    def archive_shelf(self, spec_path: str|Path) -> Path:
        """
        Archive a shelf into a compressed file for backup or distribution.
        Returns the path to the archived file.
        """
        pass

    def list_shelves(self) -> list[str]:
        """
        List all shelves present in the pantry.
        Returns a list of shelf names.
        """
        pass


class NbcShelf:
    """
    Represents a shelf in the environment store.
    A shelf contains multiple cans (environments), notebook repositories, and data directories.
    This class may provide methods to manage the contents of a shelf.
    """
    pass


class NbcCan:
    """
    Represents a can (environment) within a shelf.
    A can is typically a tarball containing an environment, and may include notebooks and data.
    This class may provide methods to interact with the environment contained in the can.
    """
    pass
