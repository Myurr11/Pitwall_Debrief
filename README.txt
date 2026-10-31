Pit Wall Debrief (live data)
1. Needs Python 3.8+ and internet. No packages to install.
2. In this folder run:  python3 pitwall.py
3. Your browser opens http://127.0.0.1:8765
4. Pick Season > Race weekend > Session (FP1/FP2/FP3/Sprint Quali/Sprint/Qualifying/Race) > Focus driver.
   On the Telemetry page pick the driver and the lap for A and B.
Data comes from the free OpenF1 API (api.openf1.org) and is cached in ./cache.
Delete ./cache to refetch. Very recent sessions may take a while to appear on OpenF1.

If you see "CERTIFICATE_VERIFY_FAILED" (common with Python on macOS):
  - run "Install Certificates.command" from /Applications/Python 3.x/, or  pip3 install certifi
  - or start with  python3 pitwall.py --insecure  (skips TLS checks; fine for public read-only data)
