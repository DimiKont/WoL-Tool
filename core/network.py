import subprocess
import platform
import re
import socket

def get_default_gateway():
    """Dynamically extracts the default gateway IP address from the Linux kernel routing table."""
    try:
        with open("/proc/net/route", "r") as f:
            for line in f.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    hex_gw = parts[2]
                    # Convert little-endian hex to standard dot-decimal IP string
                    b1 = int(hex_gw[6:8], 16)
                    b2 = int(hex_gw[4:6], 16)
                    b3 = int(hex_gw[2:4], 16)
                    b4 = int(hex_gw[0:2], 16)
                    return f"{b1}.{b2}.{b3}.{b4}"
    except:
        pass
    
    # Cross-platform fallback for local testing environments
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return ".".join(local_ip.split(".")[:3]) + ".1"
    except:
        return None

def check_status_with_os(ip_address):
    """Pings a device and returns its online status and basic OS family via TTL signatures."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    cmd = ["ping", param, "1", "-W", "1", ip_address]
    
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        ttl_match = re.search(r"ttl=(\d+)", output, re.IGNORECASE)
        
        if ttl_match:
            ttl = int(ttl_match.group(1))
            if ttl > 64 and ttl <= 128:
                return True, "Windows OS"
            elif ttl <= 64:
                return True, "Linux / Apple"
                
        return True, "Unknown System"
    except subprocess.CalledProcessError:
        return False, "Offline"

def check_status(ip_address):
    """Simple boolean status check for dashboard legacy compatibility."""
    status, _ = check_status_with_os(ip_address)
    return status

def discover_devices():
    """Scans local ARP routing nodes, filtering out incomplete entries and the gateway dynamically."""
    found = []
    gateway_ip = get_default_gateway()
    
    try:
        output = subprocess.check_output(["arp", "-a"], text=True)
        matches = re.findall(r"\((.*?)\)\s+at\s+([0-9a-fA-F:]+)", output)
        
        for ip, mac in matches:
            if "incomplete" in mac.lower() or ip == gateway_ip:
                continue
                
            found.append({"ip": ip, "mac": mac.upper()})
    except Exception as e:
        print(f"[-] Local discovery failed: {str(e)}")
        
    return found

def send_wol_packet(mac_address):
    """Broadcasts a standard 102-byte Magic Packet sequence over UDP broadcast channel."""
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
