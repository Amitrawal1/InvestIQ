#!/bin/bash
# Run the news pipeline automatically every 15 minutes with macOS launchd.
#
#   ./news_pipeline/schedule.sh install     # start the 15-minute schedule (also runs once now)
#   ./news_pipeline/schedule.sh status      # is it loaded? last exit code + recent log
#   ./news_pipeline/schedule.sh run-now     # trigger a run immediately
#   ./news_pipeline/schedule.sh uninstall   # stop and remove the schedule
#
# Missed runs (Mac asleep/off) are not a problem: every run catches up from the
# newest stored announcement.

set -euo pipefail

LABEL="com.investiq.news-pipeline"
ML_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ML_DIR/logs"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="${PYTHON:-$(command -v python3)}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-900}"
DOMAIN="gui/$(id -u)"

write_plist() {
  mkdir -p "$LOG_DIR" "$(dirname "$PLIST")"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>-m</string>
    <string>news_pipeline.run</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$ML_DIR</string>

  <key>StartInterval</key>
  <integer>$INTERVAL_SECONDS</integer>

  <key>RunAtLoad</key>
  <true/>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONWARNINGS</key>
    <string>ignore</string>
    <key>TOKENIZERS_PARALLELISM</key>
    <string>false</string>
    <!-- FinBERT is already cached: load it without network checks -->
    <key>HF_HUB_OFFLINE</key>
    <string>1</string>
  </dict>

  <key>ProcessType</key>
  <string>Background</string>
  <key>Nice</key>
  <integer>5</integer>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/launchd.err.log</string>
</dict>
</plist>
EOF
}

case "${1:-}" in
  install)
    write_plist
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Installed $LABEL: runs every $((INTERVAL_SECONDS / 60)) minutes using $PYTHON"
    echo "Logs: $LOG_DIR/news_pipeline.log"
    ;;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed $LABEL"
    ;;
  status)
    if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
      launchctl print "$DOMAIN/$LABEL" | grep -E "^\s+(state|runs|last exit code|run interval)" || true
    else
      echo "$LABEL is not installed"
    fi
    echo "--- recent log"
    tail -n 8 "$LOG_DIR/news_pipeline.log" 2>/dev/null || echo "(no log yet)"
    ;;
  run-now)
    launchctl kickstart -k "$DOMAIN/$LABEL"
    echo "Triggered $LABEL; follow with: tail -f $LOG_DIR/news_pipeline.log"
    ;;
  *)
    echo "Usage: $0 {install|status|run-now|uninstall}"
    exit 1
    ;;
esac
