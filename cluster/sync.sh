#!/bin/bash -l
# sync.sh: rsync the repo between local and the cluster.
# Usage: cluster/sync.sh {send|receive} [--dry-run|-n]
#   send    : local  -> cluster  (.sync-send filter,   exact mirror: deletes
#             everything on the cluster not sent, incl. excluded/stale files
#             like old .snakemake state and previous solve outputs)
#   receive : cluster -> local    (.sync-receive filter, additive, no --delete)

source cluster/config/sync.env

case "$1" in
    send)
        SRC="."
        DEST="${CLUSTER_URL}:${CLUSTER_DIR}"
        FILTER="${IGNORE_FILE}"
        DELETE="--delete --delete-excluded"  # exact mirror: wipe stale cluster files too
        ;;
    receive)
        SRC="${CLUSTER_URL}:${CLUSTER_DIR}/"
        DEST="."
        FILTER="${RECEIVE_FILE}"
        DELETE=""   # additive: never delete local files when pulling back
        ;;
    *) echo "Usage: $0 {send|receive} [--dry-run|-n]"; exit 1 ;;
esac

DRY_RUN=""
case "$2" in
    --dry-run|-n) DRY_RUN="--dry-run" ;;
    "") ;;
    *) echo "Usage: $0 {send|receive} [--dry-run|-n]"; exit 1 ;;
esac

[ -n "$DRY_RUN" ] && echo "[DRY RUN]"

# Warn before a real send: it wipes cluster files not sent, including any solve
# outputs you may not have pulled back yet.
if [[ "$1" == "send" && -z "$DRY_RUN" ]]; then
    echo "WARNING: 'send' mirrors local -> cluster and DELETES anything on the"
    echo "cluster that isn't sent, including solve results you may want to"
    echo "'receive' first. This cannot be undone."
    read -r -p "Continue? [y/N] " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "Syncing ${SRC} -> ${DEST} ..."
rsync -avzh ${DRY_RUN} ${DELETE} --checksum --progress --no-p --no-g --chmod=ugo=rwX \
    --exclude-from="${FILTER}" \
    "${SRC}" "${DEST}"
RSYNC_EXIT=$?

# After a successful real receive, mark the pulled solve outputs as up-to-date
# so local snakemake doesn't try to re-solve them (covers clock skew and
# non-mtime rerun triggers). Mirrors the --touch step in run_cluster.sh.
# collect_solved_networks now covers the MGA re-solves too, so this one touch
# marks solved + mga up-to-date in dependency order; the received files already
# exist, so --touch never fabricates empty ones.
if [[ "$1" == "receive" && -z "$DRY_RUN" && $RSYNC_EXIT -eq 0 ]]; then
    echo "Touching solved + MGA networks so snakemake treats them as up-to-date ..."
    conda activate metal-snapshots
    # --rerun-incomplete clears stale "incomplete" markers left by an aborted
    # local solve attempt, which would otherwise block the touch.
    snakemake collect_solved_networks --touch --rerun-incomplete
fi

exit $RSYNC_EXIT
