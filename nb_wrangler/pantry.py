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

from . import utils

# from .utils import DataDownloadError
from .logger import WranglerLoggable
from .constants import NBW_PANTRY, DATA_GET_TIMEOUT

# from .data_manager import DataSectionUrl


class NbwPantry(WranglerLoggable):
    def __init__(self, path: Path = NBW_PANTRY):
        """
        Initialize the NbwPantry with a logger, a spec manager, and an environment manager.

        The pantry is responsible for managing shelves, cans, and the overall environment store.
        """
        super().__init__()
        self.path = path
        self.shelves = self.path / "shelves"
        self.shelves.mkdir(parents=True, exist_ok=True)

    def get_shelf(self, shelf_name: str) -> "NbwShelf":
        """
        Create the central environment store directory structure.
        This includes metadata, specs, shelves, and archives directories.
        Returns the path to the created pantry.
        """
        return NbwShelf(self.shelves / shelf_name)

    def delete_shelf(self, shelf_name: str | Path) -> bool:
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


class NbwShelf(WranglerLoggable):
    """
    Represents a shelf in the environment store.

    A shelf is defined by a single wrangler spec,  which in turn defines a set of notebook
    repositories and notebooks,  and in turn defines set of refdata_dependencies.yaml files
    and requirements.txt files respectively.  The requirements.txt files and wrangler spec
    collectively define a single mamba environment.

    A shelf contains multiple cans (environments), notebook repositories, and data directories.
    This class may provide methods to manage the contents of a shelf.

    spec-1-shelf/
      wrangler-spec.yaml
      archives/ (cans)
        env-1-tar
        repo-1.tar.gz   ...
        data-1.tar.gz   ...
      notebook_repos/  (unpacked notebooks)
        repo-1/
        repo-2/
        ...
      data/  (unpacked data)
        data-1/
        data-2/
        ...
    """

    def __init__(self, shelf_path: Path):
        super().__init__()
        self.path = shelf_path

        self.path.mkdir(parents=True, exist_ok=True)
        self.archive_root.mkdir(parents=True, exist_ok=True)
        self.notebook_repos_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)

    @property
    def name(self):
        return self.path.name

    @property
    def archive_root(self) -> Path:
        return self.path / "archives"

    @property
    def notebook_repos_path(self) -> Path:
        return self.path / "notebooks"

    @property
    def data_path(self) -> Path:
        return self.path / "data"

    @property
    def abstract_data_path(self):
        return Path("${NBW_PANTRY}/shelves") / self.name / "data"

    @property
    def spec_path(self) -> Path:
        return self.path / "nbw-wranger-spec.yaml"

    def set_wrangler_spec(self, wrangler_spec_path: str) -> Path:
        with self.spec_path.open("w+") as dest_stream:
            with Path(wrangler_spec_path).open("r") as source_stream:
                dest_stream.write(source_stream.read())
        return self.spec_path

    def archive_path(self, archive_tuple: tuple[str, str, str]) -> Path:
        part: str
        path = self.archive_root
        for part in archive_tuple[:-1]:
            path = path / part
        return path

    def archive_url(self, archive_tuple: tuple[str, str, str]) -> str:
        return archive_tuple[-1]

    def archive_filepath(self, archive_tuple: tuple[str, str, str]) -> Path:
        archive_path = self.archive_path(archive_tuple)
        url = self.archive_url(archive_tuple)
        return archive_path / Path(url).name

    def archive_rel_filepath(self, archive_tuple: tuple[str, str, str]) -> str:
        s = str(self.archive_filepath(archive_tuple))
        t = str(self.archive_root)
        return s.removeprefix(t)[1:]

    def download_all_data(
        self, archive_tuples: list[tuple[str, str, str]], force: bool = False
    ) -> bool:
        errors = False
        for archive_tuple in archive_tuples:
            errors = self.download_data(archive_tuple, force=force) or errors
        return errors

    def download_data(
        self, archive_tuple: tuple[str, str, str], force: bool = False
    ) -> bool:
        archive_path = self.archive_path(archive_tuple)
        archive_path.mkdir(parents=True, exist_ok=True)
        key = self.archive_rel_filepath(archive_tuple)
        url = self.archive_url(archive_tuple)
        if not self.archive_filepath(archive_tuple).exists() or force:
            self.logger.info(f"Downloading data from '{url}' to archive file '{key}'.")
            try:
                utils.robust_get(url, timeout=DATA_GET_TIMEOUT, cwd=str(archive_path))
            except Exception as e:
                return self.logger.exception(
                    e, f"Failed downloading '{url}' to archive file '{key}':"
                )
        else:
            self.logger.info(
                f"Archive file for '{key}' already exists. Skipping downloads."
            )
        return False

    def validate_all_data(
        self,
        archive_tuples: list[tuple[str, str, str]],
        data_metadata: dict[str, dict[str, str]],
    ) -> bool:
        errors = False
        for archive_tuple in archive_tuples:
            key = self.archive_rel_filepath(archive_tuple)
            errors = self.validate_data(archive_tuple, data_metadata[key]) or errors
        return errors

    def validate_data(
        self, archive_tuple: tuple[str, str, str], metadata: dict[str, str]
    ) -> bool:
        errors = False
        key = self.archive_rel_filepath(archive_tuple)
        self.logger.info(f"Validating data archive '{key}'.")

        old_size, old_sha256 = metadata["size"], metadata["sha256"]

        d = self.collect_metadata(archive_tuple)
        new_size, new_sha256 = d["size"], d["sha256"]

        if new_size != old_size:
            errors = self.logger.error(
                f"Size mismatch for '{key}' expected '{old_size}' but got '{new_size}'."
            )
        if new_sha256 != old_sha256:
            errors = self.logger.error(
                f"SHA256 mismatch for '{key}' expected '{old_sha256}' but got '{new_sha256}'."
            )
        return errors

    def collect_all_metadata(
        self, archive_tuples: list[tuple[str, str, str]]
    ) -> dict[str, dict[str, str]]:
        return {
            self.archive_rel_filepath(archive_tuple): self.collect_metadata(
                archive_tuple
            )
            for archive_tuple in archive_tuples
        }

    def collect_metadata(self, archive_tuple: tuple[str, str, str]) -> dict[str, str]:
        key = self.archive_rel_filepath(archive_tuple)
        new_path = self.archive_filepath(archive_tuple)
        new_size = str(new_path.stat().st_size)
        self.logger.info(f"Computing sha256 for archive file '{key}'.")
        new_sha256 = utils.sha256_file(new_path)
        return dict(size=new_size, sha256=new_sha256)

    def save_exports_file(self, filename: str, exports: dict[str, str]) -> None:
        with (self.path / filename).open("w+") as stream:
            for var, value in exports.items():
                stream.write(f"export {var}={value}\n")


class NbwCan:
    """
    Represents a can (environment) within a shelf.

    A can is typically a tarball containing an environment, and may include notebooks and data.
    This class may provide methods to interact with the environment contained in the can.
    """
