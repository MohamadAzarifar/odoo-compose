# Odoo 19 One-Click Docker Stack

Run **Odoo 19** on **Ubuntu 24.04** with PostgreSQL and nginx using a single command.

## Quick start

```bash
chmod +x start.sh scripts/enable-https.sh
./start.sh
```

`start.sh` will:

1. Install Docker Engine and `docker-compose` if missing, using the [cybrtps/Docker-offline-install](https://github.com/cybrtps/Docker-offline-install) bundle (with sha256 verification)
2. Create `.env` with strong random passwords
3. Render `odoo/config/odoo.conf`
4. Pull images and start `db`, `odoo`, and `nginx`

Then open the printed URL (port **80** by default), create a database, and use the **master password** shown in the output (also in `.env` as `ODOO_ADMIN_PASSWORD`).

## Services

| Service | Image | Role |
|---------|--------|------|
| `db` | `postgres:16` | Database (internal only) |
| `odoo` | `odoo:19` | Application (internal only) |
| `nginx` | `nginx:1.27-alpine` | Reverse proxy on HTTP `80` (and `443` when HTTPS is enabled) |
| `certbot` | `certbot/certbot` | Certificate renewal (Compose profile `https`, optional) |

**Network isolation:** `db` and `odoo` are attached only to an `internal: true` Docker network (no internet). `nginx` sits on both `frontend` (published ports) and `internal` (proxy to Odoo). `certbot` uses `frontend` so renewals can reach Let's Encrypt.

Data persists in Docker volumes `odoo_db_data` and `odoo_data`.

## Project layout

```
.
├── start.sh                 # One-click bootstrap + start
├── docker-compose.yml
├── .env.example
├── addons/                  # Custom Odoo addons (bind-mounted)
├── odoo/config/
│   └── odoo.conf.template   # Rendered to odoo.conf on start
├── nginx/conf.d/
│   ├── odoo.conf            # Default HTTP reverse proxy
│   └── odoo-https.conf.template
├── certbot/                 # ACME webroot + certificates
└── scripts/enable-https.sh  # Optional HTTPS switch
```

## Configuration

Copy is automatic; edit `.env` if you need custom values:

| Variable | Purpose |
|----------|---------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials |
| `ODOO_ADMIN_PASSWORD` | Odoo database manager master password |
| `HTTP_PORT` / `HTTPS_PORT` | Host ports (default 80 / 443) |
| `DOMAIN` / `EMAIL` | Required only for HTTPS |

Do not commit `.env` or `odoo/config/odoo.conf` (both are gitignored).

## Optional HTTPS (Let's Encrypt)

Default mode is **HTTP**. When you have a domain pointing at this server:

1. Set in `.env`:
   ```bash
   DOMAIN=odoo.example.com
   EMAIL=you@example.com
   ```
2. Ensure ports **80** and **443** are reachable from the internet (open firewall/security group if needed).
3. Run:
   ```bash
   ./scripts/enable-https.sh
   ```

This issues a certificate, switches nginx to HTTPS (HTTP → HTTPS redirect), and starts the `certbot` renewer under profile `https`.

Later starts with HTTPS:

```bash
docker-compose --profile https up -d
```

Revert to HTTP-only:

```bash
cp nginx/conf.d/odoo.conf.http.bak nginx/conf.d/odoo.conf
docker-compose --profile https down
docker-compose up -d
docker-compose exec nginx nginx -s reload
```

## Day-to-day commands

```bash
docker-compose ps
docker-compose logs -f odoo
docker-compose down          # stop containers (keeps volumes)
docker-compose up -d         # start again
```

Custom addons: place them under `addons/` and restart Odoo:

```bash
docker-compose restart odoo
```

## Troubleshooting

**Port 80 already in use**  
Change `HTTP_PORT` in `.env` (e.g. `8080`) and re-run `./start.sh`, or free the port.

**Docker permission denied**  
`start.sh` may add your user to the `docker` group. Log out and back in, or use `sudo ./start.sh`.

**Cannot create database / wrong master password**  
Use `ODOO_ADMIN_PASSWORD` from `.env`. After changing it, re-run `./start.sh` so `odoo.conf` is re-rendered, then `docker-compose restart odoo`.

**Odoo not reachable behind nginx**  
Check `docker-compose ps` and `docker-compose logs nginx odoo`. Confirm the host firewall allows `HTTP_PORT`.

**HTTPS certificate fails**  
DNS must resolve `DOMAIN` to this host; port 80 must be public; `EMAIL` and `DOMAIN` must be set in `.env`.

## Requirements

- Ubuntu 24.04 (or other Debian 12-based distro) for automatic Docker install
- `git` and `sha256sum` available when Docker is not yet installed
- Sized for a **6-core / 8GB** host with about **5 users** (Odoo workers=2; container limits leave ~1GB for the OS)
- Outbound network access to clone [Docker-offline-install](https://github.com/cybrtps/Docker-offline-install), pull Odoo/Postgres/nginx images, and (optionally) reach Let's Encrypt

### Resource limits (6-core / 8GB)

| Service | CPU limit | Memory limit |
|---------|-----------|--------------|
| `db` | 1.5 | 1.5 GB |
| `odoo` | 4.0 | 5 GB |
| `nginx` | 0.25 | 128 MB |

Odoo uses `workers = 2` and per-worker soft/hard memory caps (~1 / 1.25 GB) so a handful of users stay comfortable without starving Postgres.

### Docker install method

If Docker is missing, `start.sh` follows the [cybrtps/Docker-offline-install](https://github.com/cybrtps/Docker-offline-install) instructions:

1. Clone the repo
2. Verify `docker-offline-bundle-bookworm.tar.gz` sha256  
   (`bf3e6504e9f3d4f8a852f0a009d8e37676ae8475b9d6c770105681f64254584e`)
3. Run `./run-docker-install.sh`
