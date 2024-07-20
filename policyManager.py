import os
import json
import subprocess
import configparser


def merge_policies(incomplete_policy, default_policy):
    """Merge an incomplete policy with the default policy."""
    merged_policy = default_policy.copy()
    for key, value in incomplete_policy.items():
        if isinstance(value, dict) and key in merged_policy:
            merged_policy[key] = merge_policies(value, merged_policy[key])
        else:
            merged_policy[key] = value
    return merged_policy


def build_bubblewrap_command(policy_data, app_command):
    """Build the Bubblewrap command from the policy data."""
    bubblewrap_params = policy_data.get('bubblewrap_params', [])

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

    bwrap_command = ['bwrap'] + bubblewrap_params + app_command

    return bwrap_command


def create_policy_ini(policy_json_path, debug_mode):
    """Create a policy.ini file from the policy.json file if it doesn't exist."""
    policy_ini_path = policy_json_path.replace('.json', '.ini')

    if os.path.exists(policy_ini_path):
        return policy_ini_path

    with open(policy_json_path, 'r') as json_file:
        policy_data = json.load(json_file)

    config = configparser.ConfigParser()

    # Derive read, write, and execute sections from paths specified in the JSON policy
    config['read'] = {path: 'allow' for path in policy_data.get('readable_paths', [])}
    config['write'] = {path: 'allow' for path in policy_data.get('writable_paths', [])}
    config['execute'] = {path: 'allow' for path in policy_data.get('executable_paths', [])}

    with open(policy_ini_path, 'w') as configfile:
        config.write(configfile)

    if debug_mode:
        print(f"Created policy INI file at: {policy_ini_path}")

    return policy_ini_path


def check_and_create_directory(mount_point, policy_data, username):
    """Check if the given directory is available for the user who ran the script. Create if it doesn't exist."""
    if not os.path.exists(mount_point):
        try:
            os.makedirs(mount_point)
        except Exception as e:
            print(f"[ERROR] Could not create mount directory {mount_point}: {e}")
            sys.exit(1)

    # Check and create paths specified in the policy
    for path in policy_data.get('readable_paths', []) + policy_data.get('writable_paths', []) + policy_data.get(
            'executable_paths', []):
        full_path = os.path.join(mount_point, path.lstrip('/'))
        if not os.path.exists(full_path):
            try:
                os.makedirs(full_path)
                # Set the ownership to the specified user
                uid = subprocess.check_output(['id', '-u', username]).strip()
                gid = subprocess.check_output(['id', '-g', username]).strip()
                os.chown(full_path, int(uid), int(gid))
            except Exception as e:
                print(f"[ERROR] Could not create path {full_path}: {e}")
                sys.exit(1)
