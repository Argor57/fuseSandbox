import subprocess
import os
import sys
import argparse
import signal
import json
import threading
import logging
import time
from policyManager import build_bubblewrap_command, create_policy_ini, check_and_create_directory, merge_policies
from fuseManager import increment_counter, decrement_counter, mount_fuse_filesystem, unmount_fuse_filesystem, read_counter

logging.basicConfig(level=logging.DEBUG)

debug_mode = False
process = None
COUNTER_FILE = '/tmp/fuse_manager_counter'

def signal_handler(sig, frame):
    """Handle termination signals to ensure clean unmounting of FUSE filesystem."""
    global process
    logging.info('Termination signal received')
    if process is not None:
        try:
            process.terminate()
            process.wait()
        except Exception as e:
            logging.error(f"Error terminating process: {e}")
    if decrement_counter() == 0:
        unmount_fuse_filesystem(mountpoint)
    sys.exit(0)

def launch_application(app_command, policy_file, default_policy_file, username, mount_dir):
    """Launch an application within a Bubblewrap sandbox with FUSE filesystem mounted."""
    global debug_mode, process

    try:
        # Extract policy data from the JSON file
        logging.info(f"Loading policy file: {policy_file}")
        with open(policy_file, 'r') as json_file:
            incomplete_policy = json.load(json_file)

        # Extract default policy data
        logging.info(f"Loading default policy file: {default_policy_file}")
        with open(default_policy_file, 'r') as json_file:
            default_policy = json.load(json_file)

        # Merge policies
        logging.info("Merging policies")
        policy_data = merge_policies(incomplete_policy, default_policy)

        # Replace placeholder with the actual username
        policy_data = json.loads(json.dumps(policy_data).replace("{username}", username))

        # Create the policy INI file
        policy_ini_path = create_policy_ini(policy_file, mount_dir, debug_mode, "multi")

        # Extract the policy name and create the new mount directory path
        policy_name = os.path.basename(policy_file)
        policy_name = policy_name.replace('.json', '').replace('-policy', '')

        mount_point = os.path.join(mount_dir, policy_name)

        # Check and create the mount directory and necessary paths
        logging.info(f"Checking and creating mount directory: {mount_point}")
        check_and_create_directory(mount_point, policy_data, username)

        # Build the Bubblewrap command from the policy
        logging.info("Building Bubblewrap command")
        bwrap_command = build_bubblewrap_command(policy_data, app_command, mount_point)

        # Increment the counter and mount the FUSE filesystem if necessary
        if increment_counter() == 1:
            mount_fuse_filesystem(mount_point, debug_mode)

        # Run the application in the sandbox
        if debug_mode:
            logging.debug(f"Starting application {app_command} in a sandbox...")
            logging.debug(f"Bubblewrap command: {' '.join(bwrap_command)}")
        process = subprocess.Popen(bwrap_command)
        process.wait()
    except Exception as e:
        logging.error(f"[ERROR] An error occurred: {e}")
    finally:
        process = None
        # Decrement the counter and unmount the FUSE filesystem if necessary
        if decrement_counter() == 0:
            unmount_fuse_filesystem(mount_point)

def main():
    global debug_mode

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description="Run an application in Bubblewrap with FUSE filesystem")
    parser.add_argument("-a", "--app_command", type=str, help="Command to start the application")
    parser.add_argument("-p", "--policy_file", type=str, help="Policy file for the FUSE filesystem",
                        default="./policies/default_policy.json")
    parser.add_argument("-m", "--mount_dir", type=str, help="Directory for the FUSE mount point")
    parser.add_argument("-u", "--username", type=str, required=True, help="Username to run the application as")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--default_policy_file", type=str, help="Default policy file path",
                        default="./policies/default_policy.json")

    args = parser.parse_args()

    debug_mode = args.debug
    app_command = args.app_command.split()

    launch_application(app_command, args.policy_file, args.default_policy_file, args.username, args.mount_dir)

if __name__ == '__main__':
    main()

