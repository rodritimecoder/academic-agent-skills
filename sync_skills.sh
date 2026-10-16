#!/usr/bin/env bash
# sync_skills.sh — Synchronize and install academic-agent-skills
# Works standalone for any cloned instance of academic-agent-skills.
# Installs into ~/.gemini/config/skills and ~/.pi/agent/skills, and links ~/.local/bin launchers.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEMINI_HARNESS="$HOME/.gemini/config/skills"
PI_HARNESS="$HOME/.pi/agent/skills"
BIN_DIR="$HOME/.local/bin"

EXCLUDES=(
    --exclude "__pycache__"
    --exclude "*.pyc"
    --exclude ".venv"
    --exclude "node_modules"
    --exclude ".git"
    --exclude "README.md"
    --exclude "assets"
    --exclude ".env"
    --exclude ".env*"
    --exclude ".DS_Store"
    --exclude "Thumbs.db"
)

DO_PUSH=false
DO_PULL=false

for arg in "$@"; do
    case "$arg" in
        --push|-p)
            DO_PUSH=true
            ;;
        --pull|-u)
            DO_PULL=true
            ;;
        --status|-s)
            echo "📊 [academic-sync] Repository Status:"
            git -C "$SCRIPT_DIR" status --short
            exit 0
            ;;
    esac
done

if [ "$DO_PULL" = true ]; then
    echo "📥 [academic-sync] Pulling latest updates from GitHub..."
    git -C "$SCRIPT_DIR" pull origin main
fi

echo "🎓 [academic-sync] Installing Academic Skills from $SCRIPT_DIR..."

mkdir -p "$GEMINI_HARNESS" "$PI_HARNESS" "$BIN_DIR"

# Discover all skills in this repo (directories with SKILL.md)
for skill_dir in "$SCRIPT_DIR"/*/; do
    if [ -f "$skill_dir/SKILL.md" ]; then
        skill_name="$(basename "$skill_dir")"
        echo "  📦 Syncing skill: $skill_name"
        
        # Sync to Gemini / Antigravity harness
        mkdir -p "$GEMINI_HARNESS/$skill_name"
        rsync -avu "${EXCLUDES[@]}" "$skill_dir" "$GEMINI_HARNESS/$skill_name/" >/dev/null 2>&1
        
        # Sync to Pi harness
        mkdir -p "$PI_HARNESS/$skill_name"
        rsync -avu "${EXCLUDES[@]}" "$skill_dir" "$PI_HARNESS/$skill_name/" >/dev/null 2>&1
    fi
done

# Setup Launchers in ~/.local/bin
echo "🔗 [academic-sync] Configuring CLI launchers in $BIN_DIR..."

# 1. canvas-cli
if [ -f "$SCRIPT_DIR/canvas-cli/scripts/canvas_cli.py" ]; then
    ln -sf "$SCRIPT_DIR/canvas-cli/scripts/canvas_cli.py" "$BIN_DIR/canvas-cli"
    ln -sf "$SCRIPT_DIR/canvas-cli/scripts/canvas_cli.py" "$BIN_DIR/canvas"
    chmod +x "$SCRIPT_DIR/canvas-cli/scripts/canvas_cli.py"
fi

# 2. edstem-cli
if [ -f "$SCRIPT_DIR/edstem-cli/scripts/ed_cli.py" ]; then
    ln -sf "$SCRIPT_DIR/edstem-cli/scripts/ed_cli.py" "$BIN_DIR/edstem-cli"
    chmod +x "$SCRIPT_DIR/edstem-cli/scripts/ed_cli.py"
fi

# 3. cornell-notes
if [ -f "$SCRIPT_DIR/cornell-notes/format_notes.py" ]; then
    ln -sf "$SCRIPT_DIR/cornell-notes/format_notes.py" "$BIN_DIR/cornell-notes"
    chmod +x "$SCRIPT_DIR/cornell-notes/format_notes.py"
fi

# 4. zoom-recorder
if [ -f "$SCRIPT_DIR/zoom-recorder/scripts/zoom_download.py" ]; then
    ln -sf "$SCRIPT_DIR/zoom-recorder/scripts/zoom_download.py" "$BIN_DIR/zoom-recorder"
    chmod +x "$SCRIPT_DIR/zoom-recorder/scripts/zoom_download.py"
fi

# 5. okf-architect
if [ -f "$SCRIPT_DIR/okf-architect/scripts/okf_architect.py" ]; then
    ln -sf "$SCRIPT_DIR/okf-architect/scripts/okf_architect.py" "$BIN_DIR/okf-architect"
    ln -sf "$SCRIPT_DIR/okf-architect/scripts/okf_architect.py" "$BIN_DIR/okf"
    chmod +x "$SCRIPT_DIR/okf-architect/scripts/okf_architect.py"
fi

# 6. academic-icm
if [ -f "$SCRIPT_DIR/academic-icm/scripts/academic_icm.py" ]; then
    ln -sf "$SCRIPT_DIR/academic-icm/scripts/academic_icm.py" "$BIN_DIR/academic-icm"
    chmod +x "$SCRIPT_DIR/academic-icm/scripts/academic_icm.py"
fi

# 7. markitdown-cli
if [ -f "$SCRIPT_DIR/markitdown-cli/scripts/markitdown_cli.py" ]; then
    ln -sf "$SCRIPT_DIR/markitdown-cli/scripts/markitdown_cli.py" "$BIN_DIR/markitdown-cli"
    ln -sf "$SCRIPT_DIR/markitdown-cli/scripts/markitdown_cli.py" "$BIN_DIR/markitdown"
    chmod +x "$SCRIPT_DIR/markitdown-cli/scripts/markitdown_cli.py"
fi

if [ "$DO_PUSH" = true ]; then
    echo "🚀 [academic-sync] Committing and pushing updates to GitHub..."
    if [ -d "$SCRIPT_DIR/.git" ]; then
        cd "$SCRIPT_DIR"
        if [ -n "$(git status --porcelain)" ]; then
            git add -A
            git commit -m "sync: academic skills update [$(date -u +'%Y-%m-%dT%H:%M:%SZ')]"
            git push origin main
        else
            echo "✅ Working tree is already clean. Nothing to commit."
        fi
    fi
fi

echo "✅ All academic skills synchronized into harnesses and ~/.local/bin."
