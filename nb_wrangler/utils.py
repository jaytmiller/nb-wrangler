"""Utility functions for nb-wrangler."""

import os
import io
import urllib.parse
from typing import Optional
import datetime
import functools
import hashlib
import time

import requests
import boto3  # type: ignore
from botocore.exceptions import NoCredentialsError, PartialCredentialsError  # type: ignore

from ruamel.yaml import YAML, scalarstring  # type: ignore

# NOTE: to keep this module easily importable everywhere in our code, avoid nb_wrangler imports

# --------------------------- YAML helpers to isolate ruamel.yaml details -------------------


def get_yaml() -> YAML:
    """Return configured ruamel.yaml instance. A chief goal here is that whatever
    format we pick, it should (a) round trip well and (b) be as readable as possible.
    To that end, spec order should be preserved, and support for cleanly formatted
    multi-line strings should be as easy as possible. Curators should be able to look
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


def uri_to_local_path(uri: str, timeout: int = 30) -> Optional[str]:
    """Convert URI to local path if possible. Perform any required
    downloads based on the URI, nominally: none, HTTP, HTTPS, or S3.

    For S3,  you must already have any required AWS credentials.

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
            response = requests.get(uri, timeout=timeout)
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
