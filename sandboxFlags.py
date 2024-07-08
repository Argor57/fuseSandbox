import os
import json

counter_file = '/tmp/fuse_app_counter.json'

def ensure_counter_file_exists():
    """Ensure the counter file exists, and create it if it does not."""
    if not os.path.exists(counter_file):
        with open(counter_file, 'w') as f:
            json.dump({'counter': 0}, f)

def increment_counter():
    """Increment the counter for the number of applications using the FUSE filesystem."""
    ensure_counter_file_exists()
    counter = read_counter()
    counter += 1
    write_counter(counter)

def decrement_counter():
    """Decrement the counter for the number of applications using the FUSE filesystem."""
    ensure_counter_file_exists()
    counter = read_counter()
    if counter > 0:
        counter -= 1
    write_counter(counter)

def read_counter():
    """Read the current counter value from the file."""
    ensure_counter_file_exists()
    with open(counter_file, 'r') as f:
        data = json.load(f)
    return data.get('counter', 0)

def write_counter(counter):
    """Write the current counter value to the file."""
    with open(counter_file, 'w') as f:
        json.dump({'counter': counter}, f)

def check_other_apps_running():
    """Check if other applications are still using the FUSE filesystem."""
    return read_counter() > 1
