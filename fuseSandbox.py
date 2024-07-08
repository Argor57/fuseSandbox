import subprocess
import os
import sys
import argparse
import signal
import json
from sharedFunctions import DEFAULT_POLICY_PATH, debug_print, load_policy, apply_policy, unmount_fuse, setup_fuse
from sandboxFlags import increment_counter, decrement_counter, check_other_apps_running, ensure_counter_file_exists

fuse_mountpoint = None
debug_mode = False

def signal_handler(sig, frame):
    """Handle termination signals to ensure clean unmounting of FUSE filesystem."""
    print('Termination signal received')
    decrement_counter()
    if not check_other_apps_running():
        unmount_fuse(fuse_mountpoint, debug_mode)
        stop_fuse()
    sys.exit(0)

def check_fuse_running(mountpoint):
    """Check if the FUSE filesystem is already running."""
    result = subprocess.run(['mountpoint', '-q', mountpoint])
    return result.returncode == 0

def start_fuse(mountpoint, fuse_command):
    """Start the FUSE filesystem."""
    if not check_fuse_running(mountpoint):
        setup_fuse(mountpoint, fuse_command, debug_mode)
        increment_counter()

def stop_fuse():
    """Stop the FUSE filesystem if no other applications are running."""
    global fuse_mountpoint
    if fuse_mountpoint and not check_other_apps_running():
        unmount_fuse(fuse_mountpoint, debug_mode)

def merge_policies(default_policy, app_policy):
    """Merge the application-specific policy with the default policy."""
    merged_policy = default_policy.copy()
    merged_policy.update(app_policy)
    return merged_policy

# Importing relevant functions from the fuse_scripts and sandbox_scripts
sys.path.append(os.path.join(os.path.dirname(__file__), 'fuse_scripts/src'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'sandbox_scripts'))

from namespace_launcher import setup as setup_uid_gid_maps
# from client import run_application_in_sandbox

def launch_application(app_command, mountpoint, fuse_command, app_policy_file):
    """Launch an application within a Bubblewrap sandbox with FUSE filesystem mounted."""
    global fuse_mountpoint
    fuse_mountpoint = mountpoint

    # Load the default policy
    default_policy = load_policy(DEFAULT_POLICY_PATH, debug_mode)

    # Load the application-specific policy if provided
    if app_policy_file and os.path.exists(app_policy_file):
        app_policy = load_policy(app_policy_file, debug_mode)
    else:
        app_policy = {}

    # Merge the policies
    final_policy = merge_policies(default_policy, app_policy)

    # Apply the combined policy
    apply_policy(final_policy, debug_mode)

    try:
        # Start the FUSE filesystem if not already running
        start_fuse(fuse_mountpoint, fuse_command)

        # Build the Bubblewrap command
        bwrap_command = [
            'bwrap'
        ] + final_policy.get("bubblewrap_params", []) + [
            '--bind', fuse_mountpoint, os.environ['HOME']
        ] + app_command

        # Create pipes for namespace information
        info_pipe = os.pipe()
        blockns_pipe = os.pipe()
        pid = os.fork()
        if pid == 0:
            # Child process
            os.close(info_pipe[0])
            os.close(blockns_pipe[1])

            # Make pipes inheritable
            os.set_inheritable(info_pipe[1], True)
            os.set_inheritable(blockns_pipe[0], True)

            # Add namespace-related options to the Bubblewrap command
            bwrap_command += [
                '--userns-block-fd', '%i' % blockns_pipe[0],
                '--info-fd', '%i' % info_pipe[1]
            ]

            # Execute the application in the sandbox
            debug_print(f"Starting application {app_command} in a sandbox...", debug_mode)
            debug_print(f"Bubblewrap command: {' '.join(bwrap_command)}", debug_mode)

            # Write to info_pipe before executing the command
            child_pid = os.getpid()
            os.write(info_pipe[1], json.dumps({'child-pid': child_pid}).encode())
            os.execvp(bwrap_command[0], bwrap_command)
        else:
            # Parent process
            os.close(info_pipe[1])
            os.close(blockns_pipe[0])
            data = json.load(os.fdopen(info_pipe[0]))
            # Set up UID and GID maps for the child process
            setup_uid_gid_maps(data['child-pid'], os.getuid(), os.getgid())
            os.write(blockns_pipe[1], b'1')

    finally:
        # This block will run if any exception is raised during the try block
        decrement_counter()
        if not check_other_apps_running():
            unmount_fuse(fuse_mountpoint, debug_mode)
            stop_fuse()

def main():
    """Main function to parse arguments and launch the application."""
    global debug_mode
    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description="Run application in Bubblewrap with FUSE filesystem")
    parser.add_argument("app_command", type=str, help="Command to start the application")
    parser.add_argument("fuse_mountpoint", type=str, help="Mountpoint for the FUSE filesystem")
    parser.add_argument("fuse_command", type=str, help="Command to start the FUSE filesystem")
    parser.add_argument("--app_policy_file", type=str, help="Path to the application-specific policy file", default=DEFAULT_POLICY_PATH)
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Enable debug mode if specified
    debug_mode = args.debug

    # Ensure counter file exists
    ensure_counter_file_exists()

    # Split the application command into a list
    app_command = args.app_command.split()
    # Launch the application with the given arguments
    launch_application(app_command, args.fuse_mountpoint, args.fuse_command, args.app_policy_file)

if __name__ == '__main__':
    main()
