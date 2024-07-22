import threading
import os
import logging
import time
import argparse
import signal
import subprocess
from fuse import FUSE
from fileOperations import FileOperations

logging.basicConfig(level=logging.DEBUG)

COUNTER_FILE = '/tmp/fuse_manager_counter'
fuse_thread = None
mountpoint = None
debug_mode = False

def is_fuse_mounted(mountpoint):
    return os.path.ismount(mountpoint) if mountpoint else False

def run_fuse(mountpoint, debug_mode):
    logging.info(f"Running FUSE with mountpoint: {mountpoint} and debug mode: {debug_mode}")
    FUSE(FileOperations(mountpoint), mountpoint, foreground=True, nonempty=True)

def mount_fuse_filesystem(mountpoint, debug_mode):
    global fuse_thread
    fuse_thread = threading.Thread(target=run_fuse, args=(mountpoint, debug_mode))
    fuse_thread.start()

def unmount_fuse_filesystem(mountpoint):
    if is_fuse_mounted(mountpoint):
        logging.info(f'Unmounting {mountpoint}')
        os.system(f'fusermount -u {mountpoint}')

def kill_fuse_processes():
    logging.info('Killing FUSE processes')
    result = subprocess.run(['pgrep', '-f', 'fuseManager.py'], stdout=subprocess.PIPE)
    pids = result.stdout.decode().split()
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except Exception as e:
            logging.error(f"Failed to kill process {pid}: {e}")

def signal_handler(sig, frame):
    """Handle termination signals to ensure clean unmounting of FUSE filesystem."""
    global mountpoint
    logging.info('Termination signal received. Unmounting FUSE filesystem and killing processes.')
    if mountpoint:
        unmount_fuse_filesystem(mountpoint)
    kill_fuse_processes()
    sys.exit(0)

def read_counter():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r') as file:
            return int(file.read().strip())
    return 0

def write_counter(value):
    with open(COUNTER_FILE, 'w') as file:
        file.write(str(value))

def increment_counter():
    counter = read_counter()
    counter += 1
    write_counter(counter)
    return counter

def decrement_counter():
    counter = read_counter()
    counter -= 1
    write_counter(counter)
    return counter

def manage_fuse(mountpoint, debug_mode):
    global fuse_thread
    if increment_counter() == 1:
        mount_fuse_filesystem(mountpoint, debug_mode)
    while read_counter() > 0:
        time.sleep(1)
    unmount_fuse_filesystem(mountpoint)

def main():
    global mountpoint, debug_mode

    parser = argparse.ArgumentParser(description="Run FUSE filesystem")
    parser.add_argument("--mountpoint", type=str, required=True, help="Directory for the FUSE mount point")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--action", type=str, choices=["start", "stop"], required=True, help="Action to perform")

    args = parser.parse_args()

    mountpoint = args.mountpoint
    debug_mode = args.debug

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.action == "start":
        manage_fuse(mountpoint, debug_mode)
    elif args.action == "stop":
        if decrement_counter() == 0:
            if fuse_thread:
                fuse_thread.join()
                fuse_thread = None

if __name__ == '__main__':
    main()

