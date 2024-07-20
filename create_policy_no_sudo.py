import os
import subprocess
import json
import time
import getpass

"""
Although the Script is called create_policy_no_sudo, you need to be able to install auditd and start it
With apt it looks like this

sudo apt-get install auditd

sudo systemctl start auditd
sudo systemctl enable auditd

Once the service is enabled, this script can be run *without* sudo, which could be better for usability,
but worse for security purposes, need to look into it more
"""
def configure_auditd(app_name):
    """Configure auditd to monitor the application."""
    user = getpass.getuser()
    audit_rules = [
        f"-w /tmp -p rwxa -k {app_name}_monitor",
        f"-w /home/{user} -p rwxa -k {app_name}_monitor",
        f"-a exit,always -F arch=b64 -S connect -S accept -S sendto -S recvfrom -k {app_name}_monitor"
    ]

    with open("/tmp/audit.rules", "w") as f:
        for rule in audit_rules:
            f.write(rule + "\n")

    print("Audit rules configured. Please run the following commands with sudo:")
    print("sudo auditctl -D")
    print("sudo auditctl -R /tmp/audit.rules")


def monitor_application(app_command):
    """Monitor the application using auditd to capture system calls and file accesses."""
    print("Starting application monitoring...")
    audit_log = "/var/log/audit/audit.log"
    initial_size = os.path.getsize(audit_log)

    process = subprocess.Popen(app_command.split())
    process.wait()

    final_size = os.path.getsize(audit_log)
    if final_size > initial_size:
        with open(audit_log, 'r') as f:
            f.seek(initial_size)
            log_data = f.read()

    return log_data


def analyze_audit_log(log_data):
    """Analyze the audit log to determine necessary bindings and network access."""
    bindings = set()
    network_access = False

    for line in log_data.splitlines():
        if "type=PATH" in line and "name=" in line:
            path = line.split("name=")[-1].split(" ")[0]
            if path.startswith('/'):
                bindings.add(path)
        elif "type=SYSCALL" in line and ("connect" in line or "sendto" in line or "recvfrom" in line):
            network_access = True

    return bindings, network_access


def generate_policy_file(app_name, bindings, network_access):
    """Generate a policy file based on the analyzed bindings and network access."""
    policy = {
        "allow_network": network_access,
        "readable_paths": list(bindings),
        "writable_paths": [],
        "executable_paths": [],
        "restricted_paths": [
            "/home",
            "/etc",
            "/usr",
            "/bin"
        ],
        "bubblewrap_params": [
            "--new-session",
            "--dev-bind", "/dev", "/dev",
            "--proc", "/proc",
            "--dir", "/tmp",
            "--bind", "{mount_point}", "/",
            "--chdir", "{mount_point}"
        ]
    }

    # Add writable and executable paths as necessary
    for path in bindings:
        if os.access(path, os.W_OK):
            policy["writable_paths"].append(path)
        if os.access(path, os.X_OK):
            policy["executable_paths"].append(path)

    # Save the policy file
    policy_dir = "./policies"
    os.makedirs(policy_dir, exist_ok=True)
    policy_path = os.path.join(policy_dir, f"{app_name}_policy.json")
    with open(policy_path, 'w') as f:
        json.dump(policy, f, indent=4)

    print(f"Policy file saved at: {policy_path}")


def main():
    app_command = input("Enter the command to run the application (e.g., firefox): ").strip()
    app_name = app_command.split()[0]

    configure_auditd(app_name)

    print("Please run the configured audit rules with sudo as instructed.")
    input("Press Enter to continue after configuring auditd...")

    log_data = monitor_application(app_command)
    if not log_data:
        print("No log data captured.")
        return

    print("Analyzing audit log data...")
    bindings, network_access = analyze_audit_log(log_data)

    print("Generating policy file...")
    generate_policy_file(app_name, bindings, network_access)


if __name__ == '__main__':
    main()
