import subprocess
import re
import platform

def check_status_with_os(ip_address):
    """Pings a device and strictly verifies if its response signature falls into the Windows TTL block."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    cmd = ["ping", param, "1", "-W", "1", ip_address]
    
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        ttl_match = re.search(r"ttl=(\d+)", output, re.IGNORECASE)
        
        if ttl_match:
            ttl = int(ttl_match.group(1))
            # Strict Windows signature mapping block
            if ttl > 64 and ttl <= 128:
                return True, "Windows OS"
                
        return False, "Non-Windows"
    except:
        return False, "Offline"

def discover_devices():
    """Reads the raw system ARP table directly, performing a strict single check on the TTL response frame."""
    found = []
    
    try:
        # Pull everything sitting inside the Linux neighbor cache directly
        output = subprocess.check_output(["arp", "-a"], text=True)
        matches = re.findall(r"\((.*?)\)\s+at\s+([0-9a-fA-F:]+)", output)
        
        for ip, mac in matches:
            if "incomplete" in mac.lower():
                continue
                
            # Direct TTL check validation frame
            is_windows, os_label = check_status_with_os(ip)
            
            # If the device answers the ping and drops a Windows signature, keep it!
            if is_windows:
                found.append({
                    "ip": ip, 
                    "mac": mac.upper(),
                    "name": "Windows Desktop"
                })
                
        # Sort sequentially by IP block structures
        found.sort(key=lambda x: [int(num) for num in x["ip"].split(".")])
        
    except Exception as e:
        print(f"[-] Discovery pipeline failure: {str(e)}")
        
    return found

def send_wol_packet(mac_address):
    """Broadcasts a standard 102-byte Magic Packet sequence over UDP."""
    try:
        import socket
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
