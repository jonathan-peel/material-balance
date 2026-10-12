#!/bin/bash -l
# run_cluster.sh: Solve prepared PyPSA-Eur networks on the cluster. Automates
# README steps 3-5: load environment, touch the prepared inputs so upstream
# rules don't re-run, then build collect_solved_networks -- which produces each
# cost-optimal solve AND every configured MGA re-solve (pypsa.mga.scenarios:
# e.g. min wind, min solar, max nuclear), since MGA reads the solved networks
# and Snakemake orders solve-then-mga automatically.
# Usage: ./run_cluster.sh

PROFILE="profiles/cluster"
LOG_FILE="$(date +%m%d_%H%M%S).log"

TOUCH_TARGET="collect_prepared_networks"
RUN_TARGET="collect_solved_networks"

# --- pre-launch checks: run in the visible terminal BEFORE going detached ---
# Anything that prompts or errors inside the tmux session is invisible until
# you attach, so do the lock check and arch confirmation here, up front.
if [[ -z "$TMUX" ]]; then
  # Lock check: fail fast before committing to a detached run.
  if [[ -d ".snakemake/locks" ]] && [[ "$(ls -A .snakemake/locks)" ]]; then
    echo "Error: The Snakemake directory is locked."
    echo "This usually happens if a previous run crashed or was killed."
    echo "To fast-unlock it, run: rm -f .snakemake/locks/*"
    echo "Then try this script again."
    exit 1
  fi

  # Confirm the config architecture. yaml isn't on the base env here, so read
  # the value with grep and just ask to confirm.
  CONFIG_ARCH=$(grep -E '^[[:space:]]*env_architecture:' config/default.yaml 2>/dev/null | head -1 | awk '{print $2}')
  echo "config/default.yaml has pypsa.env_architecture: ${CONFIG_ARCH:-<unreadable>}"
  echo "This must match THIS machine (e.g. linux-64 on a cluster)."
  read -rp "Is it set correctly for this host? [y/N] " arch_reply
  if [[ ! "$arch_reply" =~ ^[Yy]$ ]]; then
    echo "Aborting. Update pypsa.env_architecture in config/default.yaml and retry."
    exit 1
  fi

  SESSION="solve_$(date +%m%d_%H%M%S)"
  CMD=$(printf '%q ' "$0" "$@")
  tmux new-session -d -s "$SESSION" "bash -l $CMD; echo \"EXIT \$?\"; read"
  echo "Launched in tmux session '$SESSION'. Attach with: tmux attach -t $SESSION"
  exit 0
fi

# --- environment -----------------------------------------------------------
echo "Preparing environment..."
module load gurobi
conda activate metal-pypsa

mkdir -p cluster_logs
LOG="cluster_logs/$LOG_FILE"

echo "Running solve (+ MGA) on the cluster."
echo "Profile:   $PROFILE"
echo "Redirecting output to $LOG"

# Visual confirmation written immediately into the log file
{
  echo "========================================"
  echo "Snakemake solve run started."
  echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Node:      $USER@$(hostname):$(pwd)"
  echo "Profile:   $PROFILE"
  echo "Target:    $RUN_TARGET"
  echo "========================================"
  echo ""
} > "$LOG"

# --- guard against upstream reruns -----------------------------------------
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Dry run to confirm the DAG..." | tee -a "$LOG"
snakemake "$RUN_TARGET" -n --profile "$PROFILE" >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Touching $TOUCH_TARGET so its outputs count as up-to-date..." | tee -a "$LOG"
snakemake "$TOUCH_TARGET" --touch --profile "$PROFILE" >> "$LOG" 2>&1

# --- run -------------------------------------------------------------------
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running: snakemake $RUN_TARGET --profile $PROFILE" | tee -a "$LOG"
snakemake "$RUN_TARGET" --profile "$PROFILE" >> "$LOG" 2>&1
SNAKEMAKE_EXIT=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Snakemake has stopped (exit $SNAKEMAKE_EXIT)." | tee -a "$LOG"

# --- email notification ----------------------------------------------------
if [[ $SNAKEMAKE_EXIT -eq 0 ]]; then
  STATUS="SUCCESS"
else
  STATUS="FAILED (exit $SNAKEMAKE_EXIT)"
fi

RUN_HOST=$(hostname)
RUN_TIME=$(date '+%Y-%m-%d %H:%M:%S')

python3 - <<EOF
import smtplib
from email.message import EmailMessage
msg = EmailMessage()
msg["Subject"] = "FINISHED: solve $STATUS ($LOG_FILE)"
msg["From"]    = "$USER@ethz.ch"
msg["To"]      = "$USER@ethz.ch"
msg.set_content("""solve run finished on $RUN_HOST at $RUN_TIME.

Target:  $RUN_TARGET
Profile: $PROFILE
Status:  $STATUS
Log:     $LOG
""")
with smtplib.SMTP("localhost", 25, timeout=5) as smtp:
    smtp.sendmail(msg["From"], [msg["To"]], msg.as_string())
EOF

echo "Email notification sent to $USER@ethz.ch" | tee -a "$LOG"
echo "Run complete with status: $STATUS. Check $LOG for details." | tee -a "$LOG"
