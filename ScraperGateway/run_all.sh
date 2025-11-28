#!/bin/bash
#
# Universal Scraper Gateway - Startup Script
# Starts all backend services and the API gateway
#
# Usage:
#   ./run_all.sh          # Start all services
#   ./run_all.sh stop     # Stop all services
#   ./run_all.sh status   # Check service status

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ports
QUICKCOMM_PORT=8001
SHOPIFY_PORT=8002
REVIEWS_PORT=8003
GATEWAY_PORT=8080

# PID file locations
PID_DIR="$SCRIPT_DIR/.pids"
mkdir -p "$PID_DIR"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to stop all services
stop_services() {
    log_info "Stopping all services..."

    for pid_file in "$PID_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            service_name=$(basename "$pid_file" .pid)
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                log_success "Stopped $service_name (PID: $pid)"
            fi
            rm -f "$pid_file"
        fi
    done

    # Also kill by port as backup
    for port in $QUICKCOMM_PORT $SHOPIFY_PORT $REVIEWS_PORT $GATEWAY_PORT; do
        pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill $pid 2>/dev/null || true
        fi
    done

    log_success "All services stopped"
}

# Function to check service status
check_status() {
    echo ""
    echo "Service Status:"
    echo "==============="

    check_port() {
        local name=$1
        local port=$2
        if lsof -ti:$port >/dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} $name (port $port) - Running"
        else
            echo -e "${RED}✗${NC} $name (port $port) - Not running"
        fi
    }

    check_port "QuickComm" $QUICKCOMM_PORT
    check_port "ShopifyCode" $SHOPIFY_PORT
    check_port "reviews_Scraper" $REVIEWS_PORT
    check_port "Gateway" $GATEWAY_PORT
    echo ""
}

# Function to start a service
start_service() {
    local name=$1
    local dir=$2
    local module=$3
    local port=$4

    log_info "Starting $name on port $port..."

    cd "$dir"

    # Start uvicorn in background
    uvicorn "$module" --host 127.0.0.1 --port "$port" --log-level warning &
    local pid=$!

    echo $pid > "$PID_DIR/${name}.pid"

    # Wait a moment and check if it started
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        log_success "$name started (PID: $pid)"
    else
        log_error "Failed to start $name"
        return 1
    fi
}

# Function to start all services
start_services() {
    echo ""
    echo "============================================"
    echo "  Universal Scraper Gateway - Startup"
    echo "============================================"
    echo ""

    # Check if services are already running
    if lsof -ti:$GATEWAY_PORT >/dev/null 2>&1; then
        log_warn "Gateway already running on port $GATEWAY_PORT"
        log_info "Use './run_all.sh stop' to stop services first"
        exit 1
    fi

    # Start QuickComm
    start_service "quickcomm" "$PARENT_DIR/QuickComm" "app.main:app" $QUICKCOMM_PORT

    # Start ShopifyCode
    start_service "shopify" "$PARENT_DIR/ShopifyCode" "main:app" $SHOPIFY_PORT

    # Start reviews_Scraper
    start_service "reviews" "$PARENT_DIR/reviews_Scraper" "main:app" $REVIEWS_PORT

    # Wait for backends to initialize
    log_info "Waiting for backends to initialize..."
    sleep 2

    # Start Gateway
    log_info "Starting Gateway on port $GATEWAY_PORT..."
    cd "$SCRIPT_DIR"
    uvicorn main:app --host 0.0.0.0 --port $GATEWAY_PORT --log-level info &
    local gateway_pid=$!
    echo $gateway_pid > "$PID_DIR/gateway.pid"

    sleep 1
    if kill -0 $gateway_pid 2>/dev/null; then
        log_success "Gateway started (PID: $gateway_pid)"
    else
        log_error "Failed to start Gateway"
        exit 1
    fi

    echo ""
    echo "============================================"
    echo -e "${GREEN}All services started successfully!${NC}"
    echo "============================================"
    echo ""
    echo "Gateway URL:     http://localhost:$GATEWAY_PORT"
    echo "API Docs:        http://localhost:$GATEWAY_PORT/docs"
    echo "Health Check:    http://localhost:$GATEWAY_PORT/health/all"
    echo ""
    echo "Direct Access:"
    echo "  QuickComm:     http://localhost:$QUICKCOMM_PORT"
    echo "  ShopifyCode:   http://localhost:$SHOPIFY_PORT"
    echo "  Reviews:       http://localhost:$REVIEWS_PORT"
    echo ""
    echo "Example API Calls:"
    echo "  curl 'http://localhost:$GATEWAY_PORT/ecommerce/amazon/search?query=chocolate'"
    echo "  curl 'http://localhost:$GATEWAY_PORT/health/all'"
    echo ""
    echo "Press Ctrl+C to stop all services"
    echo ""

    # Trap Ctrl+C to stop services
    trap stop_services SIGINT SIGTERM

    # Wait for gateway process
    wait $gateway_pid
}

# Main script logic
case "${1:-start}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 1
        start_services
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
