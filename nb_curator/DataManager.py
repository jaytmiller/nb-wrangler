"""Handles management of data specified in curator spec.

Nominally the curator spec will refer to a list of "data items"
each of which may fit within the following structure:

data:
    - name: <item name>
      path: pantry:// or shelf:// or file://
      uri: Optional, https:// or s3:// to download compressed tarball from
      sha1sum: expected hash for data tarball
      env_var: <name> = <live path of data>
      unpack_to_live: bool
"""

class DataManager:

    def setup_data_item(data_name):
        pass

    def create_data_item(data_name):
        pass

    def add_to_spec():
        pass

    def add_to_shelf(): # needed?
        pass

    def delete_data_setup(data_name):
        pass
