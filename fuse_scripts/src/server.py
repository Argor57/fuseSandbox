"""
This module contains functions to start a server that listens for incoming
connections on a specified host and port, and handles communication with clients.
The server is then used to make access control decisions.

Created by Stephan Winker on 02/09/2023

Libraries/Modules:

- socket standard library
  - Access to networking functions

"""

import socket

def authorize(path: str, mode: str, conn: socket.socket) -> bool:
    """
    Gives or denies authorisation based on custom criteria 
    
    :param path: The path of the object 
    :type path: str
    :param mode: The requested syscall
    :type conn: socket.socket
    :return: A boolean that allows or denies access
    :rtype: bool
    .. todo:: [#6] Add serverside logging
    """
    #print("Checking whether authorisation is permitted")
    # Example of a requirement
    return (
      conn.getpeername()[0] in ["127.0.0.1"]                                    # Origin in allowlist 
      and path in ["/foo", "/foo/a", "/foo/b", "/foo2", "/file.txt", "/file.c"] # Path in allowlist
      and mode in ["open", "read", "write", "readdir"]                          # Syscall in allowlist
    )


def handle_client_connection(conn: socket.socket):
    """
    Handles communication with a client
    
    :param conn: The connection socket object for the client
    :type conn: socket.socket
    """

    #print("Handling incoming connection")
    while True:
        try:
            demand = conn.recv(4096).decode()
            if not demand:
                break

            #print("Received: " + demand)
    
            path, mode = demand.split(",")

            response = demand + "," + str(authorize(path, mode, conn))

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

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_socket.bind((host, port))
        server_socket.listen()

        while True:
            try:
                conn, address = server_socket.accept()
                #print("Connection from: ", str(address))
                handle_client_connection(conn)

            except OSError as socket_error:
                #print("Socket error while accepting connection:", socket_error)
                continue

    except OSError as socket_error:
        print("Socket error while binding server socket:", socket_error)
        server_socket.close()

if __name__ == "__main__":
    main()
