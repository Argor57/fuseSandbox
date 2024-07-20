#include <stdio.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    // Ensure a filename has been passed as an argument
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <Filename>\n", argv[0]);
        return 1;
    }

    const char *filename = argv[1];

    // Check if the user has read access to the file
    if (access(filename, R_OK) == 0) {
        printf("The user has read access to the file.\n");
    } else {
        perror("Access denied");
    }

    // Check if the user has write access to the file
    if (access(filename, W_OK) == 0) {
        printf("The user has write access to the file.\n");
    } else {
        perror("Access denied");
    }

    // Check if the user has execute access to the file
    if (access(filename, X_OK) == 0) {
        printf("The user has execute access to the file.\n");
    } else {
        perror("Access denied");
    }

    return 0;
}
