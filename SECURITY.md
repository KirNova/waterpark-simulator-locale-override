# Security

This patcher performs a **single, deterministic modification** to the game’s localization asset (`resources.assets`) by replacing **one UTF-8 string with an equal byte-length string**.

It:

* does **not** install software
* does **not** run background services
* does **not** access the network
* does **not** collect or transmit data

The script operates entirely on local files.

---

## Transparency

If you have security concerns:

* review the source code in `patch_staff_only.py` before execution
* run the script **offline**
* verify the dry-run mode before applying changes

A **timestamped backup** of `resources.assets` is created automatically, allowing easy rollback at any time.

---

This repository distributes **no executable binaries** and **no game assets**.
