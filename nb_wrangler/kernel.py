import json
import os
from jupyter_client.kernelspec import KernelSpecManager


def add_env_vars_to_kernelspec(kernel_name, env_vars):
    ksm = KernelSpecManager()
    kernel_spec = ksm.get_kernel_spec(kernel_name)
    kernel_json_path = os.path.join(kernel_spec.resource_dir, "kernel.json")

    # Load the existing kernel.json content
    with open(kernel_json_path, "r") as f:
        kernel_data = json.load(f)

    # Update or add the env field
    if "env" not in kernel_data:
        kernel_data["env"] = {}

    for key, value in env_vars.items():
        kernel_data["env"][key] = value

    # Write changes to kernel.json
    with open(kernel_json_path, "w") as f:
        json.dump(kernel_data, f, indent=2)

    print(f"Updated env vars for kernel '{kernel_name}' in {kernel_json_path}")


# Example usage:
# env_vars_to_add = {"MY_VAR": "my_value", "ANOTHER_VAR": "another_value"}

# Replace 'python3' with your specific kernel name if different
# add_env_vars_to_kernelspec("python3", env_vars_to_add)
