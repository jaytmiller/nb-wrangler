"""Utility functions for nb-curator."""

import os
import urllib.parse
from typing import Optional, List

import requests
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

from ruamel.yaml import YAML


def get_yaml() -> YAML:
    """Return configured ruamel.yaml instance."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def remove_common_prefix(strings: List[str]) -> List[str]:
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


def uri_to_local_path(uri: str, timeout: int = 30) -> Optional[str]:
    """Convert URI to local path if possible. Perform any required
    downloads based on the URI, nominally: none, HTTP, HTTPS, or S3.
    
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

            # Generate a filename from the last element of the URI
            filename = os.path.basename(object_key)
            with open(filename, "w+") as f:
                f.write(response.text)
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

    