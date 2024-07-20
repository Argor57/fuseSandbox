#!/bin/bash

# Function to get the username of the user who invoked sudo
get_username() {
    if [ "$SUDO_USER" ]; then
        echo "$SUDO_USER"
    else
        echo "$(whoami)"
    fi
}

# Set variables
USERNAME=$(get_username)
CURRENT_DIR=$(pwd)
TARGET_DIR="/home/${USERNAME}/fuseSandbox"
DESKTOP_DIR="/home/${USERNAME}/Desktop"

# Update package list and upgrade all packages
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y python3 python3-pip fuse bzip2 strace bubblewrap

# Install Python packages
pip3 install fusepy python-magic

# Create necessary directories with the correct ownership
if [ -d "${TARGET_DIR}" ]; then
    sudo cp -r "${CURRENT_DIR}/." "${TARGET_DIR}/"
else
    sudo mkdir -p "${TARGET_DIR}"
    sudo mv "${CURRENT_DIR}"/* "${TARGET_DIR}/"
fi
sudo chown -R ${USERNAME}:${USERNAME} "${TARGET_DIR}"

# Create a desktop entry for the create_desktop_entry.py script on the user's desktop
cat <<EOL | sudo tee ${DESKTOP_DIR}/create_desktop_entry.desktop
[Desktop Entry]
Version=1.0
Name=Create Desktop Entry
Comment=Create a desktop entry for an application to run with fuseSandbox
Exec=gnome-terminal -- bash -c "python3 ${TARGET_DIR}/create_desktop_entry.py"
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Utility;
EOL

# Give execute permissions to the desktop entry and change ownership
sudo chmod +x ${DESKTOP_DIR}/create_desktop_entry.desktop
sudo chown ${USERNAME}:${USERNAME} ${DESKTOP_DIR}/create_desktop_entry.desktop

# Print completion message
echo "Installation complete. The fuseSandbox script has been moved to ${TARGET_DIR}."
echo "You can now use the Create Desktop Entry application from your desktop."

# Check if the firefox.desktop file exists and copy it to the applications directory
if [ -f "${CURRENT_DIR}/firefox.desktop" ]; then
    sudo cp "${CURRENT_DIR}/firefox.desktop" /usr/share/applications/
    echo "firefox.desktop has been copied to /usr/share/applications/."
    sudo chown ${USERNAME}:${USERNAME} /usr/share/applications/firefox.desktop
else
    echo "firefox.desktop file not found."
fi
