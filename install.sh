#!/bin/bash

# Pi-WoL Premium Autopilot Installation Engine (Universal Token Edition)
COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_BLUE='\033[0;34m'
COLOR_YELLOW='\033[0;33m'
COLOR_RESET='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${COLOR_RED}  [✗] Error: Privileged environment context required.${COLOR_RESET}"
    echo -e "      Please run the installation script using: ${COLOR_BLUE}sudo bash${COLOR_RESET}"
    exit 1
fi

clear

echo -e "${COLOR_BLUE}=========================================${COLOR_RESET}"
echo -e "${COLOR_RED}      ___  _ _ _  _ ____ _    ${COLOR_RESET}"
echo -e "${COLOR_RED}      |__] | | |  | |  | |    ${COLOR_RESET}"
echo -e "${COLOR_RED}      |    | | |__| |__| |___ ${COLOR_RESET}"
echo -e "${COLOR_BLUE}=========================================${COLOR_RESET}"
echo -e "       Pi-WoL Premium Autopilot Installer   \n"

REAL_USER=${SUDO_USER:-$(whoami)}
REAL_HOME=$(eval echo ~$REAL_USER)

run_with_spinner() {
    local message="$1"
    local command="$2"
    
    eval "$command" > /dev/null 2>&1 &
    local pid=$!
    local spinner=( '/' '-' '\\' '|' )
    
    echo -ne "\033[?25l"
    while kill -0 $pid 2>/dev/null; do
        for icon in "${spinner[@]}"; do
            echo -ne "\r  [${COLOR_BLUE}${icon}${COLOR_RESET}] ${message}..."
            sleep 0.1
        done
    done
    wait $pid
    local return_status=$?
    echo -ne "\033[?25h"
    
    if [ $return_status -eq 0 ]; then
        echo -e "\r  [${COLOR_GREEN}✓${COLOR_RESET}] ${message}"
    else
        echo -e "\r  [${COLOR_RED}✗${COLOR_RESET}] ${message} (Error Code: ${return_status})"
        exit 1
    fi
}

run_with_spinner "Synchronizing Linux core repository indices" "apt-get update -y"
run_with_spinner "Installing foundational system layers (git, pip3)" "apt-get install -y git python3-pip iproute2 coreutils"

run_with_spinner "Cloning official Pi-WoL codebase repository from GitHub" \
    "cd $REAL_HOME && if [ -d 'Pi-WoL' ]; then rm -rf Pi-WoL; fi && sudo -u $REAL_USER git clone https://github.com/DimiKont/Pi-WoL.git"

run_with_spinner "Deploying runtime frameworks from requirements.txt" \
    "cd $REAL_HOME/Pi-WoL && pip3 install -r requirements.txt --break-system-packages"

run_with_spinner "Initializing local data profile registries" \
    "cd $REAL_HOME/Pi-WoL && if [ ! -f 'devices.json' ]; then echo '{}' > devices.json; fi && chown $REAL_USER:$REAL_USER devices.json"

# 🔑 GENERATE SECURE PI-HOLE RANDOM ALPHANUMERIC SEED TOKEN
GENERATED_TOKEN=$(head /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 12)
sudo -u $REAL_USER tee $REAL_HOME/Pi-WoL/auth.json > /dev/null <<EOF
{
    "admin_password": "$GENERATED_TOKEN"
}
EOF

run_with_spinner "Injecting hardware kernel cache access permissions" \
    "SUDOERS_RULE=\"$REAL_USER ALL=(ALL) NOPASSWD: /usr/sbin/ip neigh flush *\" && if ! grep -qF \"\$SUDOERS_RULE\" /etc/sudoers; then echo \"\$SUDOERS_RULE\" | tee -a /etc/sudoers; fi"

run_with_spinner "Building and enabling background system daemon wrapper" "
UVICORN_PATH=\$(sudo -u $REAL_USER which uvicorn)
if [ -z \"\$UVICORN_PATH\" ]; then
    UVICORN_PATH=\"$REAL_HOME/.local/bin/uvicorn\"
fi

sudo tee /etc/systemd/system/piwol.service > /dev/null <<EOF
[Unit]
Description=Pi-WoL Network Appliance Dashboard
After=network.target

[Service]
User=$REAL_USER
WorkingDirectory=$REAL_HOME/Pi-WoL
Environment=\"PATH=$REAL_HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"
ExecStart=\$UVICORN_PATH app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo \"$REAL_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart piwol.service, /usr/bin/systemctl enable piwol.service\" | tee -a /etc/sudoers > /dev/null
systemctl daemon-reload && systemctl enable piwol.service
"

run_with_spinner "Writing global terminal CLI access utility mapping rules" "sudo tee /usr/local/bin/pi-wol > /dev/null <<'EOF'
#!/bin/bash
COLOR_BLUE='\033[0;34m'
COLOR_GREEN='\033[0;32m'
COLOR_RESET='\033[0m'

REAL_USER=\${SUDO_USER:-\$(whoami)}
REAL_HOME=\$(eval echo ~\${REAL_USER})

if [ \"\$1\" = \"-p\" ]; then
    read -sp \"Enter New Web Console Password: \" new_pass
    echo \"\"
    if [ -n \"\$new_pass\" ]; then
        echo \"{\\\"admin_password\\\": \\\"\$new_pass\\\"}\" > \$REAL_HOME/Pi-WoL/auth.json
        chown \$REAL_USER:\$REAL_USER \$REAL_HOME/Pi-WoL/auth.json
        echo -e \"[✓] Pi-WoL administrative authentication token reset successfully!\"
        systemctl restart piwol.service
    else
        echo \"[✗] Error: Token cannot be blank.\"
    fi
    exit 0
fi

echo -e \"\n\${COLOR_BLUE}=== Pi-WoL Command Line Utility ===\${COLOR_RESET}\"
echo -e \"Status: \$(systemctl is-active piwol.service)\"
echo -e \"Local Dashboard Link: \${COLOR_GREEN}http://\$(hostname -I | awk '{print \$1}'):8000\${COLOR_RESET}\"
echo -e \"Commands: \n  pi-wol -p                           - Reset Console Web Password \n  sudo systemctl restart piwol.service - Restart Dashboard Engine\n\"
EOF
sudo chmod +x /usr/local/bin/pi-wol"

run_with_spinner "Starting application routing engine" "systemctl restart piwol.service"

PI_IP=$(hostname -I | awk '{print $1}')
echo -e "\n${COLOR_GREEN}=====================================================${COLOR_RESET}"
echo -e " 🎉 ${COLOR_GREEN}Pi-WoL Appliance Core Deployment Complete!${COLOR_RESET}"
echo -e " 🌐 Access your dashboard console appliance via:"
echo -e "    ${COLOR_BLUE}http://${PI_IP}:8000${COLOR_RESET}"
echo -e " 🔑 Your unique randomly generated console password is:"
echo -e "    ${COLOR_YELLOW}${GENERATED_TOKEN}${COLOR_RESET}"
echo -e "${COLOR_GREEN}=====================================================${COLOR_RESET}"

echo -e "\n${COLOR_YELLOW}What would you like to do next?${COLOR_RESET}"
echo "  1) Launch terminal information dashboard summary right now"
echo "  2) Exit setup and return to standard command prompt"
echo -ne "\nSelect option (1-2): "
read -r choice

if [ "$choice" = "1" ]; then
    /usr/local/bin/pi-wol
else
    echo -e "\nEnjoy your new console! Type ${COLOR_BLUE}pi-wol${COLOR_RESET} or ${COLOR_BLUE}pi-wol -p${COLOR_RESET} anytime.\n"
fi
