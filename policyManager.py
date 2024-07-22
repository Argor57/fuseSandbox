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
    bubblewrap_params.extend(["--bind", mount_point, "/"])
    bubblewrap_params.extend([
        "--dev-bind", "/dev", "/dev",
        "--proc", "/proc",
        "--ro-bind", "/sys", "/sys",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/sbin", "/sbin",  # Additional binding
        "--ro-bind", "/etc", "/etc"   # Additional binding
    ])
    readable_paths = policy_data.get('readable_paths', [])
    writable_paths = policy_data.get('writable_paths', [])
    executable_paths = policy_data.get('executable_paths', [])
    rwx_paths = [path for path in writable_paths if path in executable_paths]
    
    for path in rwx_paths:
        executable_paths.remove(path)
    
    for path in readable_paths:
        bubblewrap_params.extend([
            "--ro-bind",
            path.replace("{mount_point}", mount_point),
            path.replace("{mount_point}", mount_point)
        ])
    
    for path in executable_paths:
        bubblewrap_params.extend([
            "--ro-bind",
            path.replace("{mount_point}", mount_point),
            path.replace("{mount_point}", mount_point)
        ])
    
    for path in writable_paths:
        bubblewrap_params.extend([
            "--bind",
            path.replace("{mount_point}", mount_point),
            path.replace("{mount_point}", mount_point)
        ])
    
    for path in rwx_paths:
        bubblewrap_params.extend([
            "--bind",
            path.replace("{mount_point}", mount_point),
            path.replace("{mount_point}", mount_point)
        ])
    
    bubblewrap_params.extend(policy_data.get('bubblewrap_params', []))
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

def check_and_create_directory(mount_point, policy_data, username):
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
        if not os.path.exists(path):
            try:
                os.makedirs(path)
                print(f"Created path: {path}")
            except Exception as e:
                print(f"[ERROR] Could not create path {path}: {e}")
                sys.exit(1)
        else:
            print(f"Path already exists: {path}")

    create_path(mount_point)
    
    for dir_path in essential_dirs:
        full_path = os.path.join(mount_point, dir_path.lstrip('/'))
        create_path(full_path)
    
    for path in policy_data.get('readable_paths', []) + policy_data.get('writable_paths', []) + policy_data.get('executable_paths', []):
        full_path = os.path.join(mount_point, path.lstrip('/'))
        create_path(full_path)

