#!/bin/bash

# PiWoL Automated Installation Script
# Mimicking the Pi-hole deployment philosophy

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_BLUE='\033[0;34m'
COLOR_RESET='\033[0m'

echo -e "${COLOR_BLUE}=========================================${COLOR_RESET}"
echo -e "${COLOR_RED}      ___  _ _ _  _ ____ _    ${COLOR_RESET}"
echo -e "${COLOR_RED}      |__] | | |  | |  | |    ${COLOR_RESET}"
echo -e "${COLOR_RED}      |    | | |__| |__| |___ ${COLOR_RESET}"
echo -e "${COLOR_BLUE}=========================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}[*] Initializing PiWoL Appliance Deployment Core...${COLOR_RESET}"

# 1. Update and install core Python system requirements
echo -e "[*] Synchronizing environment packages..."
sudo apt-get update -y && sudo apt-get install -y python3-pip python3-fastapi uvicorn git iproute2

# 2. Pull the repository directly into the home folder
echo -e "[*] Downloading application repository source maps..."
cd ~
if [ -d "PiWoL" ]; then
    echo -e "[*] Existing PiWoL environment found. Updating codebase..."
    cd PiWoL && git pull
else
    git clone https://github.com/YOUR_GITHUB_USERNAME/PiWoL.git
    cd PiWoL
fi

# 3. Initialize empty database storage if missing
if [ ! -f "devices.json" ]; then
    echo "{}" > devices.json
fi

# 4. Inject Passwordless Sudo Rule for Self-Cleaning Cache Operations
echo -e "[*] Configuring kernel neighborhood cache access permissions..."
SUDOERS_RULE="$(whoami) ALL=(ALL) NOPASSWD: /usr/sbin/ip neigh flush *"
if ! sudo grep -qF "$SUDOERS_RULE" /etc/sudoers; then
    echo "$SUDOERS_RULE" | sudo tee -a /etc/sudoers > /dev/null
fi

# 5. Build and attach the Background Systemd Unit File Manager Daemon
echo -e "[*] Building systemd background process service structures..."
sudo tee /etc/systemd/system/piwol.service > /dev/null <<EOF
[Unit]
Description=PiWoL Network Appliance Console
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 6. Ignite execution runtime loops
echo -e "[*] Starting application web backend process routing engines..."
sudo systemctl daemon-reload
sudo systemctl enable piwol.service
sudo systemctl restart piwol.service

# 7. Final Success Status Notice
PI_IP=$(hostname -I | awk '{print $1}')
echo -e "${COLOR_GREEN}=====================================================${COLOR_RESET}"
echo -e " 🎉 ${COLOR_GREEN}PiWoL Setup Complete Successfully!${COLOR_RESET}"
echo -e " 🌐 Access your dashboard console interface layers at:"
echo -e "    ${COLOR_BLUE}http://${PI_IP}:8000${COLOR_RESET}"
echo -e "${COLOR_GREEN}=====================================================${COLOR_RESET}"