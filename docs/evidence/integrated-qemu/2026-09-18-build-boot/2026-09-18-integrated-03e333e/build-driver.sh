#!/bin/bash
cd /home/ruisth/yocto/egw/src/yocto
date -u +%Y-%m-%dT%H:%M:%SZ > "/home/ruisth/yocto/evidence-candidates/2026-09-18-integrated-03e333e/build.started"
EGW_AUTHORIZED_KEYS_FILE=$HOME/.ssh/egw_campaign.pub ./scripts/build-profile.sh integrated > "/home/ruisth/yocto/evidence-candidates/2026-09-18-integrated-03e333e/build-driver.log" 2>&1
echo "exit=$? finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "/home/ruisth/yocto/evidence-candidates/2026-09-18-integrated-03e333e/build.status"
