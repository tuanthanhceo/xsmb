#!/bin/bash
# XSMB Scraper - VPS Deploy Script
# Chạy trên VPS: bash deploy.sh

set -e

echo "=== XSMB Scraper Deploy ==="

# 1. Cài Docker nếu chưa có
if ! command -v docker &> /dev/null; then
    echo ">>> Cài Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Docker đã cài. Nếu lần đầu, logout rồi login lại để dùng docker không cần sudo."
fi

# 2. Cài Docker Compose plugin nếu chưa có
if ! docker compose version &> /dev/null 2>&1; then
    echo ">>> Cài Docker Compose plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

# 3. Clone repo
cd /root
if [ -d "xsmb" ]; then
    echo ">>> Folder xsmb đã tồn tại, pull latest..."
    cd xsmb
    git pull origin main
else
    echo ">>> Clone repo..."
    git clone https://github.com/tuanthanhceo/xsmb.git
    cd xsmb
fi

# 4. Tạo .env
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://xsmb:xsmb_secret@db:5432/xsmb
LOG_LEVEL=INFO
KETQUA_VN_URL=https://ketqua.vn/xo-so-mien-bac
KETQUA_NET_DAILY_URL=https://ketqua04.net/xsmb
KETQUA_NET_BATCH_URL=https://ketqua04.net/xsmb-300-ngay
MIN_DELAY=2.0
MAX_DELAY=5.0
EOF
    echo ">>> Đã tạo .env"
fi

# 5. Build và chạy
echo ">>> Build Docker image..."
docker compose build

echo ">>> Start DB..."
docker compose up -d db
sleep 5

echo ">>> Init database..."
docker compose run --rm scraper db init

echo ""
echo "=== Deploy xong! ==="
echo ""
echo "Chạy scrape full (nền, ~2.5 giờ):"
echo "  cd /root/xsmb && docker compose run -d --rm scraper scrape full"
echo ""
echo "Xem log:"
echo "  docker logs -f \$(docker ps -q --filter ancestor=xsmb-scraper)"
echo ""
echo "Kiểm tra status:"
echo "  cd /root/xsmb && docker compose run --rm scraper status"
echo ""
echo "Export CSV:"
echo "  cd /root/xsmb && docker compose run --rm scraper export csv"
