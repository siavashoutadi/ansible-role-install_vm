#!/usr/bin/python

import os
import subprocess
import urllib
from ansible.module_utils.basic import AnsibleModule

result = dict(
    changed=False
)

def main():
    module_args = dict(
        name=dict(required=True),
        memory=dict(type="int", required=True),
        vcpus=dict(type="int", required=True),
        disk_size=dict(type="int", required=True),
        disk_path=dict(required=True),
        location=dict(required=True),
        disk_format=dict(required=False, default="qcow2", choices=["qcow2", "raw", "vmdk"]),
        graphics=dict(required=False, choices=["spice", "vnc"], default="spice"),
        os_type=dict(required=False, default="linux"),
        os_variant=dict(required=False, default="centos7.0",
                        choices=["rhel7.0", "centos7.0", "ubuntu16.04", "sles12"]),
        virt_type=dict(required=False, default="kvm", choices=["kvm", "qemu"]),
        ks_file=dict(required=False, default=None),
        network=dict(required=False, default="default"),
        bridge=dict(required=False, default="virbr0"),
        use_bridge=dict(type=bool, required=False, default=False),
        recreate=dict(type=bool, required=False, default=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    if create_vm(module):
        module.exit_json(**result)
    else:
        module.fail_json(msg='Error in VM creation!', **result)

def create_vm(module):
    vm_exist = does_vm_exist(module.params["name"])
    recreate = module.params["recreate"]
    if not vm_exist:
        return install(module)
    elif recreate:
        if not remove(module):
            return False
        return install(module)
    else:
        result["Error"] = "VM already exist!"
        result["rc"] = "1"
        return False

def does_vm_exist(name):
    r = run_cli(["virsh", "list", "--all", "--name"])
    for line in r.get("stdout").splitlines():
        if name == line.strip():
            return True
    return False

def install(module):
    location = urllib.unquote(module.params["location"])
    cmd = ["virt-install"]
    cmd += ["--virt-type", module.params["virt_type"]]
    cmd += ["--name", module.params["name"]]
    cmd += ["--memory", str(module.params["memory"])]
    cmd += ["--vcpus", str(module.params["vcpus"])]
    cmd += ["--graphics", module.params["graphics"], "--noautoconsole"]
    cmd += ["--os-type", module.params["os_type"]]
    cmd += ["--os-variant", module.params["os_variant"]]
    disk_arg = get_disk_path(module) + ",size="
    disk_arg += str(module.params["disk_size"])
    disk_arg += ",format={0}".format(module.params["disk_format"])
    cmd += ["--disk", disk_arg]
    if module.params["use_bridge"]:
        cmd += ["--network", "bridge=%s" % module.params["bridge"]]
    else:
        cmd += ["--network", "network=%s" % module.params["network"]]
    cmd += ["--wait", "-1"]
    cmd += ["--autostart"]
    cmd += ["--location", location]

    if module.params["ks_file"]:
        ks_file = urllib.unquote(module.params["ks_file"])
        if ks_file.startswith("http"):
            cmd += ["--extra-args", "'ks={0}'".format(ks_file)]
        else:
            cmd += ["--initrd-inject", ks_file]
            file_name = os.path.basename(ks_file)
            cmd += ["--extra-args", "'ks=file:/{0}'".format(file_name)]
    r = run_cli(cmd, use_shell=True)
    if r.get("rc") != 0:
        log_error(r, "Could not install the VM!", cmd)
        return False
    result["changed"] = True
    result["cmd"] = get_cmd_string(cmd)
    result["msg"] = "VM created successfully"
    return True

def remove(module):
    cmd = ["virsh", "destroy", module.params["name"]]
    r = run_cli(cmd)
    if r.get("rc") != 0:
        log_error(r, "Could not poweroff the VM!", cmd)
        return False
    result["changed"] = True
    cmd = ["virsh", "undefine", module.params["name"]]
    r = run_cli(cmd)
    if r.get("rc") != 0:
        log_error(r, "Could not remove the VM!", cmd)
        return False
    cmd = ["virsh", "vol-delete", get_disk_path(module)]
    r = run_cli(cmd)
    if r.get("rc") != 0:
        log_error(r, "Could not remove the disk image!", cmd)
        return False
    return True

def get_disk_path(module):
    return urllib.unquote(module.params["disk_path"])

def run_cli(cmd, use_shell=False):
    if not isinstance(cmd, list):
        cmd = [cmd]
    if use_shell:
        cmd = [get_cmd_string(cmd)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=use_shell)
    stdout, stderr = p.communicate()
    rc = p.returncode
    return_value = { "stdout": stdout, "stderr": stderr, "rc": rc }
    return return_value

def log_error(retrunValue, errMsg, cmd):
    result["error"] = errMsg
    result["cmd"] = get_cmd_string(cmd)
    result["rc"] = retrunValue.get("rc")
    result["stdout"] = retrunValue.get("stdout")
    result["stderr"] = retrunValue.get("stderr")

def get_cmd_string(cmd):
    return ' '.join(cmd)

if __name__ == '__main__':
    main()