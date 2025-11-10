"""Utility functions for nb-wrangler."""

import os
import io
import re
import urllib.parse
from typing import Optional
import datetime
import functools
import hashlib
import time
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests
import boto3  # type: ignore
from botocore.exceptions import NoCredentialsError, PartialCredentialsError  # type: ignore
from ruamel.yaml import YAML, scalarstring  # type: ignore[import]
from ruamel.yaml import YAMLError  # noqa: F401

# from . import config


# NOTE: to keep this module easily importable everywhere in our code, avoid nb_wrangler imports

# --------------------------- YAML helpers to isolate ruamel.yaml details -------------------


def get_yaml() -> YAML:
    """Return configured ruamel.yaml instance. A chief goal here is that whatever
    format we pick, it should (a) round trip well and (b) be as readable as possible.
    To that end, spec order should be preserved, and support for cleanly formatted
    multi-line strings should be as easy as possible. Wranglers should be able to look
    at git diffs and clearly understand what is *really* changing
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def yaml_dumps(obj) -> str:
    """Convert an object, e.g. a wrangler spec, to our YAML format."""
    with io.StringIO() as string_stream:
        get_yaml().dump(obj, string_stream)
        return string_stream.getvalue()


def yaml_block(s):
    """Use this to ensure a multiline string is rendered as a block in YAML."""
    return scalarstring.LiteralScalarString(s)


# -----------------------------------------------------------------------------


def remove_common_prefix(strings: list[str]) -> list[str]:
    """Remove common prefix from a list of strings."""
    if not strings:
        return []

    # Find the shortest string to avoid index out of range
    shortest = min(strings, key=len)
    prefix_length = 0

    for i in range(len(shortest)):
        if all(s.startswith(shortest[: i + 1]) for s in strings):
            prefix_length = i + 1
        else:
            break

    # Remove the common prefix
    return [s[prefix_length:] for s in strings]


def create_divider(title: str, char: str = "*", width: int = 100) -> str:
    """Create a divider string with centered title."""
    return f" {title} ".center(width, char) + "\n"


def elapsed_time(start_time: datetime.datetime) -> tuple[datetime.datetime, str]:
    """Returns a string representing the elapsed time between the `start_time`
    and current time.
    """
    now = datetime.datetime.now()
    delta = now - start_time
    total_seconds = int(delta.total_seconds())
    days = delta.days
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    microseconds = delta.microseconds
    if days:
        return (
            now,
            f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}.{microseconds/1000:03d}",
        )
    else:
        return (
            now,
            f"{hours:02d}:{minutes:02d}:{seconds:02d}.{microseconds//1000:03d}",
        )


def hex_time():
    return hex(int(time.time())).replace("0x", "")


# -------------------------------------------------------------------------


class DataHandlingError(RuntimeError):
    """There was an error validating or retrieving some form of remote data."""


class DataIntegrityError(DataHandlingError):
    """Two different perspectives on the same data did not match, e.g. recorded size != current download size."""


class DataDownloadError(DataHandlingError):
    """Something went wrong with downloading a data item, most likely authentication or actual transfer."""


def robust_get(url: str, cwd: str = ".", timeout: int = 30) -> Path:
    """More tolerant GET for recalitrant Box links wget can handle."""
    filepath = Path(cwd) / os.path.basename(url)

    # wget does not overwrite existing files,  it adds .N to the name.
    if filepath.exists():
        filepath.unlink()

    try:
        # Using wget instead of native code due to recalitrant Box links wget can handle
        # Two levels of timeout:  wget and subprocess.run.  Output direct to terminal.
        subprocess.run(
            ["wget", "--timeout", str(timeout), url], timeout=timeout + 5, cwd=cwd
        )
    except Exception as e:
        # On failures, poor-man's method for now is to "delete it all".
        if filepath.exists():
            filepath.unlink()
        raise DataDownloadError(f"Failed downloading '{url}'.") from e

    return filepath


def uri_to_local_path(uri: str, timeout: int = 30) -> Optional[str]:
    """Convert URI to local path if possible. Perform any required
    downloads based on the URI, nominally: none, HTTP, HTTPS, or S3.

    For S3,  you must already have any required AWS credentials.

    Currently intended for small quick downloads only due to lack of
    chunking and/or parallelism.

    Return the local path.
    """
    # Check for file:// URI
    if uri.startswith("file://"):
        # Parse the URI
        parsed_uri = urllib.parse.urlparse(uri)
        path = parsed_uri.path
        # Handle Windows paths by replacing forward slashes with backslashes
        # This is a simplified approach and might not handle all cases correctly
        local_path = os.path.normpath(path)
        return local_path

    # Check for HTTP or HTTPS URI
    elif uri.startswith("http://") or uri.startswith("https://"):
        try:
            response = requests.get(uri, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            # Generate a filename from the last element of the URI
            filename = os.path.basename(uri)
            with open(filename, "w+") as f:
                f.write(response.text)
            return filename
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            return None

    # Check for S3 URI
    elif uri.startswith("s3://"):  # XXXX untested
        try:
            # Parse the S3 URI
            parsed_uri = urllib.parse.urlparse(uri)
            bucket_name = parsed_uri.netloc
            object_key = parsed_uri.path.lstrip("/")

            # Create a boto3 S3 client
            s3_client = boto3.client("s3")

            # Download the object from S3
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            data = response["Body"].read().decode("utf-8")  # type: ignore[index]

            # Generate a filename from the last element of the URI
            filename = os.path.basename(object_key)
            with open(filename, "w+") as f:
                f.write(data)
            return filename
        except (NoCredentialsError, PartialCredentialsError) as e:
            print(f"AWS credentials error: {e}")
            return None
        except Exception as e:
            print(f"Error downloading from S3: {e}")
            return None

    # If URI doesn't match any of the supported types
    else:
        # Check if it's a relative or absolute local path
        if os.path.exists(uri):
            return os.path.abspath(uri)
        else:
            return None


@dataclass
class HeadInfo:
    size: int
    etag: str
    last_modified: str

    def todict(self):
        return dict(self.__dict__)


def get_head_info(url: str, timeout: int = 30) -> HeadInfo:
    """Return (size, etag, last-modified) for a URL based on HTTP HEAD,
    nominally for a data file.
    """
    response = requests.head(url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    d = dict(response.headers.items())
    return HeadInfo(int(d["content-length"]), d["etag"], d["last-modified"])


# -------------------------------------------------------------------------


def once(func):
    """
    A decorator that ensures a function is executed only once.
    Subsequent calls return the cached result.
    """
    _has_run = False
    _result = None

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal _has_run, _result
        if not _has_run:
            _result = func(*args, **kwargs)
            _has_run = True
        return _result

    return wrapper


# -------------------------------------------------------------------------


def files_to_map(files: list[str]) -> dict[str, list[str]]:
    """
    Takes a list of file paths and returns a mapping from each
    file to a list of the lines in the file, nominally these are
    requirements files and the packages they request be installed.
    """
    mapping = dict()
    for f in files:
        with open(f) as opened:
            lines = opened.read().splitlines()
            lines = [line.strip() for line in lines]
        mapping[f] = lines
    return mapping


# ------------------------------- sha256 helpers -------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(filepath) -> str:
    """This is for multi-M or multi-G data tarballs..."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash string value in blocks
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def sha256_verify_file(filepath: str, expected_hash: str) -> bool:
    with open(filepath, "rb") as opened:
        return sha256_bytes(opened.read()) == expected_hash


def sha256_verify_data(data: bytes, expected_hash: str) -> bool:
    return sha256_bytes(data) == expected_hash


def sha256_verify_str(text: str, expected_hash: str) -> bool:
    return sha256_str(text) == expected_hash


# -------------------- clear dir w/o deleting it -------------------------


def clear_directory(directory_path):
    """
    Remove all contents of the specified directory recursively,
    but do not remove the directory itself. Not removing the directory
    is critical for clearing caches which have been implemented in Docker
    effectively as root-owned file system mounts which cannot be deleted.

    Args:
        directory_path (str): Path to the directory to clear

    Raises:
        OSError: If the directory doesn't exist or there are permission issues
    """
    # Check if directory exists
    if not os.path.exists(directory_path):
        raise OSError(f"Directory '{directory_path}' does not exist")

    # Iterate through all items in the directory
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)

        # Remove file or directory recursively
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.unlink(item_path)  # Remove file or symbolic link
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)  # Remove directory and all its contents


def resolve_vars(template: str, mapping: dict[str, str]) -> str:
    """
    Resolve a `template` into a fully resolved string by replacing variable
    references in the `template` with the corresponding values for them found in
    `mapping`.  This is nominally used to resolve abstract file system paths in
    various specs using a combination of os.environ and CLI overrides.

    env = {"HOME": "/home/user", "USER": "alice"}
    config_string = "The path is $HOME/project/${USER}"
    resolved = resolve_vars(config_string, env)
    resolved = "The path is /home/user/project/alice"

    Supports $, ${}, and {} variable references.

    returns (fully resolved template with respect to mapping)
    """
    return re.sub(
        r"\$(\w+)|\${(\w+)}|{(\w+)}",
        lambda m: mapping.get(m.group(1) or m.group(2) or m.group(3), m.group(0)),
        template,
    )


def resolve_env(
    env: dict[str, str], env_dict: dict[str, str] = dict(os.environ)
) -> dict[str, str]:
    """Based on `env_dict` which is nominally os.environ, replace all the variables
    in every value of `env` with their corresponding values found in `env_dict`.
    This essentially maks all absract paths in `env` literal with all variables
    replaced by their current platform and session specific values.
    """
    result = dict(env)
    for key, val in env.items():
        result[key] = resolve_vars(val, env_dict)
    return result
