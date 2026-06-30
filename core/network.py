import subprocess
import re
import socket

def check_status_with_os(ip_address, username="tsomis"):
    try:
        ping_check = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip_address], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if ping_check.returncode != 0:
            subprocess.run(["sudo", "ip", "neigh", "flush", "to", ip_address], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "offline"

        raw_output = ping_check.stdout
        ttl_match = re.search(r"ttl=(\d+)", raw_output, re.IGNORECASE)
        if not ttl_match:
            return "offline"
            
        detected_ttl = int(ttl_match.group(1))
        if detected_ttl > 64:
            return "windows"

        ssh_command = [
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "NumberOfPasswordPrompts=0", "-o", "ConnectTimeout=1",
            f"{username}@{ip_address}", "cat /etc/os-release"
        ]
        ssh_query = subprocess.run(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if ssh_query.returncode == 0:
            os_info = ssh_query.stdout.lower()
            for distro in ['ubuntu', 'arch', 'debian', 'fedora', 'mint', 'pop', 'manjaro', 'kali']:
                if distro in os_info:
                    return distro
        return "linux"
    except:
        return "offline"

def resolve_ip_to_mac(ip_address):
    try:
        subprocess.run(["ping", "-c", "1", "-W", "1", ip_address], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output = subprocess.check_output(["arp", "-n", ip_address], text=True)
        match = re.search(r"([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})", output)
        if match:
            return match.group(0).upper()
    except:
        pass
    return None

def send_wol_packet(mac_address):
    try:
        clean_mac = mac_address.replace(":", "").replace("-", "")
        if len(clean_mac) != 12:
            return False
        payload = bytes.fromhex("FFFFFF" * 2 + clean_mac * 16)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(payload, ("255.255.255.255", 9))
        return True
    except:
        return False

def execute_linux_power_action(ip_address, username, password, action):
    """
    Handles granular execution routes for unix platforms.
    """
    target_cmd = "systemctl suspend" if action == "sleep" else "poweroff"
    strict_flags = (
        "-o StrictHostKeyChecking=no "
        "-o UserKnownHostsFile=/dev/null "
        "-o NumberOfPasswordPrompts=1 "
        "-o ConnectTimeout=4"
    )
    full_cmd = f"sshpass -p '{password}' ssh {strict_flags} {username}@{ip_address} 'echo \"{password}\" | sudo -S {target_cmd}'"
    try:
        subprocess.Popen(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False
