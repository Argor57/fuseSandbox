#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    int fileDescriptor;

    if (argc < 3) {
        fprintf(stderr, "Usage: %s <Path to file> <Mode>\n", argv[0]);
        fprintf(stderr, "Modes: read, write, readwrite, append\n");
        return EXIT_FAILURE;
    }

    const char *filePath = argv[1];
    int flags = 0;
    mode_t mode = 0666; // Standard permissions

    if (strcmp(argv[2], "read") == 0) {
        flags = O_RDONLY;
    } else if (strcmp(argv[2], "write") == 0) {
        flags = O_WRONLY | O_CREAT;
    } else if (strcmp(argv[2], "readwrite") == 0) {
        flags = O_RDWR | O_CREAT;
    } else if (strcmp(argv[2], "append") == 0) {
        flags = O_WRONLY | O_APPEND | O_CREAT;
    } else {
        fprintf(stderr, "Invalid mode: %s\n", argv[2]);
        fprintf(stderr, "Modes: read, write, readwrite, append\n");
        return EXIT_FAILURE;
    }

    // Attempt to open the file in the specified mode
    fileDescriptor = open(filePath, flags, mode);
    
    if (fileDescriptor == -1) {
        perror("Error opening file");
        return EXIT_FAILURE;
    }

    // (Optional) Operations with the file...
    
    // Attempt to close the file
    if (close(fileDescriptor) == -1) {
        perror("Error closing file");
        return EXIT_FAILURE;
    }

    printf("File successfully opened/created in mode '%s'\n", argv[2]);
    return EXIT_SUCCESS;
}
