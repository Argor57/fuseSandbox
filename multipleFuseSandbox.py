import subprocess
import os
import sys
import argparse
import signal
import json
import threading

from fuseManager import start_server, send_command
from policyManager import build_bubblewrap_command, create_policy_ini, check_and_create_directory, merge_policies

debug_mode = False
process = None

def signal_handler(sig, frame):
    """Handle termination signals to ensure clean unmounting of FUSE filesystem."""
    global process
    print('Termination signal received')
    if process is not None:
        try:
            process.terminate()
            process.wait()
        except Exception as e:
            print(f"Error terminating process: {e}")
    send_command({'action': 'stop'})
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)



def launch_application(app_command, policy_file, default_policy_file, username, mount_dir):
    """Launch an application within a Bubblewrap sandbox with FUSE filesystem mounted."""
    global debug_mode, process

    try:
        # Extract policy data from the JSON file
        with open(policy_file, 'r') as json_file:
            incomplete_policy = json.load(json_file)

        # Extract default policy data
        with open(default_policy_file, 'r') as json_file:
            default_policy = json.load(json_file)

        # Merge policies
        policy_data = merge_policies(incomplete_policy, default_policy)

        # Replace placeholder with the actual and username
        policy_data = json.loads(json.dumps(policy_data).replace("{username}", username))

        # Create the policy INI file
        policy_ini_path = create_policy_ini(policy_file, mount_dir, debug_mode, "multi")

        # Extract the policy name and create the new mount directory path
        policy_name = os.path.basename(policy_file)
        policy_name = policy_name.replace('.json', '').replace('-policy', '')

        mount_point = mount_dir + "/" + policy_name

        # Check and create the mount directory and necessary paths
        check_and_create_directory(mount_point, policy_data, username)

        # Build the Bubblewrap command from the policy
        bwrap_command = build_bubblewrap_command(policy_data, app_command, mount_point)

        # Setup the FUSE filesystem using infuser.py
        if send_command(
                {'action': 'start', 'mountpoint': mount_dir, 'dir_to_mount': mount_dir, 'policy_dict': policy_ini_path,
                 'debug_mode': debug_mode}):
            print("FUSE filesystem started or already running")
        else:
            print("Failed to start FUSE filesystem")
            return

        # Run the application in the sandbox
        if debug_mode:
            print(f"Starting application {app_command} in a sandbox...")
            print(f"Bubblewrap command: {' '.join(bwrap_command)}")
        process = subprocess.Popen(bwrap_command)
        process.wait()
    except Exception as e:
        if debug_mode:
            print(f"[ERROR] An error occurred: {e}")
    finally:
        process = None
        # Notify server to decrement the counter
        send_command({'action': 'stop'})


def main():
    """Main function to parse arguments and launch the application."""
    global debug_mode
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description="Run an application in Bubblewrap with FUSE filesystem")
    parser.add_argument("app_command", type=str, help="Command to start the application")
    parser.add_argument("policy_file", type=str, help="Policy file for the FUSE filesystem",
                        default="./policies/default_policy.json")
    parser.add_argument("mount_dir", type=str, help="Directory for the FUSE mount point")
    parser.add_argument("--username", type=str, required=True, help="Username to run the application as")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--default_policy_file", type=str, help="Default policy file path",
                        default="./policies/default_policy.json")

    global args
    args = parser.parse_args()

    debug_mode = args.debug
    app_command = args.app_command.split()

    # Start the server if not already running
    if not os.path.exists('/tmp/fuse_server_socket'):
        server_thread = threading.Thread(target=start_server)
        server_thread.start()

    launch_application(app_command, args.policy_file, args.default_policy_file, args.username, args.mount_dir)


if __name__ == '__main__':
    main()
