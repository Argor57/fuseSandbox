import os
import json
import subprocess
import configparser
import sys


def merge_policies(incomplete_policy, default_policy):
    """Merge an incomplete policy with the default policy."""
    merged_policy = default_policy.copy()
    for key, value in incomplete_policy.items():
        if isinstance(value, dict) and key in merged_policy:
            merged_policy[key] = merge_policies(value, merged_policy[key])
        else:
            merged_policy[key] = value
    return merged_policy


def build_bubblewrap_command(policy_data, app_command, mount_point):
    """Build the Bubblewrap command from the policy data."""
    bubblewrap_params = []
    path_bindings = {}

    # Essential bindings for special directories
    bubblewrap_params.extend([
        "--dev-bind", "/dev", "/dev",
        "--proc", "/proc"
        "--bind", "/tmp", "/tmp"
    ])

    # Create lists for readable, writable, and executable paths
    readable_paths = policy_data.get('readable_paths', [])
    writable_paths = policy_data.get('writable_paths', [])
    executable_paths = policy_data.get('executable_paths', [])

    # Create a list for read-write-execute paths
    rwx_paths = []

    # Compare executable and writable lists
    for path in writable_paths:
        if path in executable_paths:
            rwx_paths.append(path)

    # Remove paths in both readable and executable from readable list
    for path in executable_paths:
        if path in readable_paths:
            readable_paths.remove(path)

    def process_path(path_to_process, binding_type, noexec=False):
        if "{mount_point}" in path_to_process:
            dest_path = path_to_process.replace("{mount_point}", "")
        else:
            dest_path = path_to_process
        bind_processed = [binding_type, path_to_process, dest_path]
        if noexec:
            bind_processed.append("--noexec")
        return bind_processed

    # Generate path bindings
    for path in readable_paths:
        path_bindings[path] = process_path(path, "--ro-bind", noexec=True)

    for path in writable_paths:
        if path not in rwx_paths:
            path_bindings[path] = process_path(path, "--bind", noexec=True)

    for path in executable_paths:
        if path not in rwx_paths:
            path_bindings[path] = process_path(path, "--ro-bind")

    for path in rwx_paths:
        path_bindings[path] = process_path(path, "--bind")

    # Add path bindings to bubblewrap parameters
    for bind in path_bindings.values():
        bubblewrap_params.extend(bind)

    # Check if network access is allowed
    if not policy_data.get('allow_network', False):
        # If network access is not allowed, unshare all namespaces to isolate the network
        bubblewrap_params.append('--unshare-all')
    else:
        # Unshare all namespaces except network
        bubblewrap_params.extend([
            '--unshare-pid',
            '--unshare-uts',
            '--unshare-ipc',
            '--unshare-cgroup',
            '--unshare-user',
            '--unshare-mount'
        ])

    # Add any additional bubblewrap parameters
    bubblewrap_params.extend(policy_data.get('bubblewrap_params', []))

    # Ensure the mount point is properly bound and chdir to it
    bubblewrap_params.extend(["--bind", mount_point, "/", "--chdir", mount_point])

    bwrap_command = ['bwrap'] + bubblewrap_params + app_command

    return bwrap_command


def create_policy_ini(policy_json_path, mount_point, debug_mode, usemode):
    """Create a policy.ini file from the policy.json file if it doesn't exist."""
    if usemode == "single":
        policy_ini_path = policy_json_path.replace('.json', '_single.ini')
    elif usemode == "multi":
        policy_ini_path = policy_json_path.replace('.json', '._multi.ini')
    else:
        policy_ini_path = policy_json_path.replace('.json', '.ini')

    if os.path.exists(policy_ini_path):
        return policy_ini_path

    with open(policy_json_path, 'r') as json_file:
        policy_data = json.load(json_file)

    config = configparser.ConfigParser()

    # Allow access to the mount point and everything within it
    config['read'] = {mount_point: "allow"}
    config['read'] = {mount_point + '.*': "allow"}
    config['write'] = {mount_point: "allow"}
    config['write'] = {mount_point + '.*': "allow"}
    config['execute'] = {mount_point: "allow"}
    config['execute'] = {mount_point + '.*': "allow"}
    with open(policy_ini_path, 'w') as configfile:
        config.write(configfile)

    if debug_mode:
        print(f"Created policy INI file at: {policy_ini_path}")

    return policy_ini_path

def check_and_create_directory(mount_point, policy_data, username):
    """Check if the given directory is available for the user who ran the script. Create if it doesn't exist."""
    essential_dirs = [
        "/tmp",
        "/dev",
        "/proc",
        "/sys",
        "/etc",
        "/usr",
        "/bin",
        "/lib",
        "/lib64",
        "/var",
        "/home",
        "/opt",
        "/run",
        "/srv",
        "/mnt",
        "/media"
    ]

    def create_path(path):
        """Helper function to create a path and set ownership."""
        if not os.path.exists(path):
            try:
                os.makedirs(path)
                # Set the ownership to the specified user
                uid = subprocess.check_output(['id', '-u', username]).strip()
                gid = subprocess.check_output(['id', '-g', username]).strip()
                os.chown(path, int(uid), int(gid))
            except Exception as e:
                print(f"[ERROR] Could not create path {path}: {e}")
                sys.exit(1)

    # Create the mount point directory if it doesn't exist
    create_path(mount_point)

    # Check and create essential system directories
    for dir_path in essential_dirs:
        full_path = os.path.join(mount_point, dir_path.lstrip('/'))
        create_path(full_path)

    # Check and create paths specified in the policy
    for path in policy_data.get('readable_paths', []) + policy_data.get('writable_paths', []) + policy_data.get('executable_paths', []):
        full_path = os.path.join(mount_point, path.lstrip('/'))
        create_path(full_path)
