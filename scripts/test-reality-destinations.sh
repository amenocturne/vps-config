#!/usr/bin/env bash
# Test websites for suitability as Xray Reality destinations.
# Run with VPN OFF to test accessibility from Russia.
#
# Requirements for Reality destination:
#   1. Accessible from Russia (not blocked by TSPU)
#   2. TLS 1.3 support
#   3. HTTP/2 support
#   4. Valid certificate chain
#   5. Responds on port 443
#
# Usage: ./scripts/test-reality-destinations.sh [--flush-dns] [--json]

set -euo pipefail

FLUSH_DNS=false
JSON_OUTPUT=false
TIMEOUT=5

for arg in "$@"; do
    case "$arg" in
        --flush-dns) FLUSH_DNS=true ;;
        --json) JSON_OUTPUT=true ;;
        --help|-h)
            echo "Usage: $0 [--flush-dns] [--json]"
            echo "  --flush-dns  Flush macOS DNS cache before testing"
            echo "  --json       Output results as JSON"
            exit 0
            ;;
    esac
done

# Candidate destinations grouped by category
# Format: domain|category|notes
CANDIDATES=(
    # Search engines (uncommon, less likely blocked)
    "search.brave.com|search|Brave Search"
    "kagi.com|search|Kagi Search"
    "www.bing.com|search|Microsoft Bing"
    "duckduckgo.com|search|DuckDuckGo"
    "www.ecosia.org|search|Ecosia"

    # Big tech (high traffic, hard to block entirely)
    "www.google.com|bigtech|Google"
    "www.microsoft.com|bigtech|Microsoft"
    "www.apple.com|bigtech|Apple"
    "www.samsung.com|bigtech|Samsung"
    "www.amazon.com|bigtech|Amazon"
    "www.oracle.com|bigtech|Oracle"

    # Microsoft services (enterprise dependency)
    "learn.microsoft.com|microsoft|MS Learn"
    "www.office.com|microsoft|Office 365"
    "login.microsoftonline.com|microsoft|Azure AD"
    "outlook.live.com|microsoft|Outlook"

    # Google services
    "dl.google.com|google|Google Downloads"
    "fonts.googleapis.com|google|Google Fonts"
    "translate.google.com|google|Google Translate"
    "play.google.com|google|Google Play"
    "developer.android.com|google|Android Dev"

    # Apple services
    "www.icloud.com|apple|iCloud"
    "swcdn.apple.com|apple|Apple Software CDN"
    "itunes.apple.com|apple|iTunes"

    # Developer/tech (commonly used, not political)
    "www.python.org|dev|Python"
    "www.rust-lang.org|dev|Rust"
    "go.dev|dev|Go"
    "nodejs.org|dev|Node.js"
    "www.php.net|dev|PHP"
    "stackoverflow.com|dev|Stack Overflow"
    "github.com|dev|GitHub"
    "cdn.jsdelivr.net|dev|jsDelivr CDN"
    "registry.npmjs.org|dev|npm Registry"
    "www.cloudflare.com|dev|Cloudflare"
    "www.mozilla.org|dev|Mozilla"

    # Hardware vendors (enterprise, hard to block)
    "www.nvidia.com|hardware|NVIDIA"
    "www.amd.com|hardware|AMD"
    "www.intel.com|hardware|Intel"
    "www.dell.com|hardware|Dell"
    "www.lenovo.com|hardware|Lenovo"
    "www.asus.com|hardware|ASUS"
    "www.hp.com|hardware|HP"
    "www.cisco.com|hardware|Cisco"

    # Gaming/entertainment (popular in Russia)
    "store.steampowered.com|gaming|Steam"
    "www.epicgames.com|gaming|Epic Games"
    "www.ea.com|gaming|EA"
    "www.riotgames.com|gaming|Riot Games"

    # CDN/infrastructure (blocking breaks too much)
    "one.one.one.one|cdn|Cloudflare DNS"
    "www.akamai.com|cdn|Akamai"
    "www.fastly.com|cdn|Fastly"

    # Education/reference
    "www.wikipedia.org|reference|Wikipedia"
    "www.w3.org|reference|W3C"
    "www.ieee.org|reference|IEEE"
    "arxiv.org|reference|arXiv"

    # Finance/business (enterprise dependency)
    "www.visa.com|finance|Visa"
    "www.mastercard.com|finance|Mastercard"
    "www.swift.com|finance|SWIFT"

    # Travel/booking
    "www.booking.com|travel|Booking.com"

    # Known blocked (control group)
    "www.speedtest.net|control-blocked|Speedtest (expected blocked)"
)

flush_dns() {
    if [[ "$FLUSH_DNS" == true ]]; then
        echo "Flushing DNS cache..."
        sudo dscacheutil -flushcache 2>/dev/null || true
        sudo killall -HUP mDNSResponder 2>/dev/null || true
        sleep 1
    fi
}

# Check a single domain for Reality suitability
# Returns: pass|fail|blocked  with details
check_domain() {
    local domain="$1"
    local result_tls13="fail"
    local result_h2="fail"
    local result_reachable="fail"
    local result_cert="fail"
    local tls_version=""
    local http_status=""
    local server_header=""
    local alpn_protocols=""
    local error_msg=""

    # 1. Test TLS handshake + version + certificate + ALPN
    local tls_output
    tls_output=$(echo "" | timeout "$TIMEOUT" openssl s_client \
        -connect "${domain}:443" \
        -tls1_3 \
        -alpn h2,http/1.1 \
        -servername "$domain" \
        2>&1) || true

    if echo "$tls_output" | grep -q "Verify return code: 0"; then
        result_cert="pass"
    fi

    tls_version=$(echo "$tls_output" | sed -n 's/.*Protocol *: *\([^ ]*\).*/\1/p' | head -1)
    tls_version="${tls_version:-unknown}"
    if [[ "$tls_version" == "TLSv1.3" ]]; then
        result_tls13="pass"
    fi

    alpn_protocols=$(echo "$tls_output" | sed -n 's/.*ALPN protocol: *\([^ ]*\).*/\1/p' | head -1)
    alpn_protocols="${alpn_protocols:-none}"
    if [[ "$alpn_protocols" == *"h2"* ]]; then
        result_h2="pass"
    fi

    # 2. Test HTTP/2 connectivity + get server info
    local curl_output
    curl_output=$(timeout "$TIMEOUT" curl -sS -I \
        --http2 \
        --resolve "${domain}:443:$(dig +short "$domain" A 2>/dev/null | head -1)" \
        "https://${domain}/" \
        2>&1) || true

    if echo "$curl_output" | grep -qi "^HTTP/2"; then
        result_h2="pass"
        result_reachable="pass"
        http_status=$(echo "$curl_output" | head -1 | tr -d '\r')
    elif echo "$curl_output" | grep -qi "^HTTP/"; then
        result_reachable="pass"
        http_status=$(echo "$curl_output" | head -1 | tr -d '\r')
    fi

    server_header=$(echo "$curl_output" | grep -i "^server:" | head -1 | sed 's/^[Ss]erver:\s*//' | tr -d '\r')

    # If connection failed entirely
    if [[ "$result_reachable" == "fail" && "$result_cert" == "fail" ]]; then
        error_msg="connection_failed"
    fi

    # Determine overall status
    local overall="fail"
    if [[ "$result_tls13" == "pass" && "$result_h2" == "pass" && "$result_cert" == "pass" && "$result_reachable" == "pass" ]]; then
        overall="pass"
    elif [[ "$result_reachable" == "fail" && "$result_cert" == "fail" ]]; then
        overall="blocked"
    fi

    echo "${overall}|${result_tls13}|${result_h2}|${result_cert}|${result_reachable}|${tls_version}|${alpn_protocols}|${http_status}|${server_header}|${error_msg}"
}

# Main
flush_dns

passed=()
failed=()
blocked=()

if [[ "$JSON_OUTPUT" == true ]]; then
    echo "["
    first=true
fi

total=${#CANDIDATES[@]}
current=0

for entry in "${CANDIDATES[@]}"; do
    IFS='|' read -r domain category notes <<< "$entry"
    current=$((current + 1))

    if [[ "$JSON_OUTPUT" != true ]]; then
        printf "\r[%d/%d] Testing %-40s" "$current" "$total" "$domain"
    fi

    result=$(check_domain "$domain")
    IFS='|' read -r overall tls13 h2 cert reachable tls_ver alpn http_stat server err <<< "$result"

    if [[ "$JSON_OUTPUT" == true ]]; then
        [[ "$first" == true ]] && first=false || echo ","
        cat <<JSONENTRY
  {
    "domain": "$domain",
    "category": "$category",
    "notes": "$notes",
    "overall": "$overall",
    "tls13": "$tls13",
    "h2": "$h2",
    "cert_valid": "$cert",
    "reachable": "$reachable",
    "tls_version": "$tls_ver",
    "alpn": "$alpn",
    "http_status": "$http_stat",
    "server": "$server"
  }
JSONENTRY
    fi

    case "$overall" in
        pass) passed+=("$domain|$category|$notes|$server") ;;
        blocked) blocked+=("$domain|$category|$notes") ;;
        fail) failed+=("$domain|$category|$notes|tls13=$tls13,h2=$h2,cert=$cert,reach=$reachable") ;;
    esac
done

if [[ "$JSON_OUTPUT" == true ]]; then
    echo ""
    echo "]"
    exit 0
fi

# Clear progress line
printf "\r%-80s\r" ""

echo ""
echo "========================================================================"
echo "  REALITY DESTINATION TEST RESULTS"
echo "========================================================================"
echo ""

# Suitable destinations
if [[ ${#passed[@]} -gt 0 ]]; then
    echo "SUITABLE (TLS 1.3 + H2 + Valid Cert + Reachable):"
    echo "--------"
    printf "  %-35s %-12s %-20s %s\n" "DOMAIN" "CATEGORY" "NOTES" "SERVER"
    printf "  %-35s %-12s %-20s %s\n" "------" "--------" "-----" "------"
    for entry in "${passed[@]}"; do
        IFS='|' read -r domain category notes server <<< "$entry"
        printf "  %-35s %-12s %-20s %s\n" "$domain" "$category" "$notes" "$server"
    done
    echo ""
fi

# Blocked
if [[ ${#blocked[@]} -gt 0 ]]; then
    echo "BLOCKED (unreachable from this network):"
    echo "--------"
    for entry in "${blocked[@]}"; do
        IFS='|' read -r domain category notes <<< "$entry"
        printf "  %-35s %-12s %s\n" "$domain" "$category" "$notes"
    done
    echo ""
fi

# Partial failures
if [[ ${#failed[@]} -gt 0 ]]; then
    echo "PARTIAL FAIL (reachable but missing requirements):"
    echo "--------"
    for entry in "${failed[@]}"; do
        IFS='|' read -r domain category notes details <<< "$entry"
        printf "  %-35s %-12s %-20s %s\n" "$domain" "$category" "$notes" "$details"
    done
    echo ""
fi

echo "========================================================================"
echo "  SUMMARY: ${#passed[@]} suitable / ${#blocked[@]} blocked / ${#failed[@]} partial"
echo "========================================================================"
echo ""

if [[ ${#passed[@]} -gt 0 ]]; then
    echo "Recommended for Reality config (copy to nodes.yml):"
    echo ""
    echo "  reality_destinations:"
    for entry in "${passed[@]}"; do
        IFS='|' read -r domain category notes server <<< "$entry"
        echo "    - dest: \"${domain}:443\""
        echo "      server_names: [\"${domain}\"]"
        echo "      category: ${category}  # ${notes}"
    done
fi
