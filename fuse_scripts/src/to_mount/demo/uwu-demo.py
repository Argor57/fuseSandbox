"""
This module contains functions to start a server that listens for incoming
connections on a specified host and port, and handles communication with clients.
The server is then used to make access control decisions.

Created by Stephan Winker on 02/09/2023

Libraries/Modules:

- socket standard library
  - Access to networking functions
- sys standard library
  - Access to command line arguments 
- subprocess standard library
  - Access to run to spawn child processes 

"""

import sys
import socket
import subprocess

def authorize(path: str, mode: str, script_path: str) -> bool:
    """
    Gives or denies authorisation based on custom criteria 
    
    :param path: The path of the object 
    :type path: str
    :param mode: The requested syscall
    :type mode: str 
    :param script_path: The path to a script
    :type script_path: str 
    :return: A boolean that allows or denies access
    :rtype: bool
    .. todo:: [#6] Add serverside logging
    """

    try:
        # Führt das Bash-Skript aus und liest den Rückgabewert
        result = subprocess.run(['bash', script_path], capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running the script: {e}")
        return False


def handle_client_connection(conn: socket.socket, script_path: str):
    """
    Handles communication with a client
    
    :param conn: The connection socket object for the client
    :type conn: socket.socket
    :param script_path: The path to a script
    :type script_path: str 
    """

    #print("Handling incoming connection")
    while True:
        try:
            demand = conn.recv(4096).decode()
            if not demand:
                break

            #print("Received: " + demand)
    
            path, mode = demand.split(",")

            response = demand + "," + str(authorize(path, mode, script_path))

            #print("Sending: " + response)
            conn.send(response.encode())

        except ConnectionResetError as connection_error:
            #print(f"ERROR - Connection reset by peer: {connection_error}")
            break
        except Exception as e:
            #print(f"ERROR - {e}")
            pass

def main():
    """
    Starts a server that listens for incoming connections on a specified host and port
    """
    host = "127.0.0.1"
    port = 2233

    if len(sys.argv) < 2:
        print("Usage: uwu-demo.py [script_path]")
        sys.exit(1)

    script_path = sys.argv[1]
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_socket.bind((host, port))
        server_socket.listen()

        while True:
            try:
                conn, address = server_socket.accept()
                #print("Connection from: ", str(address))
                handle_client_connection(conn, script_path)

            except OSError as socket_error:
                #print("Socket error while accepting connection:", socket_error)
                continue

    except OSError as socket_error:
        print("Socket error while binding server socket:", socket_error)
        server_socket.close()

if __name__ == "__main__":
    main()
