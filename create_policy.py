import os
import subprocess
import json

def monitor_application(app_command):
    """Monitor the application using strace to capture system calls."""
    try:
        # Run the application with strace to capture file and network accesses
        strace_output = subprocess.check_output(
            ['strace', '-f', '-e', 'trace=file,network', '-o', '/tmp/strace_output.txt'] + app_command.split(),
            stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running strace: {e.output.decode()}")
        return None

    return '/tmp/strace_output.txt'

def analyze_strace_output(strace_file):
    """Analyze the strace output to determine necessary bindings and network access."""
    bindings = set()
    network_access = False

    with open(strace_file, 'r') as f:
        for line in f:
            if 'openat(' in line or 'access(' in line:
                # Extract the file path
                path = line.split('"')[1]
                if path.startswith('/'):
                    bindings.add(path)
            elif 'socket(' in line or 'connect(' in line:
                network_access = True

    return bindings, network_access

def generate_policy_file(app_name, bindings, network_access):
    """Generate a policy file based on the analyzed bindings and network access."""
    policy = {
        "allow_network": network_access,
        "readable_paths": [],
        "writable_paths": [],
        "executable_paths": [],
        "restricted_paths": []
    }

    # Determine readable, writable, and executable paths
    for path in bindings:
        if os.access(path, os.R_OK):
            policy["readable_paths"].append(path)
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

    print("Monitoring application...")
    strace_file = monitor_application(app_command)
    if strace_file is None:
        return

    print("Analyzing strace output...")
    bindings, network_access = analyze_strace_output(strace_file)

    print("Generating policy file...")
    generate_policy_file(app_name, bindings, network_access)

if __name__ == '__main__':
    main()
