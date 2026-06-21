# Deploy to Oracle Cloud Always-Free (best free option for this app)

Why Oracle: **$0 forever**, and it gives you the **RAM + disk the CV agent needs**.
Render's free tier starved you at 512 MB — the CV agent builds 4 PDFs in parallel
and OOM-killed there. Oracle's free Ampere VM gives **up to 24 GB RAM / 200 GB disk**,
which is far more than enough.

| Need (CV agent) | Oracle free gives | Render free gave |
|---|---|---|
| RAM for parallel PDF build | up to **24 GB** | 512 MB |
| Disk for generated PDFs | up to **200 GB** | ephemeral |
| Always-on (for prayer scheduler) | yes | sleeps after 15 min |

---

## 1. Create the VM (Oracle Console → Compute → Instances → Create)

- **Shape:** `VM.Standard.A1.Flex` (Ampere ARM). Recommended sweet spot:
  **2 OCPU / 8 GB RAM** — easy to allocate and ample for CV generation.
  You can go up to **4 OCPU / 24 GB** (still free) if you want max headroom,
  but the 4/24 single VM is the hardest to get capacity for.
- **Image:** Canonical **Ubuntu 22.04** (aarch64).
- **SSH keys:** **Save the private key** — unrecoverable later.
- **Boot volume:** click *Specify a custom boot volume size* → set **~150 GB**
  (Always-Free total block-storage allowance is 200 GB). This is where your
  generated PDFs accumulate, so give it room.
- Keep "Assign a public IPv4 address."

> **"Out of host capacity"?** The free ARM shapes fill up. Pick a quieter region
> during signup (Phoenix, San Jose, Mumbai, Osaka, Singapore, Stockholm, Milan…)
> and click *Create* again later — capacity frees up.

## 2. Reserve the IP + open ports

- **Reserve the public IP** (so it survives stop/start): instance → *IP addresses*
  → Ephemeral → *Reserve*.
- **Open ports** — Oracle only opens SSH/22 by default. VCN → Security Lists →
  default → Add Ingress Rules: `0.0.0.0/0` TCP **80** and `0.0.0.0/0` TCP **443**.
  (Do **not** open 8080 — only Caddy is public.)

## 3. On the VM: install + run

```bash
# from your PC
ssh -i <your-private-key> ubuntu@<VM-PUBLIC-IP>
```

```bash
# on the VM
git clone https://github.com/somia295/ai-demo.git && cd ai-demo
bash deploy/oracle/install.sh          # installs Docker, preps output/
newgrp docker                           # pick up docker group
```

Put your secrets in the **repo-root** `.env` (gitignored, didn't come with the clone).
From your PC:
```bash
scp -i <your-private-key> .env ubuntu@<VM-PUBLIC-IP>:~/ai-demo/.env
```
Make sure it has: `OPENAI_API_KEY`, `JWT_SECRET`, `ADMIN_PASSWORD_HASH`,
`TELEGRAM_BOT_TOKEN`, `PRODUCTION=true`.

Edit `deploy/oracle/.env` → set `DOMAIN` + `DUCKDNS_*`
(create a free subdomain at [duckdns.org](https://www.duckdns.org) first).

Build + launch (native ARM build — avoids x86/ARM image mismatch):
```bash
cd deploy/oracle
docker compose up -d --build --profile duckdns
docker compose logs -f app     # wait for "Application startup complete"
```

## 4. HTTPS + Telegram

Caddy auto-provisions a Let's Encrypt cert for your DuckDNS domain:
```bash
curl https://aihub.duckdns.org/health      # {"status":"ok"}
```

Register the webhook (Telegram requires https — that's why Caddy is mandatory):
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://aihub.duckdns.org/webhook/telegram"
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"   # last_error_message should be empty
```

Message your bot → it replies. Done.

---

## Operational notes

- **Survives reboots:** all three services use `restart: unless-stopped`; Caddy +
  DuckDNS are containers too, so they auto-start with Docker.
- **Generated PDFs** live in `~/ai-demo/output/` on the host (bind mount) — they
  persist across image rebuilds. Browse or `scp` them down anytime.
- **Prayer reminders are in-memory:** a VM reboot wipes registered users; re-share
  your location once to re-enable. (Tell me if you want this persisted to disk/DB.)
- **Updating the app:** `git pull && docker compose up -d --build` (output/ is
  preserved by the bind mount).
- **Cost:** $0. Oracle holds a card on file only to verify you're human; you are
  not charged while on Always-Free resources.

## Troubleshooting

- **`curl /health` fails / cert not issued:** ensure ports **80 and 443** are open
  in the security list, and your DuckDNS domain resolves to the VM IP
  (`nslookup aihub.duckdns.org`).
- **`getWebhookInfo` shows `last_error_message`:** usually the domain/cert — re-run
  the `setWebhook` curl after Caddy has issued the cert.
- **Docker permission denied:** run `newgrp docker` (or log out/in).
