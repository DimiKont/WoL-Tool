import os
import json
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from core import network

app = FastAPI(title="Pi-WoL Core Console")
templates = Jinja2Templates(directory="templates")
DB_FILE = "devices.json"
AUTH_FILE = "auth.json"

def load_devices():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except: return {}

def save_devices(devices):
    with open(DB_FILE, "w") as f: json.dump(devices, f, indent=4)

def get_console_password():
    if not os.path.exists(AUTH_FILE):
        return ""
    try:
        with open(AUTH_FILE, "r") as f:
            return json.load(f).get("admin_password", "")
    except:
        return ""

def is_authenticated(request: Request):
    secret = get_console_password()
    if not secret: 
        return True
    return request.cookies.get("piwol_session") == "authenticated"

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_authenticated(request):
        return templates.TemplateResponse(request=request, name="index.html", context={
            "request": request, "auth_required": True, "error": False
        })

    devices = load_devices()
    client_host = request.client.host if request.client else None
    processed_devices = {}
    
    for alias, info in devices.items():
        if info["ip"] == client_host: continue
        is_online = network.check_status_with_os(info["ip"])
        os_platform = info.get("os_type", "windows").lower()
        processed_devices[alias] = {
            "ip": info["ip"], "mac": info["mac"], "online": is_online,
            "os_type": os_platform, "os_label": "Windows OS" if os_platform == "windows" else "Linux (SSH)"
        }
        
    return templates.TemplateResponse(request=request, name="index.html", context={
        "request": request, "devices": processed_devices, "auth_required": False
    })

@app.post("/login")
async def login(password: str = Form(...)):
    if password == get_console_password():
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="piwol_session", value="authenticated", max_age=86400, httponly=True)
        return response
    return templates.TemplateResponse(name="index.html", context={
        "request": {}, "auth_required": True, "error": True
    })

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("piwol_session")
    return response

@app.post("/api/add")
async def web_add_device(
    request: Request,
    alias: str = Form(...), mac: str = Form(...), ip: str = Form(...),
    os_type: str = Form(...), ssh_user: str = Form(None),
    is_dual_boot: str = Form(None),
    dual_alias: str = Form(None), dual_ip: str = Form(None),
    dual_os_type: str = Form(None), dual_ssh_user: str = Form(None)
):
    if not is_authenticated(request): return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    
    devices = load_devices()
    clean_mac = mac.upper().strip().replace("-", ":")
    
    primary_alias = alias.lower().strip()
    devices[primary_alias] = {
        "ip": ip.strip(), "mac": clean_mac,
        "os_type": os_type.lower().strip(), "ssh_user": ssh_user.strip() if ssh_user else ""
    }
    
    if is_dual_boot == "true" and dual_alias and dual_ip:
        secondary_alias = dual_alias.lower().strip()
        devices[secondary_alias] = {
            "ip": dual_ip.strip(), "mac": clean_mac,
            "os_type": dual_os_type.lower().strip(), "ssh_user": dual_ssh_user.strip() if dual_ssh_user else ""
        }
        
    save_devices(devices)
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/delete/{alias}")
async def web_delete_device(alias: str, request: Request):
    if not is_authenticated(request): return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    devices = load_devices()
    if alias.lower() in devices:
        del devices[alias.lower()]
        save_devices(devices)
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/wake/{alias}")
async def web_wake_device(alias: str, request: Request):
    if not is_authenticated(request): return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    devices = load_devices()
    target = alias.lower()
    if target in devices:
        network.send_wol_packet(devices[target]["mac"])
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/sleep/{alias}")
async def web_sleep_device(alias: str, bg_tasks: BackgroundTasks, request: Request, username: str = Form(None), password: str = Form(None)):
    if not is_authenticated(request): return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    devices = load_devices()
    target = alias.lower()
    if target not in devices: return RedirectResponse(url="/", status_code=303)
    
    device_info = devices[target]
    if device_info.get("os_type") == "linux":
        bg_tasks.add_task(network.execute_linux_ssh_sleep, device_info["ip"], device_info.get("ssh_user", "root"))
        return RedirectResponse(url="/", status_code=303)
        
    if username and password:
        sleep_payload = '$rundll = "[DllImport(\"powrprof.dll\")] public static extern bool SetSuspendState(bool hiber, bool force, bool disable);"; $type = Add-Type -MemberDefinition $rundll -Name "Win32Power" -Namespace "Win32" -PassThru; $type::SetSuspendState($false, $false, $false)'
        try:
            import winrm
            session = winrm.Session(device_info["ip"], auth=(username, password), transport='ntlm')
            bg_tasks.add_task(session.run_ps, sleep_payload)
        except: pass
        
    return RedirectResponse(url="/", status_code=303)
