#!/bin/bash
# Diagnose Remnawave VPN connectivity issues
# This script checks DNS, Cloudflare proxy status, and node connectivity

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NODES_INVENTORY="$PROJECT_ROOT/ansible/inventories/nodes.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Remnawave VPN Connectivity Diagnostic Tool${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if nodes inventory exists
if [ ! -f "$NODES_INVENTORY" ]; then
    echo -e "${RED}✗ Error: Nodes inventory not found at $NODES_INVENTORY${NC}"
    exit 1
fi

# Extract node information from inventory
echo -e "${BLUE}📋 Reading node configuration...${NC}"
NODE_INFO=$(awk '
    /node-[0-9]+:/ {node=$1; sub(/:$/, "", node)}
    /ansible_host:/ {ip=$2}
    /vless_ws_domain:/ {domain=$2; gsub(/"/, "", domain); print node "," ip "," domain}
' "$NODES_INVENTORY")

if [ -z "$NODE_INFO" ]; then
    echo -e "${RED}✗ No nodes found in inventory${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found $(echo "$NODE_INFO" | wc -l) nodes${NC}"
echo ""

# Test each node
echo "$NODE_INFO" | while IFS=',' read -r NODE_NAME NODE_IP VLESS_DOMAIN; do
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Testing: $NODE_NAME${NC}"
    echo -e "  IP: $NODE_IP"
    echo -e "  Domain: $VLESS_DOMAIN"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Test 1: DNS Resolution
    echo -e "${YELLOW}[1/7]${NC} DNS Resolution Test..."
    DNS_RESULT=$(dig +short "$VLESS_DOMAIN" | head -1)
    
    if [ -z "$DNS_RESULT" ]; then
        echo -e "  ${RED}✗ FAIL: Domain does not resolve${NC}"
        echo -e "  ${YELLOW}→ Action: Add DNS A record in Cloudflare for $VLESS_DOMAIN pointing to $NODE_IP${NC}"
    elif [[ "$DNS_RESULT" =~ ^104\. ]] || [[ "$DNS_RESULT" =~ ^172\. ]]; then
        echo -e "  ${GREEN}✓ PASS: Resolves to Cloudflare IP ($DNS_RESULT)${NC}"
    elif [ "$DNS_RESULT" = "$NODE_IP" ]; then
        echo -e "  ${RED}✗ FAIL: Resolves to node IP directly ($DNS_RESULT)${NC}"
        echo -e "  ${YELLOW}→ Action: Enable Cloudflare proxy (orange cloud) for $VLESS_DOMAIN${NC}"
    else
        echo -e "  ${YELLOW}⚠ WARNING: Resolves to unexpected IP ($DNS_RESULT)${NC}"
    fi
    echo ""
    
    # Test 2: Cloudflare Proxy Check
    echo -e "${YELLOW}[2/7]${NC} Cloudflare Proxy Check..."
    CF_CHECK=$(curl -sI "https://$VLESS_DOMAIN" 2>/dev/null | grep -i "cf-ray" || true)
    
    if [ -n "$CF_CHECK" ]; then
        echo -e "  ${GREEN}✓ PASS: Traffic is proxied through Cloudflare${NC}"
        echo -e "  ${GREEN}  $CF_CHECK${NC}"
    else
        echo -e "  ${RED}✗ FAIL: Not proxied through Cloudflare${NC}"
        echo -e "  ${YELLOW}→ Action: Enable Cloudflare proxy (orange cloud)${NC}"
    fi
    echo ""
    
    # Test 3: HTTPS Connectivity
    echo -e "${YELLOW}[3/7]${NC} HTTPS Connectivity Test..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://$VLESS_DOMAIN" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "000" ]; then
        echo -e "  ${RED}✗ FAIL: Cannot connect via HTTPS${NC}"
        echo -e "  ${YELLOW}→ Action: Check if node is listening on port 443${NC}"
    elif [ "$HTTP_CODE" = "404" ] || [ "$HTTP_CODE" = "400" ] || [ "$HTTP_CODE" = "426" ]; then
        echo -e "  ${GREEN}✓ PASS: HTTPS connection successful (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "  ${YELLOW}⚠ WARNING: Unexpected HTTP code ($HTTP_CODE)${NC}"
    fi
    echo ""
    
    # Test 4: WebSocket Support
    echo -e "${YELLOW}[4/7]${NC} WebSocket Support Check..."
    WS_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Connection: Upgrade" \
        -H "Upgrade: websocket" \
        "https://$VLESS_DOMAIN/api/v2/ws" 2>/dev/null || echo "000")
    
    if [ "$WS_CHECK" = "101" ] || [ "$WS_CHECK" = "426" ] || [ "$WS_CHECK" = "400" ]; then
        echo -e "  ${GREEN}✓ PASS: WebSocket endpoint responds (HTTP $WS_CHECK)${NC}"
    else
        echo -e "  ${RED}✗ FAIL: WebSocket not working (HTTP $WS_CHECK)${NC}"
        echo -e "  ${YELLOW}→ Action: Enable WebSocket in Cloudflare Network settings${NC}"
    fi
    echo ""
    
    # Test 5: Node Direct Connectivity (Reality port 8443)
    echo -e "${YELLOW}[5/7]${NC} Direct Node Connectivity (Reality)..."
    if timeout 3 bash -c "echo > /dev/tcp/$NODE_IP/8443" 2>/dev/null; then
        echo -e "  ${GREEN}✓ PASS: Port 8443 is accessible${NC}"
    else
        echo -e "  ${RED}✗ FAIL: Cannot connect to port 8443${NC}"
        echo -e "  ${YELLOW}→ Action: Check firewall allows port 8443${NC}"
    fi
    echo ""
    
    # Test 6: Node Panel API Port (2222)
    echo -e "${YELLOW}[6/7]${NC} Node Panel API Port..."
    if timeout 3 bash -c "echo > /dev/tcp/$NODE_IP/2222" 2>/dev/null; then
        echo -e "  ${GREEN}✓ PASS: Port 2222 is accessible${NC}"
    else
        echo -e "  ${YELLOW}⚠ WARNING: Cannot connect to port 2222${NC}"
        echo -e "  ${YELLOW}→ Note: This is normal if firewall blocks external access${NC}"
    fi
    echo ""
    
    # Test 7: SSL Certificate Check
    echo -e "${YELLOW}[7/7]${NC} SSL Certificate Check..."
    SSL_INFO=$(echo | timeout 3 openssl s_client -connect "$NODE_IP:443" -servername "$VLESS_DOMAIN" 2>/dev/null | grep -E "subject=|issuer=" || true)
    
    if [ -n "$SSL_INFO" ]; then
        echo -e "  ${GREEN}✓ PASS: SSL certificate found${NC}"
        echo "$SSL_INFO" | while read -r line; do
            echo -e "  ${GREEN}  $line${NC}"
        done
    else
        echo -e "  ${RED}✗ FAIL: No SSL certificate or connection failed${NC}"
        echo -e "  ${YELLOW}→ Action: Check SSL certificates in /opt/remnanode/certs/${NC}"
    fi
    echo ""
    echo ""
done

# Summary and recommendations
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Diagnostic Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Common Issues and Fixes:${NC}"
echo ""
echo -e "1. ${YELLOW}DNS resolves to node IP instead of Cloudflare IP:${NC}"
echo -e "   → Enable Cloudflare proxy (orange cloud) in DNS settings"
echo ""
echo -e "2. ${YELLOW}Domain doesn't resolve:${NC}"
echo -e "   → Add A record in Cloudflare pointing to node IP"
echo ""
echo -e "3. ${YELLOW}WebSocket not working:${NC}"
echo -e "   → Enable WebSocket in Cloudflare → Network settings"
echo ""
echo -e "4. ${YELLOW}SSL certificate issues:${NC}"
echo -e "   → Check /opt/remnanode/certs/ on node servers"
echo -e "   → Ensure SSL mode is 'Full (strict)' in Cloudflare"
echo ""
echo -e "5. ${YELLOW}Reality works but WebSocket doesn't:${NC}"
echo -e "   → This is a DNS/Cloudflare configuration issue"
echo -e "   → Follow steps 1-3 above"
echo ""
echo -e "${GREEN}For detailed setup instructions, see:${NC}"
echo -e "  docs/REMNAWAVE_DNS_SETUP.md"
echo ""
