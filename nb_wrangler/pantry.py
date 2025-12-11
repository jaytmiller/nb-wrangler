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

import shutil
from pathlib import Path
from functools import cache
import os
from typing import Optional

from . import utils

# from .utils import DataDownloadError
from .logger import WranglerLoggable
from .environment import WranglerEnvable
from .constants import NBW_PANTRY, DATA_GET_TIMEOUT, ARCHIVE_TIMEOUT


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

    def list_shelves(self) -> bool:
        """Print out the root path of each shelf, one per line."""
        for shelf in self.shelves.glob("*"):
            print(shelf.name)
        return True

    def select_shelves(self, glob_expr: str) -> list[str]:
        return [str(shelf.name) for shelf in self.shelves.glob(glob_expr)]

    def delete_shelf(self, shelf_name: str | Path) -> bool:
        """
        Delete an existing shelf.
        This operation should be cautious and may require confirmation.
        Returns True if deletion was successful, False otherwise.
        """
        shutil.rmtree(str(self.shelves / shelf_name))
        return True

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


class NbwShelf(WranglerLoggable, WranglerEnvable):
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

    def env_archive_path(self, moniker: str, archive_format: str) -> Path:
        """Return the path for a packed environment within the shelf."""
        if not archive_format.startswith("."):
            archive_format = "." + archive_format
        return self.archive_root / ("env-" + moniker.lower() + archive_format)

    @property
    def notebook_repos_path(self) -> Path:
        return self.path / "notebook-repos"

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

    def archive_path(self, archive_tuple: tuple[str, str, str, str, str]) -> Path:
        part: str
        path = self.archive_root
        for part in archive_tuple[:-3]:
            path = path / part
        return path

    def archive_url(self, archive_tuple: tuple[str, str, str, str, str]) -> str:
        return archive_tuple[2]

    def archive_filepath(self, archive_tuple: tuple[str, str, str, str, str]) -> Path:
        archive_path = self.archive_path(archive_tuple)
        url = self.archive_url(archive_tuple)
        return archive_path / Path(url).name

    def archive_rel_filepath(
        self, archive_tuple: tuple[str, str, str, str, str]
    ) -> str:
        s = str(self.archive_filepath(archive_tuple))
        t = str(self.archive_root)
        return s.removeprefix(t)[1:]

    def download_all_data(
        self,
        archive_tuples: list[tuple[str, str, str, str, str]],
        force: bool = False,
    ) -> bool:
        no_errors = True
        for archive_tuple in archive_tuples:
            no_errors = self.download_data(archive_tuple, force=force) and no_errors
        return no_errors

    def download_data(
        self, archive_tuple: tuple[str, str, str, str, str], force: bool = False
    ) -> bool:
        archive_path = self.archive_path(archive_tuple)
        archive_path.mkdir(parents=True, exist_ok=True)
        key = self.archive_rel_filepath(archive_tuple)
        url = self.archive_url(archive_tuple)
        if not self.archive_filepath(archive_tuple).exists() or force:
            self.logger.info(f"Downloading data from '{url}' to archive file '{key}'.")
            try:
                utils.robust_get(
                    url,
                    timeout=DATA_GET_TIMEOUT,
                    cwd=str(archive_path),
                    quiet="",
                    continue_from_error="",
                )
            except Exception as e:
                return self.logger.exception(
                    e,
                    f"Failed downloading '{url}' to archive file '{key}' at '{archive_path}':",
                )
        else:
            self.logger.info(
                f"Archive file for '{Path(key).name}' already exists a '{archive_path}'. Skipping downloads."
            )
        return True

    def validate_all_data(
        self,
        archive_tuples: list[tuple[str, str, str, str, str]],
        data_metadata: dict[str, dict[str, str]],
    ) -> bool:
        no_errors = True
        for archive_tuple in archive_tuples:
            key = self.archive_rel_filepath(archive_tuple)
            no_errors = (
                self.validate_data(archive_tuple, data_metadata[key]) and no_errors
            )
        return no_errors

    def validate_data(
        self, archive_tuple: tuple[str, str, str, str, str], metadata: dict[str, str]
    ) -> bool:
        no_errors = True
        key = self.archive_rel_filepath(archive_tuple)
        self.logger.info(f"Validating data archive '{key}'.")

        old_size, old_sha256 = metadata["size"], metadata["sha256"]

        d = self.collect_metadata(archive_tuple)
        new_size, new_sha256 = d["size"], d["sha256"]

        if new_size != old_size:
            no_errors = self.logger.error(
                f"Size mismatch for '{key}' expected '{old_size}' but got '{new_size}'."
            )
        if new_sha256 != old_sha256:
            no_errors = self.logger.error(
                f"SHA256 mismatch for '{key}' expected '{old_sha256}' but got '{new_sha256}'."
            )
        return no_errors

    def collect_all_metadata(
        self, archive_tuples: list[tuple[str, str, str, str, str]]
    ) -> dict[str, dict[str, str]]:
        return {
            self.archive_rel_filepath(archive_tuple): self.collect_metadata(
                archive_tuple
            )
            for archive_tuple in archive_tuples
        }

    @cache
    def collect_metadata(
        self, archive_tuple: tuple[str, str, str, str, str]
    ) -> dict[str, str]:
        key = self.archive_rel_filepath(archive_tuple)
        new_path = self.archive_filepath(archive_tuple)
        new_size = str(new_path.stat().st_size)
        self.logger.info(f"Computing sha256 for archive file '{key}'.")
        new_sha256 = utils.sha256_file(new_path)
        return dict(size=new_size, sha256=new_sha256)

    def save_exports_file(self, filename: str, exports: dict[str, str]) -> bool:
        self.logger.info("New data exports file available at", self.path / filename)
        with (self.path / filename).open("w+") as stream:
            for var, value in exports.items():
                stream.write(f"export {var}={value}\n")
        return True

    def delete_archives(
        self, data_delete: str, archive_tuples: list[tuple[str, str, str, str, str]]
    ) -> bool:
        no_errors = True
        for archive_tuple in archive_tuples:
            no_errors = self.delete_either(data_delete, archive_tuple) and no_errors
        return no_errors

    def delete_either(
        self, data_delete: str, archive_tuple: tuple[str, str, str, str, str]
    ) -> bool:
        no_errors = True
        if data_delete in ["archived", "both"]:
            delete_path = self.archive_filepath(archive_tuple)
            if delete_path.exists():
                self.logger.info(f"Deleting data archive file at {delete_path}...")
                try:
                    delete_path.unlink(missing_ok=True)
                except Exception as e:
                    no_errors = self.logger.exception(
                        e, f"Failed deleting archive {delete_path}."
                    )
            else:
                self.logger.info(
                    f"No archive file found at {delete_path}.  Skipping packed delete."
                )
        if data_delete in ["unpacked", "both"]:
            # Deletion requires deleting the top-level directory where the archive was unpacked.
            # For a data_path like 'grp/redcat/trds', we delete 'grp'.
            delete_path = self.data_path / Path(archive_tuple[3]).parts[0]
            if delete_path.exists():
                self.logger.info(
                    f"Deleting unpacked data directory at {delete_path}..."
                )
                try:
                    shutil.rmtree(str(delete_path))
                except Exception as e:
                    no_errors = self.logger.exception(
                        e, f"Failed deleting unpacked data directory {delete_path}."
                    )
            else:
                self.logger.info(
                    f"No archive directory exists at {delete_path}.  Skipping unpacked delete. "
                )
        return no_errors

    def symlink_install_data(
        self, archive_tuples: list[tuple[str, str, str, str, str]]
    ) -> bool:
        """Create symlinks from install_data locations to the pantry data directory."""
        self.logger.info("Creating symlinks for install_data locations.")
        for archive_tuple in archive_tuples:
            install_data_path = utils.resolve_vars(archive_tuple[4], dict(os.environ))
            symlink_path = Path(install_data_path)
            target_path = self.data_path  # / archive_tuple[3]

            if not target_path.exists():
                self.logger.warning(
                    f"Symlink target '{target_path}' does not exist. Skipping."
                )
                continue

            if symlink_path.exists():
                if symlink_path.is_symlink() and os.path.realpath(symlink_path) == str(
                    target_path
                ):
                    self.logger.debug(
                        f"Symlink '{symlink_path}' already exists and points to the correct target."
                    )
                    continue
                else:
                    self.logger.warning(
                        f"Path '{symlink_path}' already exists and is not the expected symlink. Skipping."
                    )
                    continue

            self.logger.info(f"Creating symlink: '{symlink_path}' -> '{target_path}'")
            try:
                symlink_path.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(target_path, symlink_path)
            except Exception as e:
                self.logger.error(f"Failed to create symlink: {e}")
                return False
        return True

    def archive(
        self,
        archive_filepath: Path,
        source_dirpath: Path,
        extract: Optional[str] = None,
    ) -> bool:
        archive_filepath.parent.mkdir(parents=True, exist_ok=True)
        select = extract if extract is not None else source_dirpath.name
        cmd = f"tar -acf {archive_filepath} {select}"
        cwd = source_dirpath if extract is not None else source_dirpath.parent
        result = self.env_manager.wrangler_run(
            cmd, cwd=cwd, check=False, timeout=ARCHIVE_TIMEOUT
        )
        return self.env_manager.handle_result(
            result,
            f"Failed to pack {source_dirpath} into {archive_filepath}:\n",
            f"Packed {source_dirpath} into {archive_filepath}",
        )

    def unarchive(
        self,
        archive_filepath: Path,
        destination_dirpath: Path,
        extract: Optional[str] = None,
    ) -> bool:
        self.logger.debug(f"Unarchiving {archive_filepath} {destination_dirpath} {extract}.")
        destination_dirpath = destination_dirpath.resolve()
        destination_dirpath.mkdir(parents=True, exist_ok=True)
        select = extract if extract is not None else ""
        cmd = f"tar -axf {archive_filepath} {select}"
        cwd = destination_dirpath
        result = self.env_manager.wrangler_run(
            cmd, cwd=cwd, check=False, timeout=ARCHIVE_TIMEOUT
        )
        return self.env_manager.handle_result(
            result,
            f"Failed to unpack {archive_filepath} into {cwd}:\n",
            f"Unpacked {archive_filepath} into {cwd}",
        )

    def unpack_environment(
        self, env_name: str, moniker: str, archive_format: str
    ) -> bool:
        return self.unarchive(
            self.env_archive_path(moniker, archive_format),
            self.env_manager.mm_envs_dir(env_name),
            extract=env_name,
        )

    def pack_wrangler(self, archive_filepath: Path | str) -> bool:
        archive_path = Path(archive_filepath)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        return self.archive(archive_path, self.env_manager.nbw_root_dir)

    def unpack_wrangler(self, archive_filepath: Path | str) -> bool:
        archive_path = Path(archive_filepath)
        return self.unarchive(archive_path, self.env_manager.nbw_root_dir)

    def pack_environment(
        self, env_name: str, moniker: str, archive_format: str
    ) -> bool:
        return self.archive(
            self.env_archive_path(moniker, archive_format),
            self.env_manager.env_live_path(env_name),
        )


class NbwCan:
    """
    Represents a can (environment) within a shelf.

    A can is typically a tarball containing an environment, and may include notebooks and data.
    This class may provide methods to interact with the environment contained in the can.
    """
