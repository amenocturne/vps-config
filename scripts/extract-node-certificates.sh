#!/bin/bash
# Extract SSL certificates from Remnawave nodes for panel trust
# This script extracts self-signed certificates from all running nodes
# and creates a CA bundle that the panel can use for secure TLS connections

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NODES_INVENTORY="$PROJECT_ROOT/ansible/inventories/nodes.yml"
OUTPUT_DIR="$PROJECT_ROOT/tmp"
CA_BUNDLE="$OUTPUT_DIR/remnawave-nodes-ca.pem"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Remnawave Node Certificate Extractor${NC}"
echo "========================================"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if nodes inventory exists
if [ ! -f "$NODES_INVENTORY" ]; then
    echo -e "${RED}Error: Nodes inventory not found at $NODES_INVENTORY${NC}"
    exit 1
fi

# Extract node IPs from inventory
echo "Extracting node IPs from inventory..."
NODE_IPS=$(grep -E "ansible_host:" "$NODES_INVENTORY" | awk '{print $2}' | sort -u)

if [ -z "$NODE_IPS" ]; then
    echo -e "${RED}Error: No node IPs found in inventory${NC}"
    exit 1
fi

echo -e "Found nodes:"
echo "$NODE_IPS" | while read ip; do echo "  - $ip"; done
echo ""

# Clear old CA bundle
> "$CA_BUNDLE"
echo "# Remnawave Node CA Bundle" >> "$CA_BUNDLE"
echo "# Auto-generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" >> "$CA_BUNDLE"
echo "" >> "$CA_BUNDLE"

# Extract certificate from each node
SUCCESS_COUNT=0
FAIL_COUNT=0

for NODE_IP in $NODE_IPS; do
    echo -n "Extracting certificate from $NODE_IP:2222... "
    
    # Try to extract certificate
    CERT=$(echo "" | timeout 5 openssl s_client -connect "$NODE_IP:2222" -showcerts 2>/dev/null | \
           awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/{print}' | \
           awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/{cert=cert$0"\n"}/END CERTIFICATE/{if(length(cert)>0){print cert; exit}; cert=""}')
    
    if [ -n "$CERT" ]; then
        echo -e "${GREEN}✓${NC}"
        echo "# Node: $NODE_IP" >> "$CA_BUNDLE"
        echo "$CERT" >> "$CA_BUNDLE"
        echo "" >> "$CA_BUNDLE"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo -e "${RED}✗${NC}"
        echo -e "  ${YELLOW}Failed to extract certificate. Is the node running and accessible?${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

echo ""
echo "========================================"
echo -e "Results: ${GREEN}$SUCCESS_COUNT succeeded${NC}, ${RED}$FAIL_COUNT failed${NC}"

if [ $SUCCESS_COUNT -eq 0 ]; then
    echo -e "${RED}Error: No certificates were extracted!${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Ensure nodes are deployed and running:"
    echo "     just deploy-nodes"
    echo "     just ssh-nodes 'docker ps | grep remnanode'"
    echo ""
    echo "  2. Verify nodes are listening on port 2222:"
    echo "     just ssh-nodes 'ss -tlnp | grep :2222'"
    echo ""
    echo "  3. Check firewall allows port 2222:"
    echo "     just ssh-nodes 'sudo ufw status | grep 2222'"
    echo ""
    echo "  4. Test connectivity manually:"
    for NODE_IP in $NODE_IPS; do
        echo "     nc -zv $NODE_IP 2222"
    done
    exit 1
fi

echo ""
echo "CA Bundle created: $CA_BUNDLE"
echo ""

# Offer to copy to panel server
read -p "Copy CA bundle to panel server now? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Try to extract panel IP from remnawave-test inventory
    REMNAWAVE_INVENTORY="$PROJECT_ROOT/ansible/inventories/remnawave-test.yml"
    
    if [ -f "$REMNAWAVE_INVENTORY" ]; then
        PANEL_IP=$(grep -E "ansible_host:" "$REMNAWAVE_INVENTORY" | head -1 | awk '{print $2}')
        
        if [ -n "$PANEL_IP" ]; then
            echo "Copying to panel server at $PANEL_IP..."
            
            # Copy file
            scp "$CA_BUNDLE" "root@$PANEL_IP:/opt/remnawave/certs/remnawave-nodes-ca.pem"
            
            # Set permissions
            ssh "root@$PANEL_IP" "chown remnawave:remnawave /opt/remnawave/certs/remnawave-nodes-ca.pem && chmod 644 /opt/remnawave/certs/remnawave-nodes-ca.pem"
            
            # Restart panel
            echo "Restarting panel..."
            ssh "root@$PANEL_IP" "cd /opt/remnawave && docker compose restart"
            
            echo -e "${GREEN}✓ CA bundle deployed to panel server${NC}"
            echo ""
            echo "Verify in panel:"
            echo "  https://panel.yourdomain.com/nodes"
            echo "  Nodes should show as 'Online'"
        else
            echo -e "${YELLOW}Could not find panel IP in inventory${NC}"
            echo "Copy manually with:"
            echo "  scp $CA_BUNDLE root@PANEL_IP:/opt/remnawave/certs/remnawave-nodes-ca.pem"
        fi
    else
        echo -e "${YELLOW}Remnawave inventory not found${NC}"
        echo "Copy manually with:"
        echo "  scp $CA_BUNDLE root@PANEL_IP:/opt/remnawave/certs/remnawave-nodes-ca.pem"
    fi
else
    echo ""
    echo "To copy manually, run:"
    echo "  scp $CA_BUNDLE root@PANEL_IP:/opt/remnawave/certs/remnawave-nodes-ca.pem"
    echo "  ssh root@PANEL_IP 'chown remnawave:remnawave /opt/remnawave/certs/remnawave-nodes-ca.pem'"
    echo "  ssh root@PANEL_IP 'cd /opt/remnawave && docker compose restart'"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
