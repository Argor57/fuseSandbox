import argparse
import os
import signal
import subprocess
import sys
import json
import logging
from fuseManager import mount_fuse_filesystem, unmount_fuse_filesystem, is_fuse_mounted
from policyManager import build_bubblewrap_command, check_and_create_directory, merge_policies

logging.basicConfig(level=logging.DEBUG)

debug_mode = False
process = None
mount_dir = None

def signal_handler(sig, frame):
    """Handle termination signals to ensure clean unmounting of FUSE filesystem."""
    global process, mount_dir
    logging.info('Termination signal received')
    if process:
        process.terminate()
        process.wait()
    if mount_dir and is_fuse_mounted(mount_dir):
        logging.info(f"Unmounting FUSE filesystem from {mount_dir}")
        unmount_fuse_filesystem(mount_dir)
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

        # Check and create the mount directory and necessary paths
        logging.info(f"Checking and creating mount directory: {mount_dir}")
        check_and_create_directory(mount_dir, policy_data, username)

        # Check if a FUSE filesystem is already mounted and unmount it if necessary
        if is_fuse_mounted(mount_dir):
            logging.info(f"A FUSE filesystem is already mounted at {mount_dir}. Unmounting it first.")
            unmount_fuse_filesystem(mount_dir)

        # Setup the FUSE filesystem
        logging.info(f"Mounting FUSE filesystem at {mount_dir}")
        fuse_thread = mount_fuse_filesystem(mount_dir, False)

        # Build the Bubblewrap command from the policy
        logging.info("Building Bubblewrap command")
        bwrap_command = build_bubblewrap_command(policy_data, app_command.split(), mount_dir)

        # Run the application in the sandbox
        if debug_mode:
            logging.debug(f"Starting application {app_command} in a sandbox...")
            logging.debug(f"Bubblewrap command: {' '.join(bwrap_command)}")
        process = subprocess.Popen(bwrap_command)
        process.wait()
    except FileNotFoundError as e:
        logging.error(f"[ERROR] Policy file not found: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"[ERROR] JSON decode error in policy file: {e}")
    except Exception as e:
        logging.error(f"[ERROR] An error occurred: {e}")
    finally:
        if mount_dir and is_fuse_mounted(mount_dir):
            logging.info(f"Unmounting FUSE filesystem from {mount_dir}")
            unmount_fuse_filesystem(mount_dir)
        process = None

def main():
    """Main function to parse arguments and launch the application."""
    global debug_mode, mount_dir
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description="Run an application in Bubblewrap with FUSE filesystem")
    parser.add_argument("-a", "--app_command", type=str, help="Command to start the application", required=True)
    parser.add_argument("-p", "--policy_file", type=str, help="Policy file",
                        default="./policies/default_policy.json")
    parser.add_argument("-m", "--mount_dir", type=str, help="Directory for the FUSE mount point", required=True)
    parser.add_argument("-u", "--username", type=str, required=True, help="Username to run the application as")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--default_policy_file", type=str, help="Default policy file path",
                        default="./policies/default_policy.json")

    args = parser.parse_args()

    # Extracted variables from argparse arguments
    app_command = args.app_command
    policy_file = args.policy_file
    mount_dir = args.mount_dir
    username = args.username
    default_policy_file = args.default_policy_file
    debug_mode = args.debug

    launch_application(app_command, policy_file, default_policy_file, username, mount_dir)

if __name__ == '__main__':
    main()

