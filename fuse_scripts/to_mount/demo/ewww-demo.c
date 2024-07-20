#include <stdio.h>
#include <stdlib.h>

int main() {
    const char* logPath = getenv("LOG_PATH");
    if (logPath == NULL) {
        logPath = "/home/vagrant/src/mountpoint/demo/log.txt";
    }

    FILE *f = fopen(logPath, "a");
    if (f == NULL) {
        perror("Error opening logfile");
        return 1;
    }

    fprintf(f, "ewww - Everything is fine\n");
    fclose(f);

    return 0;
}
