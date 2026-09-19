# Sourced by the session scripts. Defines the SSH access to the guest and the
# session log. $E must be set by the caller.
SSH_OPTS=(-i "$HOME/.ssh/egw_campaign" -p 2222 -o IdentitiesOnly=yes -o BatchMode=yes
          -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$E/boot/known_hosts"
          -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR)

gssh() { ssh "${SSH_OPTS[@]}" egw@127.0.0.1 "$@"; }
# scp takes -P for the port, ssh takes -p: the option lists are not interchangeable.
SCP_OPTS=(-i "$HOME/.ssh/egw_campaign" -P 2222 -o IdentitiesOnly=yes -o BatchMode=yes
          -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$E/boot/known_hosts"
          -o ConnectTimeout=10 -o LogLevel=ERROR)
gscp() { scp "${SCP_OPTS[@]}" "$@"; }
log()  { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$E/driver.log"; }
run_name() { cat "$E/.current_run" 2>/dev/null; }
