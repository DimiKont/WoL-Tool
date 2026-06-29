import os
import json
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from core import network

app = FastAPI(title="Smart WoL Core Engine")
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
    
    processed_devices = {}
    for alias, info in devices.items():
        is_online, os_family = network.check_status_with_os(info["ip"])
        processed_devices[alias] = {
            "ip": info["ip"],
            "mac": info["mac"],
            "online": is_online,
            "os": os_family if is_online else "Offline State"
        }
        
    render_context = {
        "request": request,
        "devices": processed_devices,
        "scan_results": current_scan_cache,
        "current_user": SESSION_USER,
        "current_pass": SESSION_PASS,
        "session_set": bool(SESSION_USER and SESSION_PASS),
        "has_env_creds": bool(SESSION_USER and SESSION_PASS)
    }
    
    current_scan_cache = []
    return templates.TemplateResponse(request=request, name="index.html", context=render_context)

@app.post("/api/credentials")
async def web_set_credentials(username: str = Form(...), password: str = Form(...)):
    global SESSION_USER, SESSION_PASS
    SESSION_USER = username.strip()
    SESSION_PASS = password
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/scan")
async def web_scan_network():
    global current_scan_cache
    raw_discovered = network.discover_devices() or []
    
    current_scan_cache = []
    for dev in raw_discovered:
        _, os_family = network.check_status_with_os(dev["ip"])
        current_scan_cache.append({
            "ip": dev["ip"],
            "mac": dev["mac"].upper(),
            "os": os_family
        })
        
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/add")
async def web_add_device(alias: str = Form(...), mac: str = Form(...), ip: str = Form(...)):
    devices = load_devices()
    target_alias = alias.lower().strip()
    target_mac = mac.upper().strip()
    target_ip = ip.strip()
    
    # Check for tracking collisions
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
def web_sleep_device(alias: str, username: str = Form(None), password: str = Form(None)):
    devices = load_devices()
    target = alias.lower()
    
    user = username.strip() if (username and username.strip()) else SESSION_USER
    text_pass = password if (password and password.strip()) else SESSION_PASS
    
    if not user or not text_pass:
        raise HTTPException(status_code=400, detail="Missing authorization tokens.")

    if target in devices:
        device = devices[target]
        
        sleep_payload = (
            "$rundll = '[DllImport(\"powrprof.dll\")] public static extern bool SetSuspendState(bool hiber, bool force, bool disable);'; "
            "$type = Add-Type -MemberDefinition $rundll -Name \"Win32Power\" -Namespace \"Win32\" -PassThru; "
            "$type::SetSuspendState($false, $false, $false)"
        )
        
        try:
            import winrm
            # FIXED PARAMETERS: Matching our successful CLI test script configuration
            session = winrm.Session(
                device["ip"], 
                auth=(user, text_pass), 
                transport='ntlm', 
                read_timeout_sec=10, 
                operation_timeout_sec=5
            )
            session.run_ps(sleep_payload)
        except Exception as e:
            # Catching the read timeout because it means the computer successfully went to sleep!
            if "timeout" in str(e).lower():
                pass 
            else:
                raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
                
        return RedirectResponse(url="/", status_code=303)
    raise HTTPException(status_code=404, detail="Target node mismatch")
