#!/usr/bin/env bash
# Runs the unchanged run_sensors.sh over the v3 captures (inside WSL).
set -euo pipefail
export PATH=/opt/zeek/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd "$(dirname "$0")/.."
date -u +%FT%TZ
for c in CTU-IoT-Malware-Capture-36-1 CTU-IoT-Malware-Capture-7-1; do
  tools/run_sensors.sh "pcaps/$c"
  date -u +%FT%TZ
done
