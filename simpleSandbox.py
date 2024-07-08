import subprocess
import os
import sys
import argparse
import signal
from sharedFunctions import DEFAULT_POLICY_PATH, debug_print, load_policy, apply_policy, unmount_fuse, setup_fuse

fuse_mountpoint = None
debug_mode = False

def signal_handler(sig, frame):
    """Handle termination signals to ensure clean unmounting of FUSE filesystem."""
    print('Termination signal received')
    unmount_fuse(fuse_mountpoint, debug_mode)
    sys.exit(0)

def launch_application(app_command, mountpoint, fuse_command, username):
    """Launch an application within a Bubblewrap sandbox with FUSE filesystem mounted."""
    global fuse_mountpoint
    fuse_mountpoint = mountpoint

    # Load the default policy
    default_policy = load_policy(DEFAULT_POLICY_PATH, debug_mode)

    # Apply the default policy
    apply_policy(default_policy, debug_mode)

    try:
        # Setup the FUSE filesystem
        setup_fuse(fuse_mountpoint, fuse_command, debug_mode)

        # Build the Bubblewrap command from the policy
        bwrap_command = ['sudo', '-u', username, 'bwrap'] + default_policy.get("bubblewrap_params", []) + [
            '--bind', fuse_mountpoint, '/mnt/fuse_mount',
            '--chdir', '/mnt/fuse_mount'
        ] + app_command

        # Run the application in the sandbox
        debug_print(f"Starting application {app_command} in a sandbox...", debug_mode)
        debug_print(f"Bubblewrap command: {' '.join(bwrap_command)}", debug_mode)
        subprocess.run(bwrap_command)
    except Exception as e:
        debug_print(f"[ERROR] An error occurred: {e}", debug_mode)
    finally:
        # This block will run if any exception is raised during the try block
        try:
            unmount_fuse(fuse_mountpoint, debug_mode)
        except Exception as e:
            debug_print(f"[ERROR] Failed to unmount FUSE filesystem: {e}", debug_mode)

def main():
    """Main function to parse arguments and launch the application."""
    global debug_mode
    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description="Run an application in Bubblewrap with FUSE filesystem")
    parser.add_argument("app_command", type=str, help="Command to start the application")
    parser.add_argument("fuse_mountpoint", type=str, help="Mountpoint for the FUSE filesystem")
    parser.add_argument("fuse_command", type=str, help="Command to start the FUSE filesystem")
    parser.add_argument("--username", type=str, required=True, help="Username to run the application as")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Enable debug mode if specified
    debug_mode = args.debug

    # Split the application command into a list
    app_command = args.app_command.split()

    # Launch the application with the given arguments
    launch_application(app_command, args.fuse_mountpoint, args.fuse_command, args.username)

if __name__ == '__main__':
    main()
