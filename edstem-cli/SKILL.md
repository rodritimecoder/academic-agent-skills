---
name: edstem-cli
description: "Interact with Ed Discussion and Ed Courses: list courses, search forum threads, view thread discussions and answers, post questions, reply to classmates or tutors, and inspect course announcements. Use when asked about Ed, EdStem, forum threads, course discussions, or student Q&A."
---

# EdStem CLI Skill

Fetch course discussions, search threads, retrieve answers/comments, post questions, and interact with the EdStem platform.

## Setup

Requires `ED_API_TOKEN` (and optional `ED_BASE_URL`), read from the environment or from a `.env` file in the skill directory (`~/.gemini/config/skills/edstem-cli/.env`):

```bash
# Get your token at:
#   - Australia / Global (UTS, USYD, UNSW, etc.): https://edstem.org/settings/api-tokens
#   - US: https://edstem.org/us/settings/api-tokens
ED_API_TOKEN=your_ed_api_token
```

By default, requests route to `https://edstem.org/api/` (Australia / Global). To use the US endpoint, set:
```bash
ED_BASE_URL=https://us.edstem.org/api/
```

## Usage

Run the CLI using python3:

```bash
CLI=~/.gemini/config/skills/edstem-cli/scripts/ed_cli.py
python3 $CLI <command> [args]
```

### Deterministic Token Shielding (Kem Glitch Architecture)
To eliminate context bloat and token exhaust in agent loops, always use deterministic projection:
- `--table` (`-t`): Formats output as a high-density Markdown table (**~98% token reduction** on thread lists).
- `--project <keys>` (`-p`): Strictly limits fields to a comma-separated list (e.g. `--project id,title,replies`).
- `--out <file>` (`-o`): Buffers bulk thread/lesson payloads to disk and prints a concise 1-line receipt with preview.
- `--limit <N>` (`-n`): Caps the number of returned records (default: 30).
- `--format [table|json|ids]`: Select exact rendering format.

## Available Commands

### 1. User & Course Discovery
Find your courses and course IDs first:

```bash
# Authenticated user profile and organization
python3 $CLI user --summary

# List all enrolled courses as a compact table
python3 $CLI courses --table

# Project strictly course ID and code
python3 $CLI courses --project id,code --table
```

### 2. Thread Browsing & Search
Browse or search discussions in a specific course without blowing up context:

```bash
# List recent threads rendered as a dense Markdown table (only ~350 tokens!)
python3 $CLI threads <course_id> --table

# Search threads by keyword and format as table
python3 $CLI threads <course_id> --search "assignment 3" --table

# Project strictly thread ID and title
python3 $CLI threads <course_id> --project id,title --table

# Buffer 50 threads to disk to keep agent context clean
python3 $CLI threads <course_id> --limit 50 --out /tmp/all_threads.json
```

### 3. Reading Thread Discussions
View thread content, code snippets, and comments/replies:

```bash
# View thread content and comment tree as readable clean text
python3 $CLI thread <thread_id> --text-only

# View by course thread number (e.g. Post #42)
python3 $CLI thread --course-id <course_id> --number 42 --text-only

# Full raw JSON payload
python3 $CLI thread <thread_id>
```

### 4. Posting & Replying
Create new threads or comment on existing threads (automatically converted to Ed's XML format):

```bash
# Post a question or discussion thread
python3 $CLI post <course_id> \
  --title "Question about Assignment 3 sorting constraints" \
  --content "Does sort.c need to support duplicate timestamps?" \
  --category "Assignments" \
  --type question

# Post anonymously or make it private (staff-only)
python3 $CLI post <course_id> \
  --title "Private feedback on rubric" \
  --content "Is the report due date firm?" \
  --private

# Reply to an existing thread
python3 $CLI reply <thread_id> \
  --content "I tested this locally with make test and it passes all test cases."
```

### 5. Workspaces & Cloud IDE
Discover and inspect course workspaces (e.g. shared student/tutor IDE instances):

```bash
# List all workspaces in a course
python3 $CLI workspaces <course_id> --summary

# Search workspaces by title or author (e.g. "Assessment 3" or "Tim")
python3 $CLI workspaces <course_id> --search "Tim" --summary

# Inspect workspace details and obtain real-time connection ticket
python3 $CLI workspace <workspace_id> --connect

# Stream real-time file tree from live workspace container
python3 $CLI workspace-files <workspace_id>

# Read code directly from container buffer without downloading
python3 $CLI workspace-cat <workspace_id> archive.h

# Pull full workspace tree to local directory
python3 $CLI workspace-pull <workspace_id> --dest ./my_assessment_3

# Live sync workspace to Git (continuous watch daemon with auto-commits)
python3 $CLI workspace-sync <workspace_id> --dest ./my_assessment_3 --push

# Single-pass sync and git commit (run once and exit)
python3 $CLI workspace-sync <workspace_id> --dest ./my_assessment_3 --once
```

### 6. Lessons & Programming Challenges
Explore course modules, lab lessons, and assignment specifications:

```bash
# List all modules and lessons (quizzes, labs, assignments)
python3 $CLI lessons <course_id> --summary

# Inspect a specific lesson and view slide/challenge content
python3 $CLI lesson <lesson_id> --summary
```
