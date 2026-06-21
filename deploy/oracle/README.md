# Oracle Always-Free deploy — Terraform + GitHub Actions CI/CD

Professional, fully free, **push-to-deploy** pipeline for the AI Agent Hub.

- **Infra as code** — `terraform apply` (run from Cloud Shell, pre-authenticated) creates the VCN, security list (22/80/443), and a Ubuntu instance that **auto-installs Docker** via cloud-init.
- **CI/CD** — every `git push` to `main` builds a **multi-arch** image (amd64 + arm64 → works on both the x86 micro and the ARM A1), pushes it to **GHCR**, then deploys to the server over SSH.
- **Secrets never in git** — they live in GitHub Secrets and are written to the server at deploy time. Your real CV/photo are uploaded once and **runtime-mounted** (not baked into the image).

**Cost: $0** — Oracle Always-Free + GHCR (public, free) + GitHub Actions (unlimited for public repos) + Terraform.

---

## One-time setup

### 1. Provision the server
**Option A — fresh server (recommended for a clean, reproducible setup):**
```bash
# in Oracle Cloud Shell (Terraform is pre-installed + pre-authenticated)
cd ai-demo/deploy/oracle/terraform
cp terraform.tfvars.example terraform.tfvars      # fill compartment_ocid + both SSH public keys
terraform init
terraform apply                                   # creates VCN + instance; cloud-init installs Docker
```
Grab the printed `instance_public_ip`.

**Option B — use an existing instance** (e.g. the micro you already made): skip Terraform; just ensure Docker is installed there.

### 2. Create the deploy key (so GitHub Actions can SSH in)
```bash
# on your machine or in Cloud Shell
ssh-keygen -t ed25519 -f ~/.ssh/aihub_deploy -N ""
```
- **Public key** (`aihub_deploy.pub`) → add to the server:
  ```bash
  ssh ubuntu@<SERVER-IP> 'cat >> ~/.ssh/authorized_keys' < ~/.ssh/aihub_deploy.pub
  ```
  (Or set it as `deploy_ssh_public_key` in `terraform.tfvars` before `apply`.)
- **Private key** (`aihub_deploy`) → store as GitHub Secret **`DEPLOY_SSH_KEY`** (paste the whole file).

### 3. Set the GitHub Secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `OPENAI_API_KEY` | your LLM key |
| `OPENAI_BASE_URL` | e.g. `https://api.openai.com/v1` |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini` |
| `JWT_SECRET` | from `python -m hub.core.security` |
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_PASSWORD_HASH` | bcrypt hash from `python -m hub.core.security` |
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `DEPLOY_SSH_KEY` | the private key from step 2 |
| `ORACLE_HOST` | server public IP, e.g. `92.4.172.53` |
| `DOMAIN` | e.g. `aihub.duckdns.org` |
| `DUCKDNS_TOKEN` | from duckdns.org |
| `DUCKDNS_SUBDOMAIN` | e.g. `aihub` |
| `TZ` | e.g. `Europe/Berlin` |

(`OPENAI_TEMPERATURE`, `OPENAI_MAX_TOKENS`, `TELEGRAM_WEBHOOK_SECRET` are optional.)

### 4. Point a free domain at the server (for HTTPS — Telegram requires it)
1. [duckdns.org](https://www.duckdns.org) → add a subdomain (e.g. `aihub`).
2. Paste the server IP → **update** (so `aihub.duckdns.org` resolves to it).
3. Copy the **token** → `DUCKDNS_TOKEN` secret.

### 5. Upload your real CV + photo once (runtime data — not in the repo/image)
```bash
scp samples/cv.pdf samples/cover_letter.pdf ubuntu@<SERVER-IP>:~/ai-demo/samples/
scp photos/photo.JPG              ubuntu@<SERVER-IP>:~/ai-demo/photos/
```

### 6. Deploy
```bash
git push origin main     # triggers the workflow: build → push image → deploy
```
Watch the **Actions** tab. The `deploy` job ends with a health check against `https://<DOMAIN>/health`.

### 7. Register the Telegram webhook (once)
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<DOMAIN>/webhook/telegram"
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"   # last_error_message should be empty
```

---

## Ongoing
- Edit code → `git push` → bot auto-rebuilds and redeploys. **No SSH, no clicking.**
- Secrets: change them in GitHub **Settings → Secrets**; they're injected on the next deploy.
- CV/photo: re-upload to the server only when they change (not on every deploy).

## Operations
- **Logs:** `ssh ubuntu@<SERVER-IP>` → `cd ~/ai-demo/deploy/oracle && docker compose logs -f app`
- **Update the server manually:** `cd ~/ai-demo/deploy/oracle && docker compose pull && docker compose up -d`
- **Fresh server / disaster recovery:** `terraform apply` from Cloud Shell, then push.

## Troubleshooting
- **`/health` fails / cert not issued:** ensure DuckDNS resolves to the server IP (`nslookup <domain>`) and ports **80 + 443** are open in the security list.
- **`getWebhookInfo` shows `last_error_message`:** re-run `setWebhook` after the cert is issued.
- **Deploy job can't SSH:** the deploy public key isn't in the server's `~/.ssh/authorized_keys`, or `ORACLE_HOST`/`DEPLOY_SSH_KEY` secrets are wrong.
