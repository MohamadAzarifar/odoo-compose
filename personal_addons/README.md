# Personal Odoo addons

Put your own custom modules here (one folder per module, each with `__manifest__.py`).

Mounted in the container as `/mnt/personal-addons` and listed **before** `./addons` in `addons_path`, so a personal module with the same technical name takes precedence over a third-party one in `addons/`.

## Layout

```text
personal_addons/
  my_module/
    __init__.py
    __manifest__.py
    models/
    views/
    ...
```

## After adding or changing a module

```bash
docker-compose restart odoo
```

Then in Odoo: **Apps → Update Apps List** → install/upgrade the module.

Use `./addons` for shared/third-party modules (themes, OCA, etc.).
