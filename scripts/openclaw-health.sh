#!/bin/bash
# OpenClaw Health Check & Auto-Fix Script
# Chạy: wsl -- bash /mnt/d/Contenfactory/scripts/openclaw-health.sh
# Hoặc copy vào WSL rồi: bash openclaw-health.sh

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

COMPOSE_FILE="/mnt/c/Users/Admin/.gemini/antigravity/scratch/docker-compose.yml"
MCP_COMPOSE="/mnt/d/Contenfactory/agents/openclaw-mcp/docker-compose.yml"

echo "========================================="
echo "  OpenClaw Health Check"
echo "========================================="

# 1. Docker daemon
echo -n "[1/6] Docker daemon... "
if docker info >/dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC} - Starting docker..."
    sudo systemctl start docker
    sleep 3
    if docker info >/dev/null 2>&1; then
        echo -e "  ${GREEN}Fixed${NC}"
    else
        echo -e "  ${RED}Cannot start docker. Run: sudo systemctl start docker${NC}"
        exit 1
    fi
fi

# 2. Containers running
echo -n "[2/6] Containers... "
RUNNING=$(docker ps --format '{{.Names}}' 2>/dev/null | sort | tr '\n' ' ')
NEED_START=false
for svc in 9router openclaw-gateway; do
    if ! echo "$RUNNING" | grep -q "$svc"; then
        NEED_START=true
        echo -e "${YELLOW}$svc not running${NC}"
    fi
done
if [ "$NEED_START" = true ]; then
    echo "  Starting containers..."
    docker compose -f "$COMPOSE_FILE" up -d 2>/dev/null
    [ -f "$MCP_COMPOSE" ] && docker compose -f "$MCP_COMPOSE" up -d 2>/dev/null
    sleep 5
    echo -e "  ${GREEN}Started${NC}"
else
    echo -e "${GREEN}OK${NC} ($RUNNING)"
fi

# 3. OpenClaw gateway health
echo -n "[3/6] Gateway health... "
sleep 2
HEALTH=$(docker inspect openclaw-gateway --format '{{.State.Status}}' 2>/dev/null || echo "missing")
if [ "$HEALTH" = "running" ]; then
    echo -e "${GREEN}running${NC}"
else
    echo -e "${RED}$HEALTH${NC} - Restarting..."
    docker restart openclaw-gateway
    sleep 15
fi

# 4. Wait for gateway ready
echo -n "[4/6] Gateway ready... "
for i in $(seq 1 12); do
    if docker exec openclaw-gateway node -e "fetch('http://127.0.0.1:18789/healthz').then(r=>{if(r.ok)process.exit(0);else process.exit(1)}).catch(()=>process.exit(1))" 2>/dev/null; then
        echo -e "${GREEN}OK${NC} (${i}0s)"
        break
    fi
    if [ "$i" = "12" ]; then
        echo -e "${RED}TIMEOUT after 120s${NC}"
        echo "  Check: docker logs --tail 30 openclaw-gateway"
        exit 1
    fi
    sleep 10
done

# 5. Telegram channel
echo -n "[5/6] Telegram... "
TG_STATUS=$(docker exec openclaw-gateway openclaw channels status --probe 2>&1 | grep -i telegram || echo "not found")
if echo "$TG_STATUS" | grep -q "works"; then
    echo -e "${GREEN}OK${NC}"
    echo "  $TG_STATUS"
elif echo "$TG_STATUS" | grep -q "running"; then
    echo -e "${GREEN}running${NC}"
    echo "  $TG_STATUS"
else
    echo -e "${RED}ISSUE${NC}"
    echo "  $TG_STATUS"
    echo "  Try: docker restart openclaw-gateway && sleep 60"
fi

# 6. Model test
echo -n "[6/6] Model (factory)... "
RESULT=$(docker exec openclaw-gateway node -e "fetch('http://9router:20128/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer sk-cbc933d4615534b2-8f3ukd-4aa137eb'},body:JSON.stringify({model:'factory',messages:[{role:'user',content:'ping'}],max_tokens:5})}).then(r=>r.text()).then(t=>{if(t.includes('error'))console.log('ERROR:'+t.substring(0,200));else console.log('OK')}).catch(e=>console.log('FAIL:'+e.message))" 2>&1)
if echo "$RESULT" | grep -q "^OK"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}$RESULT${NC}"
    echo "  Model quota may be exhausted. Check: https://aistudio.google.com/apikey"
fi

echo ""
echo "========================================="
echo "  Done. If all green, send a message to"
echo "  @contencreatorbot on Telegram to test."
echo "========================================="
