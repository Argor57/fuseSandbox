import socket
import threading
import json
import os
import subprocess
import sys
from fuse_scripts import infuser
import logging
import time

SOCKET_PATH = '/tmp/fuse_manager_socket'
counter = 0
fuse_thread = None
mountpoint = None
policy_dict = None
debug_mode = False

def mount_fuse_filesystem(mountpoint, dir_to_mount, policy_dict, uri_file, state_file, debug_mode):
    """
    Mount the FUSE filesystem using the infuser.py script.
    """
    try:
        fuse_thread = threading.Thread(target=infuser.main, args=(mountpoint, dir_to_mount, policy_dict, uri_file, state_file))
        fuse_thread.start()
        # Wait a few seconds to ensure the FUSE filesystem is mounted
        time.sleep(5)
        return fuse_thread
    except RuntimeError as e:
        log = logging.getLogger("infuser")
        log.critical(f"Error while trying to mount FileSystem: {e}")
        log.critical(f"Check if {dir_to_mount} is maybe still mounted to {mountpoint} and if so, "
                     f"unmount it with the following command:")
        log.critical(f"sudo fusermount -u {mountpoint}")
        sys.exit(0)

def unmount_fuse_filesystem(mountpoint):
    """
    Unmount the FUSE filesystem.
    """
    subprocess.run(["fusermount", "-u", mountpoint])

def handle_client(client_socket):
    global counter, fuse_thread, mountpoint, policy_dict, debug_mode
    try:
        message = client_socket.recv(1024).decode('utf-8')
        command = json.loads(message)

        if command['action'] == 'start':
            counter += 1
            if counter == 1:
                # Start the FUSE filesystem
                mountpoint = command['mountpoint']
                policy_dict = command['policy_dict']
                debug_mode = command['debug_mode']
                fuse_thread = mount_fuse_filesystem(mountpoint, command['dir_to_mount'], policy_dict, 'uri_file.csv', 'state_file.json', debug_mode)
            client_socket.send(b'ACK')

        elif command['action'] == 'stop':
            counter -= 1
            if counter == 0:
                # Stop the FUSE filesystem
                unmount_fuse_filesystem(mountpoint)
                fuse_thread.join()
                fuse_thread = None
            client_socket.send(b'ACK')

    except Exception as e:
        print(f"Error: {e}")
        client_socket.send(b'NACK')

    finally:
        client_socket.close()

def start_server():
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(5)

    print("Fuse Manager Server started")

    while True:
        client_socket, _ = server.accept()
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.start()

def send_command(command):
    """Send a command to the Fuse Manager Server."""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(SOCKET_PATH)
    client.send(json.dumps(command).encode('utf-8'))
    response = client.recv(1024)
    client.close()
    return response == b'ACK'
