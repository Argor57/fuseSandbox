import os
import json
import subprocess

# Define the path to the default policy file
DEFAULT_POLICY_PATH = os.path.join(os.path.dirname(__file__), 'policies', 'default_policy.json')

def debug_print(message, debug_mode):
    """Print debug messages if debug mode is enabled."""
    if debug_mode:
        print(f"[DEBUG] {message}")

def load_policy(policy_file, debug_mode):
    """Load a policy file and return it as a JSON object."""
    debug_print(f"Laden der Policy-Datei: {policy_file}", debug_mode)
    with open(policy_file, 'r') as f:
        policy = json.load(f)
    debug_print(f"Inhalt der Policy-Datei:\n{json.dumps(policy, indent=2)}", debug_mode)
    return policy

def apply_policy(policy, debug_mode):
    """Apply the given policy by printing the relevant information."""
    if policy.get("allow_network"):
        debug_print("Network access allowed", debug_mode)
    else:
        debug_print("Network access denied", debug_mode)
    
    debug_print(f"Readable paths: {policy.get('readable_paths', [])}", debug_mode)
    debug_print(f"Writable paths: {policy.get('writable_paths', [])}", debug_mode)
    debug_print(f"Executable paths: {policy.get('executable_paths', [])}", debug_mode)
    debug_print(f"Restricted paths: {policy.get('restricted_paths', [])}", debug_mode)
    debug_print(f"Bubblewrap parameters: {policy.get('bubblewrap_params', [])}", debug_mode)

def unmount_fuse(fuse_mountpoint, debug_mode):
    """Unmount the FUSE filesystem."""
    if fuse_mountpoint:
        debug_print(f"Unmounting FUSE filesystem from {fuse_mountpoint}", debug_mode)
        subprocess.run(['fusermount', '-u', fuse_mountpoint])
        print(f"Unmounted FUSE filesystem from {fuse_mountpoint}")

def setup_fuse(fuse_mountpoint, fuse_command, debug_mode):
    """Setup the FUSE filesystem."""
    if not os.path.ismount(fuse_mountpoint):
        debug_print(f"Erstellen des FUSE-Mountpoints: {fuse_mountpoint}", debug_mode)
        os.makedirs(fuse_mountpoint, exist_ok=True)
        debug_print(f"Starten des FUSE-Dateisystems mit dem Befehl: {fuse_command}", debug_mode)
        subprocess.Popen(fuse_command.split() + [fuse_mountpoint])

def create_policy_ini(json_policy_path, ini_policy_path):
    # Read the JSON policy file
    with open(json_policy_path, 'r') as file:
        policies = json.load(file)
    
    # Create a ConfigParser object
    config = configparser.ConfigParser()
    
    # Populate the ConfigParser object with the policies
    for operation, rules in policies.items():
        config[operation] = {rule['pattern']: rule['action'] for rule in rules}
    
    # Write the policies to the .ini file
    with open(ini_policy_path, 'w') as configfile:
        config.write(configfile)

    return ini_policy_path

#def is_action_allowed(action, policy):
#    """Check if a specific action is allowed based on the policy."""
#    if action in policy.get('allowed_actions', []):
#        return True
#    elif action in policy.get('denied_actions', []):
#        return False
#    else:
#        return None

