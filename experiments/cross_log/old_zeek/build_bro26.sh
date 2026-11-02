#!/usr/bin/env bash
# Build Bro 2.6.4 (the Zeek generation used for IoT-23's logs) into /opt/bro26.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq --no-install-recommends build-essential gcc-9 g++-9 cmake make \
  flex bison libpcap-dev libssl-dev zlib1g-dev swig python3 gnupg dirmngr >/dev/null
# Signature check (best effort; result is logged either way).
KEY=$(gpg --list-packets "$HERE/bro-2.6.4.tar.gz.asc" 2>/dev/null | grep -oE 'keyid [0-9A-F]+' | awk '{print $2}' | head -1)
echo "signature keyid: $KEY"
gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$KEY" 2>&1 | tail -2 || true
gpg --batch --verify "$HERE/bro-2.6.4.tar.gz.asc" "$HERE/bro-2.6.4.tar.gz" 2>&1 | tail -3 || true
rm -rf /root/build && mkdir -p /root/build && cd /root/build
tar -xzf "$HERE/bro-2.6.4.tar.gz" && cd bro-2.6.4
export CC=gcc-9 CXX=g++-9
./configure --prefix=/opt/bro26 --disable-broctl --disable-python --disable-auxtools \
  --disable-broker-tests --build-type=Release
make -j16
make install
/opt/bro26/bin/bro --version
