import os
import json
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from core import network

app = FastAPI(title="Smart-WoL Core Engine")
templates = Jinja2Templates(directory="templates")
DB_FILE = "devices.json"

SESSION_USER = ""
SESSION_PASS = ""
current_scan_cache = []

def load_devices():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_devices(devices):
    with open(DB_FILE, "w") as f:
        json.dump(devices, f, indent=4)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    global current_scan_cache
    devices = load_devices()
    client_host = request.client.host if request.client else None
    
    processed_devices = {}
    for alias, info in devices.items():
        if info["ip"] == client_host:
            continue
            
        is_online, os_family = network.check_status_with_os(info["ip"])
        
        processed_devices[alias] = {
            "ip": info["ip"],
            "mac": info["mac"],
            "online": is_online,
            "os": os_family
        }
        
    render_context = {
        "request": request,
        "devices": processed_devices,
        "scan_results": current_scan_cache,
        "current_user": SESSION_USER,
        "current_pass": SESSION_PASS,
        "session_set": bool(SESSION_USER and SESSION_PASS)
    }
    
    current_scan_cache = []
    return templates.TemplateResponse(request=request, name="index.html", context=render_context)

@app.post("/api/scan")
async def web_scan_network(request: Request):
    global current_scan_cache
    raw_discovered = network.discover_devices() or []
    devices = load_devices()
    
    tracked_macs = {info["mac"].upper() for info in devices.values()}
    client_host = request.client.host if request.client else None
    
    current_scan_cache = []
    for dev in raw_discovered:
        if dev["mac"] in tracked_macs or dev["ip"] == client_host or dev["ip"] == "127.0.0.1":
            continue
            
        _, os_family = network.check_status_with_os(dev["ip"])
            
        current_scan_cache.append({
            "ip": dev["ip"],
            "mac": dev["mac"],
            "name": dev["name"],
            "os": os_family
        })
        
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/add")
async def web_add_device(alias: str = Form(...), mac: str = Form(...), ip: str = Form(...)):
    devices = load_devices()
    target_alias = alias.lower().strip()
    target_mac = mac.upper().strip()
    target_ip = ip.strip()
    
    for existing_alias, info in devices.items():
        if info["mac"] == target_mac:
            raise HTTPException(status_code=400, detail=f"Collision: MAC {target_mac} already tracked as '{existing_alias}'.")
        if info["ip"] == target_ip:
            raise HTTPException(status_code=400, detail=f"Collision: IP {target_ip} already tracked as '{existing_alias}'.")
            
    if target_alias in devices:
        raise HTTPException(status_code=400, detail=f"The alias name '{target_alias}' is already allocated.")

    devices[target_alias] = {"ip": target_ip, "mac": target_mac}
    save_devices(devices)
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/delete/{alias}")
async def web_delete_device(alias: str):
    devices = load_devices()
    target = alias.lower()
    if target in devices:
        del devices[target]
        save_devices(devices)
    return RedirectResponse(url="/", status_code=303)

@app.get("/api/wake/{alias}")
async def web_wake_device(alias: str):
    devices = load_devices()
    target = alias.lower()
    if target in devices:
        network.send_wol_packet(devices[target]["mac"])
        return RedirectResponse(url="/", status_code=303)
    raise HTTPException(status_code=404, detail="Node mismatch")

@app.post("/api/sleep/{alias}")
def web_sleep_device(alias: str, username: str = Form(None), password: str = Form(None), remember: str = Form(None)):
    global SESSION_USER, SESSION_PASS
    devices = load_devices()
    target = alias.lower()
    
    # Check incoming inline modal tokens or pull from running application memory cache fallback
    user = username.strip() if username else SESSION_USER
    text_pass = password if password else SESSION_PASS
    
    if not user or not text_pass:
        raise HTTPException(status_code=400, detail="Missing credential authorization parameters.")

    # 🎯 PERSISTENCE LAYER: If "remember credentials" was toggled, store them globally in application memory
    if remember == "true" and username and password:
        SESSION_USER = username.strip()
        SESSION_PASS = password

    if target in devices:
        device = devices[target]
        
        sleep_payload = (
            "$rundll = '[DllImport(\"powrprof.dll\")] public static extern bool SetSuspendState(bool hiber, bool force, bool disable);'; "
            "$type = Add-Type -MemberDefinition $rundll -Name \"Win32Power\" -Namespace \"Win32\" -PassThru; "
            "$type::SetSuspendState($false, $false, $false)"
        )
        
        try:
            import winrm
            session = winrm.Session(
                device["ip"], 
                auth=(user, text_pass), 
                transport='ntlm', 
                read_timeout_sec=10, 
                operation_timeout_sec=5
            )
            session.run_ps(sleep_payload)
        except Exception as e:
            if "timeout" in str(e).lower():
                pass 
            else:
                raise HTTPException(status_code=500, detail=f"WinRM Execution error: {str(e)}")
                
        return RedirectResponse(url="/", status_code=303)
    raise HTTPException(status_code=404, detail="Target node mismatch")
