import os
import getpass

def find_policy_file(policy_name):
    policies_dir = os.path.expanduser("~/fuseSandbox/policies")
    policy_path = os.path.join(policies_dir, f"{policy_name}.json")

    if os.path.exists(policy_path):
        return policy_path
    else:
        print(f"Error: Policy file '{policy_name}.json' not found in {policies_dir}.")
        return None

def create_desktop_file(app_name, policy_name, mount_point, username, debug):
    policy_path = find_policy_file(policy_name)
    if not policy_path:
        return

    desktop_file_path = os.path.expanduser(f"~/.local/share/applications/{app_name}.desktop")
    desktop_symlink_path = os.path.expanduser(f"~/Desktop/{app_name}.desktop")

    if os.path.exists(desktop_file_path) or os.path.exists(desktop_symlink_path):
        print(f"Error: A file with the name '{app_name}.desktop' already exists.")
        return

    desktop_file_content = f"""[Desktop Entry]
Version=1.0
Name={app_name} Default Policy
Comment=Run {app_name} with the default FUSE sandbox policy
Exec=gnome-terminal -- bash -c "python3 /home/{username}/fuseSandbox/fuseSandbox.py '{app_name}' '{policy_path}' '{mount_point}' --username {username} {'--debug' if debug else ''}"
Icon={app_name}
Terminal=true
Type=Application
Categories=Network;WebBrowser;
"""

    # Ensure the directory exists
    os.makedirs(os.path.dirname(desktop_file_path), exist_ok=True)

    # Write the desktop file
    with open(desktop_file_path, 'w') as file:
        file.write(desktop_file_content)

    # Make the desktop file executable
    os.chmod(desktop_file_path, 0o755)

    # Create a symlink on the desktop
    if not os.path.exists(desktop_symlink_path):
        os.symlink(desktop_file_path, desktop_symlink_path)

    print(f"Desktop entry created: {desktop_file_path}")
    print(f"Symlink created on desktop: {desktop_symlink_path}")

def main():
    app_name = input("Enter the name of the application to run (e.g., firefox): ").strip()
    policy_name = input("Enter the name of the policy file (without .json): ").strip()
    mount_point = input(
        "Enter the mount point for the FUSE filesystem (default: ./fuseSandbox/fuse_mount): ").strip() or './fuseSandbox/fuse_mount'
    username = getpass.getuser()
    debug = input("Enable debug mode? (y/N): ").strip().lower() == 'y'

    create_desktop_file(app_name, policy_name, mount_point, username, debug)

if __name__ == '__main__':
    main()
