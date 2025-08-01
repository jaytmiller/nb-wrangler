"""Utility functions for nb-curator."""

import os
import urllib.parse
from typing import Optional
import datetime
import functools


import requests
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

from ruamel.yaml import YAML, scalarstring


# NOTE: to keep this module easily importable everywhere in our code, avoid nb_curator imports


def get_yaml() -> YAML:
    """Return configured ruamel.yaml instance."""
    yaml = YAML(typ="rtsc")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml

def yaml_block(s):
    return scalarstring.LiteralScalarString(s)


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


def elapsed_time(start_time: datetime.datetime):
    delta = datetime.datetime.now() - start_time
    total_seconds = int(delta.total_seconds())
    days = delta.days
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    microseconds = delta.microseconds
    if days:
        return (
            f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}.{microseconds:06d}"
        )
    else:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{microseconds:06d}"


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
    elif uri.startswith("s3://"):
        try:
            # Parse the S3 URI
            parsed_uri = urllib.parse.urlparse(uri)
            bucket_name = parsed_uri.netloc
            object_key = parsed_uri.path.lstrip("/")

            # Create a boto3 S3 client
            s3_client = boto3.client("s3")

            # Download the object from S3
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            data = response["Body"].read().decode("utf-8")

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


