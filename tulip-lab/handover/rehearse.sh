#!/bin/bash
# The tiny rehearsal under the /train unit's limits: CPU only, 4 GiB of
# memory (cgroup), 512 tasks (cgroup), no network (own namespace), the
# venv's packages only (system copies of the vendored ones hidden).
# usage (as root, cgroup v1):
#   mkdir -p /sys/fs/cgroup/memory/tulip-rehearsal /sys/fs/cgroup/pids/tulip-rehearsal
#   echo 4294967296 > /sys/fs/cgroup/memory/tulip-rehearsal/memory.limit_in_bytes
#   echo 512 > /sys/fs/cgroup/pids/tulip-rehearsal/pids.max
#   mkdir run && (cd run && python3 -m zipfile -e ../tulip-package.zip .)
#   ./rehearse.sh run rehearsal-tiny.log
#   python3 returned.py run        # what the /train page would send back
set -u
DIR=$1; LOG=$2
CG=/sys/fs/cgroup
HERE=$(cd "$(dirname "$0")" && pwd)
echo $$ > $CG/memory/tulip-rehearsal/cgroup.procs
echo $$ > $CG/pids/tulip-rehearsal/cgroup.procs
echo 0 > $CG/memory/tulip-rehearsal/memory.max_usage_in_bytes
echo 0 > $CG/memory/tulip-rehearsal/memory.failcnt
cd "$DIR/tulip"
find . -type f -printf '%P\t%T@\n' | sort > "$DIR/before.txt"
export CUDA_VISIBLE_DEVICES="" PYTHONPATH="$HERE/hide" PYTHONDONTWRITEBYTECODE=1
unset HTTPS_PROXY HTTP_PROXY https_proxy http_proxy NO_PROXY no_proxy
# peak resident memory of the cgroup (rss, without the page cache)
( peak=0; while true; do
    r=$(awk '$1=="total_rss"{print $2}' $CG/memory/tulip-rehearsal/memory.stat)
    [ "$r" -gt "$peak" ] && peak=$r && echo $peak > "$DIR/peak_rss.txt"
    sleep 1; done ) &
SAMPLER=$!
start=$(date +%s)
unshare -n python3 build.py tiny > "$LOG" 2>&1
code=$?
end=$(date +%s)
kill $SAMPLER 2>/dev/null
find . -type f -printf '%P\t%T@\n' | sort > "$DIR/after.txt"
{
  echo "== exit $code after $((end - start)) s"
  echo "== cgroup memory peak (max_usage_in_bytes, with page cache): $(cat $CG/memory/tulip-rehearsal/memory.max_usage_in_bytes)"
  echo "== cgroup resident peak (total_rss, sampled each second): $(cat "$DIR/peak_rss.txt" 2>/dev/null)"
  echo "== memory limit hits (failcnt): $(cat $CG/memory/tulip-rehearsal/memory.failcnt)"
  grep -h oom_kill $CG/memory/tulip-rehearsal/memory.oom_control | sed 's/^/== /'
  echo "== pids peak: $(cat $CG/pids/tulip-rehearsal/pids.peak 2>/dev/null || echo n/a)"
} >> "$LOG"
