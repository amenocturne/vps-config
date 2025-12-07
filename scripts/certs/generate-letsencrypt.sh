#!/bin/bash
# Generate Let's Encrypt certificates for rutube.dad domains using Cloudflare DNS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Let's Encrypt Certificate Generator for rutube.dad ===${NC}\n"

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="$SCRIPT_DIR/../../ansible/inventories/remnawave-test/.secrets.yml"

# Try to load Cloudflare token from secrets file
if [ -f "$SECRETS_FILE" ]; then
    echo -e "${YELLOW}Loading Cloudflare API token from secrets file...${NC}"
    CF_Token=$(grep '^cloudflare_api_token:' "$SECRETS_FILE" | sed 's/cloudflare_api_token: *"\(.*\)"/\1/' | tr -d '"' | xargs)
fi

# Check if Cloudflare API token is set
if [ -z "$CF_Token" ] || [ "$CF_Token" = "" ]; then
    echo -e "${RED}ERROR: Cloudflare API token not found!${NC}"
    echo ""
    echo "Please add your Cloudflare API token to:"
    echo "  $SECRETS_FILE"
    echo ""
    echo "Add this line:"
    echo '  cloudflare_api_token: "your-token-here"'
    echo ""
    echo "To create a token:"
    echo "  1. Go to https://dash.cloudflare.com/profile/api-tokens"
    echo "  2. Click 'Create Token'"
    echo "  3. Use 'Edit zone DNS' template"
    echo "  4. Select 'rutube.dad' zone"
    echo "  5. Copy the token and add to secrets file"
    exit 1
fi

export CF_Token
echo -e "${GREEN}✓ Cloudflare API token loaded${NC}\n"

# Check if acme.sh is installed
if ! command -v acme.sh &> /dev/null; then
    echo -e "${YELLOW}acme.sh not found. Installing...${NC}"
    curl https://get.acme.sh | sh -s email=admin@rutube.dad
    # Source acme.sh
    . ~/.acme.sh/acme.sh.env
fi

# Base directory for certificates
CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/ansible/inventories/remnawave-test/certs"
mkdir -p "$CERT_DIR"

echo -e "${GREEN}Certificate directory: $CERT_DIR${NC}\n"

# Domains to generate certificates for
DOMAINS=(
    "nl1.rutube.dad"
    "us1.rutube.dad"
)

echo -e "${YELLOW}Generating wildcard certificate for *.rutube.dad${NC}"
echo ""

# Set Let's Encrypt as default CA
~/.acme.sh/acme.sh --set-default-ca --server letsencrypt

# Generate wildcard certificate
~/.acme.sh/acme.sh --issue \
    --dns dns_cf \
    -d "*.rutube.dad" \
    -d "rutube.dad" \
    --keylength ec-256

# Install certificates to our directory
~/.acme.sh/acme.sh --install-cert \
    -d "*.rutube.dad" \
    --ecc \
    --cert-file "$CERT_DIR/fullchain.pem" \
    --key-file "$CERT_DIR/key.pem" \
    --fullchain-file "$CERT_DIR/fullchain.pem"

# Set proper permissions
chmod 644 "$CERT_DIR/fullchain.pem"
chmod 600 "$CERT_DIR/key.pem"

echo ""
echo -e "${GREEN}✅ Certificates generated successfully!${NC}"
echo ""
echo "Certificate files:"
echo "  - Certificate: $CERT_DIR/fullchain.pem"
echo "  - Private Key: $CERT_DIR/key.pem"
echo ""
echo "Certificate details:"
openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -subject -dates -text | grep -A 2 "Subject Alternative Name" || true
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Deploy certificates to nodes: just deploy-nodes"
echo "  2. Verify certificates are loaded: docker logs remnanode"
echo "  3. Test connections from VPN clients"
