import os


_latest_modified_timestamp = None


def _get_latest_modified_timestamp():
    global _latest_modified_timestamp

    if _latest_modified_timestamp is not None:
        return _latest_modified_timestamp

    # walk the files in the directory and get the file modified time
    latest_timestamp = 0
    for root, dirs, files in os.walk("."):
        for file in files:
            file_path = os.path.join(root, file)
            file_modified_time = os.path.getmtime(file_path)
            if file_modified_time > latest_timestamp:
                latest_timestamp = file_modified_time

    _latest_modified_timestamp = latest_timestamp
    return latest_timestamp
