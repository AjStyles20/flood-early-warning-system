# Legacy Archive

This folder keeps older prototype files that are no longer part of the active FloodWatch implementation.

The archive exists for safety and traceability. It prevents accidental loss of earlier work while keeping the main project tree professional and easier to explain.

## Current archived items

- `old_new_folder_code/`
  - Older duplicate Python files originally stored in the root-level `New folder/`.
- `legacy_scripts/update_dashboard.py`
  - Older one-off script that targeted a static dashboard flow instead of the active FastAPI/Jinja2 application.

## Active implementation reminder

The current application is under:

```text
files/api/
```

Do not import from this archive or present archived files as active implementation unless they are intentionally restored and retested.
