#!/usr/bin/env bash
# Stage 3 step 2-4: run Zeek and Suricata over one IoT-23 pcap with Community ID.
# Linux only (WSL, Docker or a VM). Needs zeek >= 6.0 and suricata >= 7.0.
#
#   tools/run_sensors.sh <capture_dir>          (e.g. pcaps/CTU-IoT-Malware-Capture-8-1)
#
# Writes <cross_log>/sensor_out/<capture>/{zeek/conn.log,zeek/dns.log,suricata/eve.json}
# and appends tool versions to sensor_out/<capture>/versions.txt.
# The ET Open ruleset is downloaded ONCE into ruleset/ and then reused unchanged
# for every capture; its hash is checked on every call. Rules are never edited.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CAP_DIR="$(cd "$1" && pwd)"
CAP="$(basename "$CAP_DIR")"
# A <name>.trimmed.pcap (see src/trim_pcap.py) replaces a pcap with a truncated
# last record, which Zeek refuses to read.
PCAP="$(ls "$CAP_DIR"/*.trimmed.pcap 2>/dev/null | head -1 || true)"
[ -n "$PCAP" ] || PCAP="$(ls "$CAP_DIR"/*.pcap | head -1)"
OUT="$HERE/sensor_out/$CAP"
RS="$HERE/ruleset"
mkdir -p "$OUT/zeek" "$OUT/suricata" "$RS"

SURI_VER="$(suricata -V | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
if [ ! -f "$RS/emerging.rules.tar.gz" ]; then
  URL="https://rules.emergingthreats.net/open/suricata-${SURI_VER}/emerging.rules.tar.gz"
  curl -fsS -o "$RS/emerging.rules.tar.gz" "$URL"
  { echo "url=$URL"; echo "downloaded_utc=$(date -u +%FT%TZ)";
    echo "sha256=$(sha256sum "$RS/emerging.rules.tar.gz" | cut -d' ' -f1)"; } > "$RS/RULESET.txt"
  tar -xzf "$RS/emerging.rules.tar.gz" -C "$RS"
  cat "$RS"/rules/*.rules > "$RS/all.rules"
  echo "rules_version=$(cat "$RS/rules/version.txt" 2>/dev/null || echo unknown)" >> "$RS/RULESET.txt"
  echo "all_rules_sha256=$(sha256sum "$RS/all.rules" | cut -d' ' -f1)" >> "$RS/RULESET.txt"
fi
# Refuse to run if the ruleset changed since the first capture.
want="$(grep '^all_rules_sha256=' "$RS/RULESET.txt" | cut -d= -f2)"
have="$(sha256sum "$RS/all.rules" | cut -d' ' -f1)"
[ "$want" = "$have" ] || { echo "ruleset hash changed: $have != $want" >&2; exit 2; }

# Suricata config: the packaged default, with only Community ID switched on.
CONF_SRC="$(suricata --build-info | grep -oE '/[^ ]*suricata\.yaml' | head -1 || true)"
[ -f "$CONF_SRC" ] || CONF_SRC=/etc/suricata/suricata.yaml
sed 's/community-id: false/community-id: true/' "$CONF_SRC" > "$RS/suricata.yaml"
grep -q 'community-id: true' "$RS/suricata.yaml" || { echo "could not enable community-id" >&2; exit 3; }
sha256sum "$RS/suricata.yaml" > "$RS/suricata.yaml.sha256"

{ echo "capture=$CAP"; echo "pcap=$(basename "$PCAP")";
  echo "pcap_sha256=$(sha256sum "$PCAP" | cut -d' ' -f1)";
  echo "zeek=$(zeek --version)"; echo "suricata=$(suricata -V)";
  echo "run_utc=$(date -u +%FT%TZ)"; } > "$OUT/versions.txt"

# Zeek: -C ignores checksum errors (common in captures); community-id logging
# is built into Zeek >= 6.0.
( cd "$OUT/zeek" && zeek -C -r "$PCAP" policy/protocols/conn/community-id-logging \
    LogAscii::use_json=F )
# Suricata: offline pcap, checksum validation off (-k none), fixed rules only.
suricata -c "$RS/suricata.yaml" -S "$RS/all.rules" -k none -r "$PCAP" \
  -l "$OUT/suricata" --runmode single >/dev/null
grep -q '"community_id"' "$OUT/suricata/eve.json" || { echo "eve.json has no community_id" >&2; exit 4; }
grep -q 'community_id' "$OUT/zeek/conn.log" || { echo "conn.log has no community_id" >&2; exit 4; }
echo "done $CAP"
