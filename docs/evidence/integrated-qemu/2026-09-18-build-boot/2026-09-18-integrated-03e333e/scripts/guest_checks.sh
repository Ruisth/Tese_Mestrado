# Runbook section 3.4: acceptance inside the guest. Fed to 'sh -s' over SSH as
# the operator 'egw'. Every command is echoed before its output.
run() { echo; echo "\$ $*"; "$@" 2>&1; echo "[exit=$?]"; }
echo "### system"
run systemctl is-system-running
run systemctl --failed --no-legend
run uname -a
run head -n 4 /etc/os-release
run cat /etc/hostname
echo "### memory"
run free -m
run head -n 1 /proc/meminfo
run cat /proc/cmdline
echo "### cpu"
run nproc
run grep -m1 '^CPU part' /proc/cpuinfo
run grep -m1 '^Features' /proc/cpuinfo
echo "### storage"
run df -h / /var/lib/docker /opt/egw
run findmnt /var/lib/docker
run findmnt -no SOURCE,FSTYPE,OPTIONS /
run lsblk
run sudo -n blkid
run systemctl is-active docker var-lib-docker.mount
run systemctl status systemd-growfs@var-lib-docker.service --no-pager
run systemctl show -p Requires,After docker.service
echo "### container runtime"
run docker info
run docker compose version
run docker version
run docker ps -a
run docker images
run findmnt -no FSTYPE /sys/fs/cgroup
echo "### network, dns, time"
run ip -o addr show
run cat /etc/resolv.conf
run nslookup registry-1.docker.io
run timedatectl
run timedatectl show
run date -u
run sh -c 'ss -ltnu 2>/dev/null || netstat -ltnu'
echo "### journal and logs"
run findmnt -no SOURCE,FSTYPE /var/log
run ls -ld /var/log /var/log/journal
run sudo -n journalctl --disk-usage
run sudo -n journalctl --list-boots --no-pager
echo "### operator access and permissions"
run id
run ls -ld /opt/egw /opt/egw/data /opt/egw/data/events /home/egw /home/egw/.ssh
run sh -c 'command -v curl openssl sudo resize2fs e2fsck docker'
run ls -l /usr/libexec/sftp-server
run grep -i '^Subsystem' /etc/ssh/sshd_config
run sudo -n visudo -c
run sudo -n -l
run sudo -n sshd -T
