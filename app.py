import os
import json
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from core import network

app = FastAPI(title="Pi-WoL Core Console")
templates = Jinja2Templates(directory="templates")
DB_FILE = "devices.json"

def load_hardware_nodes():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except: return {}

def save_hardware_nodes(nodes):
    with open(DB_FILE, "w") as f: json.dump(nodes, f, indent=4)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    nodes = load_hardware_nodes()
    processed_nodes = {}
    
    for mac_key, node_info in nodes.items():
        profiles_list = []
        hardware_is_online = False
        active_os_detected = "offline"
        
        checked_ips = set()
        for p_id, p_info in node_info.get("profiles", {}).items():
            ip_target = p_info["ip"]
            
            if ip_target not in checked_ips:
                live_status = network.check_status_with_os(ip_target)
                checked_ips.add(ip_target)
                if live_status != "offline":
                    hardware_is_online = True
                    active_os_detected = live_status
            
            profiles_list.append({
                "id": p_id,
                "alias": p_info["alias"],
                "ip": ip_target,
                "os_type": p_info["os_type"],
                "os_label": p_info["os_type"].upper()
            })
            
        overall_state = "online" if hardware_is_online else "offline"

        processed_nodes[mac_key] = {
            "hardware_name": node_info.get("hardware_name", "Multi-Boot Client"),
            "mac": node_info["mac"],
            "state": overall_state,
            "active_os": active_os_detected,
            "profiles": profiles_list
        }
        
    return templates.TemplateResponse(request=request, name="index.html", context={
        "request": request, "nodes": processed_nodes
    })

@app.get("/api/lookup/{ip}")
async def dynamic_mac_lookup(ip: str):
    found_mac = network.resolve_ip_to_mac(ip.strip())
    if found_mac:
        return {"success": True, "mac": found_mac}
    return {"success": False, "error": "Unreachable"}

@app.post("/api/add")
async def web_add_device(
    alias: str = Form(...), mac: str = Form(...), ip: str = Form(...),
    os_type: str = Form(...)
):
    nodes = load_hardware_nodes()
    clean_mac = mac.upper().strip().replace("-", ":")
    clean_ip = ip.strip()
    clean_os = os_type.lower().strip()
    
    profile_unique_id = f"{clean_os}_{alias.lower().replace(' ', '_')}"
    
    if clean_mac not in nodes:
        nodes[clean_mac] = {
            "hardware_name": f"{alias.capitalize()} Rig",
            "mac": clean_mac,
            "profiles": {}
        }
        
    nodes[clean_mac]["profiles"][profile_unique_id] = {
        "alias": alias.strip(),
        "ip": clean_ip,
        "os_type": clean_os
    }
    
    save_hardware_nodes(nodes)
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/delete/{mac}/{profile_id}")
async def web_delete_profile(mac: str, profile_id: str):
    nodes = load_hardware_nodes()
    mac_key = mac.upper()
    if mac_key in nodes:
        if profile_id in nodes[mac_key]["profiles"]:
            del nodes[mac_key]["profiles"][profile_id]
        if not nodes[mac_key]["profiles"]:
            del nodes[mac_key]
        save_hardware_nodes(nodes)
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/wake/{mac}")
async def web_wake_device(mac: str):
    network.send_wol_packet(mac.upper())
    return RedirectResponse(url="/", status_code=303)

def run_winrm_safe(ip, username, password, command_payload):
    try:
        import winrm
        session = winrm.Session(ip, auth=(username, password), transport='ntlm', read_timeout_sec=6, operation_timeout_sec=5)
        session.run_cmd(command_payload) # Running raw command executions
        print(f"[WINDOWS POWER SUCCESS]: Execution completed for {ip}")
    except Exception as winrm_err:
        print(f"[WINDOWS POWER CONTROL ERROR]: Could not communicate via WinRM to {ip}. Details: {winrm_err}")

@app.post("/api/power/{action}/{ip}/{os_type}")
async def web_power_action(action: str, ip: str, os_type: str, bg_tasks: BackgroundTasks, username: str = Form(...), password: str = Form(...)):
    if os_type != "windows":
        bg_tasks.add_task(network.execute_linux_power_action, ip, username.strip(), password, action)
        return RedirectResponse(url="/", status_code=303)
        
    if username and password:
        # 🎯 Clean native commands that explicitly support headless shell contexts
        if action == "sleep":
            payload = "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
        else:
            payload = "shutdown.exe /s /f /t 0"
            
        bg_tasks.add_task(run_winrm_safe, ip, username.strip(), password, payload)
        
    return RedirectResponse(url="/", status_code=303)
