# Collaboration API isolation and certificate caching

The service runs as `openvertaling`, with write access confined by systemd to `/var/lib/openvertaling-collaboration`. The installer stops the service before migrating ownership of the existing SQLite database and its journal files. Python application files remain root-owned.

Certificate downloads share a 60-second cooldown, including unknown key IDs and failed downloads. A cached, unexpired signing key is usable while another request refreshes certificates. Expired keys fail closed; a newly rotated key can trigger the next refresh once the cooldown expires. Concurrent cold-start requests share one download.

The installer also installs HTTP-context request and connection zones in `/etc/nginx/conf.d/openvertaling-collaboration-limits.conf`. The API location allows 20 requests/second with a burst of 40 and 20 simultaneous connections per client address. Exceeding either limit returns HTTP 429. Direct API binding remains on localhost.

Run `python3 -m unittest discover -s tests -p test_certificate_cache.py` and `python3 -m unittest discover -s tests -p test_collaboration_system.py` before deploying. The tests include RSA signatures, changed signatures, key rotation, failures, cache expiry, and concurrent refreshes.
