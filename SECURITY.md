# Security

This repository includes two scripts:

* `patch_staff_only.py`: applies **deterministic, byte-length preserved** changes to
  `resources.assets` based on `key_map.json`.
* `inspect_assets.py`: read-only inspection helpers (dump/search/list), with an optional
  diagnostic language-order fix that also preserves file size and creates a backup.

Both tools:

* do **not** install software
* do **not** run background services
* do **not** access the network
* do **not** collect or transmit data

The scripts operate entirely on local files.

---

## Transparency

If you have security concerns:

* review the source code in `patch_staff_only.py` and `inspect_assets.py` before execution
* run the scripts **offline**
* verify the dry-run mode before applying any changes

A **timestamped backup** of `resources.assets` is created automatically, allowing easy
rollback at any time.

---

This repository distributes **no executable binaries** and **no game assets**.
