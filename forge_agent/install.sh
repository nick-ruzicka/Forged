#!/bin/bash
set -e
echo "Installing Forge Agent..."

mkdir -p ~/.forge

AGENT_PATH="$(cd "$(dirname "$0")" && pwd)/agent.py"
PYTHON="$(which python3)"
PLIST=~/Library/LaunchAgents/com.forge.agent.plist

echo "  Agent script: $AGENT_PATH"
echo "  Python: $PYTHON"

# Generate token if not present
if [ ! -f ~/.forge/agent-token ]; then
  python3 -c "import secrets; print(secrets.token_hex(32))" > ~/.forge/agent-token
  echo "  Token generated: ~/.forge/agent-token"
fi

# Write launchd plist
cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.forge.agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${AGENT_PATH}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${HOME}/.forge/agent.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/.forge/agent.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DOCKER_HOST</key>
    <string>unix://${HOME}/.colima/default/docker.sock</string>
  </dict>
</dict>
</plist>
EOF

# Load the service
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "✓ Forge Agent installed and running on localhost:4242"
echo "  Token: ~/.forge/agent-token"
echo "  Log:   ~/.forge/agent.log"
echo "  Plist: $PLIST"
echo ""
echo "  Test: curl http://localhost:4242/health"
