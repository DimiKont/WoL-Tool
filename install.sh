#!/bin/bash

# PiWoL Premium Silent Installer Philosophy
COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_BLUE='\033[0;34m'
COLOR_RESET='\033[0m'

# Clear screen frame for terminal focus
clear

echo -e "${COLOR_BLUE}=========================================${COLOR_RESET}"
echo -e "${COLOR_RED}      ___  _ _ _  _ ____ _    ${COLOR_RESET}"
echo -e "${COLOR_RED}      |__] | | |  | |  | |    ${COLOR_RESET}"
echo -e "${COLOR_RED}      |    | | |__| |__| |___ ${COLOR_RESET}"
echo -e "${COLOR_BLUE}=========================================${COLOR_RESET}"
echo -e "       Appliance Installer Utility Core   \n"

# 🌀 BACKGROUND SPINNER MACRO FUNCTION
run_with_spinner() {
    local message="$1"
    local command="$2"
    
    # Run the command in the background, suppressing all stdout/stderr logs
    eval "$command" > /dev/null 2>&1 &
    local pid=$!
    local spinner=( '/' '-' '\\' '|' )
    
    # Hide the terminal cursor while the spinner runs
    tput civvis
    
    while kill -0 $pid 2>/dev/null; do
        for icon in "${spinner[@]}"; do
            echo -ne "\r  [${COLOR_BLUE}${icon}${COLOR_RESET}] ${message}..."
            sleep 0.1
        done
    done
    
    # Wait for the command to catch any return exit status codes
    wait $pid
    local return_status=$?
    
    # Restore the cursor layout
    tput cnorm
    
    if [ $return_status -eq 0 ]; then
        # Print a beautiful green checkmark when complete
        echo -e "\r  [${COLOR_GREEN}✓${COLOR_RESET}] ${message}"
    else
        # Print a red fail alert if the script encounters a crash block
        echo -e "\r  [${COLOR_RED}✗${COLOR_RESET}] ${message} (Error Code: ${return_status})"
        exit 1
    fi
}

# --- THE MUTE INSTALLATION TIMELINE SEQUENCE ---

run_with_spinner "Synchronizing Linux core repositories" \
    "sudo apt-get update -y"

run_with_spinner "Installing environment tooling components (git, pip3)" \
    "sudo apt-get install -y git python3-pip iproute2"

run_with_spinner "Cloning verified application branch profiles" \
    "cd ~ && if [ -d 'PiWoL' ]; then cd PiWoL && git pull; else git clone https://github.com/YOUR_GITHUB_USERNAME/PiWoL.git; fi"

run_with_spinner "Deploying explicit runtime engines (fastapi, uvicorn, winrm)" \
    "pip3 install fastapi uvicorn pywinrm --break-system-packages"

run_with_spinner "Initializing local registry structure variables" \
    "cd ~/PiWoL && if [ ! -f 'devices.json' ]; then echo '{}' > devices.json; fi"

run_with_spinner "Injecting hardware layer security permission structures" \
    "SUDOERS_RULE=\"\$(whoami) ALL=(ALL) NOPASSWD: /usr/sbin/ip neigh flush *\" && if ! sudo grep -qF \"\$SUDOERS_RULE\" /etc/sudoers; then echo \"\$SUDOERS_RULE\" | sudo tee -a /etc/sudoers; fi"

run_with_spinner "Attaching and launching system environment background daemon" \
    "cd ~/PiWoL && sudo tee /etc/systemd/system/piwol.service > /dev/null <<EOF
[Unit]
Description=PiWoL Appliance Engine
After=network.target

[Service]
User=\$(whoami)
WorkingDirectory=\$(pwd)
ExecStart=/usr/local/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable piwol.service && sudo systemctl restart piwol.service"

# --- SUCCESS INTERFACE DISPLAY BOX ---
PI_IP=$(hostname -I | awk '{print $1}')
echo -e "\n${COLOR_GREEN}=====================================================${COLOR_RESET}"
echo -e " 🎉 ${COLOR_GREEN}PiWoL Installed Successfully!${COLOR_RESET}"
echo -e " 🌐 Access your dashboard console appliance via:"
echo -e "    ${COLOR_BLUE}http://${PI_IP}:8000${COLOR_RESET}"
echo -e "${COLOR_GREEN}=====================================================${COLOR_RESET}"