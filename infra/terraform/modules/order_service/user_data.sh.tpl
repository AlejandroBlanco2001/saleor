#!/bin/bash
set -euxo pipefail

# --- Docker + Compose plugin (Ubuntu 22.04) ---
apt-get update -y
apt-get install -y ca-certificates curl gnupg git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# --- App code ---
# Manual prerequisite (documented in README, not baked in here): the repo
# must be reachable without embedding credentials in user_data. Either a
# public git remote, or the AMI/instance already has the code (e.g. via a
# pre-baked snapshot) -- adjust this clone line for your actual setup.
mkdir -p /opt/saleor
cd /opt/saleor
git clone <YOUR_REPO_URL> . || echo "Manual step required: copy the repo to /opt/saleor (git clone or scp/aws s3 cp)."

# --- .env.cloud for the order-service Compose profile ---
cat > /opt/saleor/.env.cloud <<EOF
ASYNC_DATABASE_URL=${async_database_url}
DJANGO_EVENTS_URL=${django_events_url}
ORDER_SERVICE_SHARED_SECRET=${order_service_shared_secret}
EOF

cd /opt/saleor
ENV_FILE=.env.cloud docker compose --profile order-service up -d --build
