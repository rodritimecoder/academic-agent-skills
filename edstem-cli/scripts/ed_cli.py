#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

DEFAULT_BASE_URL = "https://edstem.org/api/"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

def load_env_file(filepath: Path) -> dict[str, str]:
    env_vars = {}
    if not filepath.is_file():
        return env_vars
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("\"'")
    except Exception:
        pass
    return env_vars

def get_config() -> tuple[str, str]:
    token = os.environ.get("ED_API_TOKEN")
    base_url = os.environ.get("ED_BASE_URL")

    candidates = [
        ENV_FILE,
        Path.home() / ".gemini/config/skills/edstem-cli/.env",
        Path.home() / ".pi/agent/skills/edstem-cli/.env",
        Path(".env"),
    ]

    for candidate in candidates:
        if candidate.is_file():
            file_vars = load_env_file(candidate)
            if not token:
                token = file_vars.get("ED_API_TOKEN")
            if not base_url:
                base_url = file_vars.get("ED_BASE_URL")
            if token and base_url:
                break

    if not base_url:
        base_url = DEFAULT_BASE_URL

    if not base_url.endswith("/"):
        base_url += "/"

    return token or "", base_url

def text_to_ed_xml(text: str) -> str:
    clean_text = text.strip()
    if clean_text.startswith("<document") and clean_text.endswith("</document>"):
        return clean_text

    paragraphs = clean_text.split("\n\n")
    xml_parts = ['<document version="2.0">']

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("```") and p.endswith("```"):
            lines = p.split("\n")
            lang = lines[0][3:].strip()
            code_content = "\n".join(lines[1:-1])
            escaped_code = html.escape(code_content)
            if lang:
                xml_parts.append(f'<code-block language="{html.escape(lang)}">{escaped_code}</code-block>')
            else:
                xml_parts.append(f'<code-block>{escaped_code}</code-block>')
        elif p.startswith("#"):
            match = re.match(r"^(#{1,6})\s+(.*)$", p)
            if match:
                level = len(match.group(1))
                h_text = html.escape(match.group(2))
                xml_parts.append(f'<heading level="{level}">{h_text}</heading>')
            else:
                xml_parts.append(f'<paragraph>{html.escape(p)}</paragraph>')
        else:
            escaped = html.escape(p).replace("\n", "<break/>")
            xml_parts.append(f'<paragraph>{escaped}</paragraph>')

    xml_parts.append("</document>")
    return "".join(xml_parts)

def ed_xml_to_plain_text(xml_string: str) -> str:
    if not xml_string:
        return ""
    if not xml_string.startswith("<document"):
        return xml_string
    try:
        root = ET.fromstring(xml_string)
        parts = []

        def traverse(node):
            tag = node.tag.lower()
            if tag == "paragraph":
                text = "".join(node.itertext()).strip()
                if text:
                    parts.append(text)
            elif tag == "heading":
                level = node.attrib.get("level", "1")
                text = "".join(node.itertext()).strip()
                prefix = "#" * int(level) if level.isdigit() else "#"
                parts.append(f"{prefix} {text}")
            elif tag == "code-block":
                code = "".join(node.itertext())
                parts.append(f"```\n{code}\n```")
            elif tag in ("document", "list", "list-item"):
                for child in node:
                    traverse(child)
            else:
                text = "".join(node.itertext()).strip()
                if text:
                    parts.append(text)

        traverse(root)
        return "\n\n".join(parts)
    except Exception:
        return re.sub(r"<[^>]+>", " ", xml_string).strip()

class EdClient:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url

    def _request(self, endpoint: str, method: str = "GET", params: dict | None = None, data: dict | None = None) -> dict:
        if not self.token:
            sys.stderr.write(
                "Error: ED_API_TOKEN is not set.\n"
                "Please generate a token from your Ed settings page:\n"
                "  - Australia / Global: https://edstem.org/settings/api-tokens\n"
                "  - US: https://edstem.org/us/settings/api-tokens\n"
                f"Then save it in {ENV_FILE} as ED_API_TOKEN=your_token\n"
            )
            sys.exit(1)

        clean_endpoint = endpoint.lstrip("/")
        full_url = urljoin(self.base_url, clean_endpoint)

        if params:
            valid_params = {k: v for k, v in params.items() if v is not None}
            if valid_params:
                full_url += ("&" if "?" in full_url else "?") + urlencode(valid_params)

        body = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "EdStem-CLI-Agent/1.0",
            "Accept": "application/json",
        }

        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(full_url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as resp:
                raw_response = resp.read().decode("utf-8")
                if not raw_response:
                    return {"status": "ok"}
                return json.loads(raw_response)
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            sys.stderr.write(f"HTTP Error {e.code} ({e.reason}) calling {full_url}\n")
            if err_body:
                sys.stderr.write(f"Server response: {err_body}\n")
            sys.exit(1)
        except URLError as e:
            sys.stderr.write(f"Network error calling {full_url}: {e.reason}\n")
            sys.exit(1)

def project_data(data: any, fields: list[str]) -> any:
    if isinstance(data, list):
        return [project_data(x, fields) for x in data]
    if isinstance(data, dict):
        return {k: data[k] for k in fields if k in data}
    return data

def format_table(data: list[dict], max_col_width: int = 40) -> str:
    if not data:
        return "No records found."
    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
        return json.dumps(data, indent=2)

    keys = list(data[0].keys())
    for item in data[1:]:
        for k in item.keys():
            if k not in keys:
                keys.append(k)

    headers = [str(k) for k in keys]
    rows = []
    for item in data:
        row = []
        for k in keys:
            val = item.get(k, "")
            if val is None:
                val = ""
            elif isinstance(val, (dict, list)):
                val = json.dumps(val)
            else:
                val = str(val).strip().replace("\n", " ")
            if len(val) > max_col_width:
                val = val[:max_col_width - 3] + "..."
            row.append(val)
        rows.append(row)

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "|-" + "-|-".join("-" * col_widths[i] for i in range(len(headers))) + "-|"
    row_lines = ["| " + " | ".join(r[i].ljust(col_widths[i]) for i in range(len(headers))) + " |" for r in rows]

    return "\n".join([header_line, sep_line] + row_lines)

def render_output(data: any, args: argparse.Namespace) -> None:
    limit = getattr(args, "limit", None)
    if limit is not None and isinstance(data, list):
        data = data[:limit]

    project_arg = getattr(args, "project", None)
    if project_arg:
        fields = [f.strip() for f in project_arg.split(",") if f.strip()]
        data = project_data(data, fields)

    out_file = getattr(args, "out", None)
    if out_file:
        p = Path(out_file)
        if p.parent:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2))
        receipt = {
            "status": "ok",
            "saved_to": str(p.resolve()),
            "count": len(data) if isinstance(data, list) else 1,
            "preview": data[:3] if isinstance(data, list) else data
        }
        print(json.dumps(receipt, indent=2))
        return

    fmt = getattr(args, "format", "json")
    if getattr(args, "table", False):
        fmt = "table"

    if fmt == "table" and isinstance(data, list) and data and isinstance(data[0], dict):
        print(format_table(data))
    elif fmt == "ids" and isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "id" in item:
                print(item["id"])
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, indent=2))

def cmd_user(client: EdClient, args: argparse.Namespace):
    res = client._request("user")
    user = res.get("user", {})
    realms = res.get("realms", [])
    courses = res.get("courses", [])

    if args.summary or args.table:
        render_output({
            "user_id": user.get("id"),
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role"),
            "realms": [r.get("name") for r in realms],
            "enrolled_course_count": len(courses)
        }, args)
    else:
        render_output(res, args)

def cmd_courses(client: EdClient, args: argparse.Namespace):
    res = client._request("user")
    course_entries = res.get("courses", [])

    courses_out = []
    for entry in course_entries:
        course = entry.get("course", {})
        role = entry.get("role", {}).get("role", "")
        courses_out.append({
            "id": course.get("id"),
            "code": course.get("code"),
            "name": course.get("name"),
            "year": course.get("year"),
            "session": course.get("session"),
            "role": role,
            "status": course.get("status")
        })

    if getattr(args, "summary", False) or getattr(args, "table", False) or getattr(args, "project", False):
        render_output(courses_out, args)
    else:
        render_output(course_entries, args)

def cmd_threads(client: EdClient, args: argparse.Namespace):
    params = {
        "limit": getattr(args, "limit", None) or 30,
        "offset": getattr(args, "offset", 0),
        "sort": getattr(args, "sort", "new"),
    }
    if getattr(args, "filter", None):
        params["filter"] = args.filter

    res = client._request(f"courses/{args.course_id}/threads", params=params)
    threads = res.get("threads", [])
    users = {u.get("id"): u.get("name") for u in res.get("users", [])}

    search_term = getattr(args, "search", None)
    if search_term:
        term = search_term.lower()
        threads = [
            t for t in threads
            if term in t.get("title", "").lower() or term in t.get("document", "").lower()
        ]

    compact = []
    for t in threads:
        compact.append({
            "id": t.get("id"),
            "number": t.get("number"),
            "type": t.get("type"),
            "category": t.get("category"),
            "title": t.get("title"),
            "author": users.get(t.get("user_id"), "Unknown"),
            "replies": t.get("reply_count"),
            "pinned": t.get("is_pinned"),
            "created_at": t.get("created_at")
        })

    if getattr(args, "summary", False) or getattr(args, "table", False) or getattr(args, "project", False):
        render_output(compact, args)
    else:
        render_output(res, args)

def cmd_thread(client: EdClient, args: argparse.Namespace):
    if args.course_id and args.number:
        endpoint = f"courses/{args.course_id}/threads/{args.number}"
    elif args.thread_id:
        endpoint = f"threads/{args.thread_id}"
    else:
        sys.stderr.write("Error: Must provide either <thread_id> or --course-id <id> with --number <num>\n")
        sys.exit(1)

    res = client._request(endpoint)
    thread = res.get("thread", {})

    if args.text_only:
        title = thread.get("title", "")
        category = thread.get("category", "")
        num = thread.get("number", "")
        body_text = ed_xml_to_plain_text(thread.get("content", ""))

        output = [
            f"=== [Thread #{num}] {title} ({category}) ===",
            f"Author ID: {thread.get('user_id')} | Date: {thread.get('created_at')}",
            "",
            body_text,
            "",
            f"--- Comments & Answers ({thread.get('reply_count', 0)}) ---"
        ]

        def dump_comments(comments_list, depth=0):
            indent = "  " * depth
            for c in comments_list:
                c_text = ed_xml_to_plain_text(c.get("content", ""))
                output.append(f"{indent}[Comment #{c.get('number')}] User {c.get('user_id')} ({c.get('created_at')}):")
                for line in c_text.splitlines():
                    output.append(f"{indent}  {line}")
                output.append("")
                if c.get("comments"):
                    dump_comments(c.get("comments"), depth + 1)

        dump_comments(thread.get("answers", []))
        dump_comments(thread.get("comments", []))
        print("\n".join(output))
    else:
        render_output(res, args)

def cmd_post(client: EdClient, args: argparse.Namespace):
    xml_content = text_to_ed_xml(args.content)
    payload = {
        "thread": {
            "type": args.type,
            "title": args.title,
            "category": args.category,
            "subcategory": args.subcategory or "",
            "subsubcategory": args.subsubcategory or "",
            "content": xml_content,
            "is_pinned": args.pinned,
            "is_private": args.private,
            "is_anonymous": args.anonymous,
            "is_megathread": False,
            "anonymous_comments": False,
        }
    }
    res = client._request(f"courses/{args.course_id}/threads", method="POST", data=payload)
    render_output(res, args)

def cmd_reply(client: EdClient, args: argparse.Namespace):
    xml_content = text_to_ed_xml(args.content)
    payload = {
        "comment": {
            "content": xml_content,
            "parent_id": args.parent_id,
            "is_anonymous": args.anonymous,
            "is_private": args.private
        }
    }
    res = client._request(f"threads/{args.thread_id}/comments", method="POST", data=payload)
    render_output(res, args)

def cmd_lock(client: EdClient, args: argparse.Namespace):
    res = client._request(f"threads/{args.thread_id}/lock", method="POST")
    render_output(res, args)

def cmd_unlock(client: EdClient, args: argparse.Namespace):
    res = client._request(f"threads/{args.thread_id}/unlock", method="POST")
    render_output(res, args)

def cmd_workspaces(client: EdClient, args: argparse.Namespace):
    res = client._request(f"courses/{args.course_id}/workspaces")
    workspaces = res.get("workspaces", [])
    users = {u.get("id"): u.get("name") for u in res.get("users", [])}

    out = []
    for ws in workspaces:
        uid = ws.get("user_id")
        out.append({
            "id": ws.get("id"),
            "title": ws.get("title"),
            "type": ws.get("type"),
            "author": users.get(uid, f"User {uid}"),
            "created_at": ws.get("created_at"),
            "opened_at": ws.get("opened_at"),
            "shared_at": ws.get("shared_at"),
        })

    search_term = getattr(args, "search", None)
    if search_term:
        term = search_term.lower()
        out = [w for w in out if term in w["title"].lower() or term in w["author"].lower()]

    if getattr(args, "summary", False) or getattr(args, "table", False) or getattr(args, "project", False):
        render_output(out, args)
    else:
        render_output(res, args)

def cmd_workspace(client: EdClient, args: argparse.Namespace):
    res = client._request(f"workspaces/{args.workspace_id}")
    if getattr(args, "connect", False):
        try:
            ticket_res = client._request(f"workspaces/{args.workspace_id}/connect", method="POST")
            res["ticket"] = ticket_res.get("ticket")
        except Exception as e:
            res["ticket_error"] = str(e)
    render_output(res, args)

def cmd_workspace_files(_client: EdClient, args: argparse.Namespace):
    ws_script = Path(__file__).parent / "ed_ws.js"
    res = subprocess.run([str(ws_script), "files", args.workspace_id], capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        sys.exit(res.returncode)
    print(res.stdout.strip())

def cmd_workspace_cat(_client: EdClient, args: argparse.Namespace):
    ws_script = Path(__file__).parent / "ed_ws.js"
    res = subprocess.run([str(ws_script), "cat", args.workspace_id, args.file_path], capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        sys.exit(res.returncode)
    sys.stdout.write(res.stdout)

def cmd_workspace_pull(_client: EdClient, args: argparse.Namespace):
    ws_script = Path(__file__).parent / "ed_ws.js"
    cmd = [str(ws_script), "pull", args.workspace_id]
    if getattr(args, "dest", None):
        cmd.append(args.dest)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        sys.exit(res.returncode)
    print(res.stdout.strip())

def cmd_workspace_sync(_client: EdClient, args: argparse.Namespace):
    ws_script = Path(__file__).parent / "ed_ws.js"
    dest = getattr(args, "dest", None) or f"workspace_{args.workspace_id}"
    cmd = [str(ws_script), "sync", args.workspace_id, dest]
    if getattr(args, "push", False):
        cmd.append("--push")
    if getattr(args, "once", False):
        cmd.append("--once")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[ed-sync] Watcher stopped.")

def cmd_lessons(client: EdClient, args: argparse.Namespace):
    res = client._request(f"courses/{args.course_id}/lessons")
    modules = {m.get("id"): m.get("name") for m in res.get("modules", [])}
    lessons = res.get("lessons", [])

    out = []
    for l in lessons:
        mid = l.get("module_id")
        out.append({
            "id": l.get("id"),
            "title": l.get("title"),
            "module": modules.get(mid, f"Module {mid}"),
            "kind": l.get("kind"),
            "due_at": l.get("due_at"),
            "slide_count": l.get("slide_count"),
        })

    search_term = getattr(args, "search", None)
    if search_term:
        term = search_term.lower()
        out = [x for x in out if term in x["title"].lower() or term in x["module"].lower()]

    if getattr(args, "summary", False) or getattr(args, "table", False) or getattr(args, "project", False):
        render_output(out, args)
    else:
        render_output(res, args)

def cmd_lesson(client: EdClient, args: argparse.Namespace):
    res = client._request(f"lessons/{args.lesson_id}")
    lesson = res.get("lesson", {})
    slides = lesson.get("slides", [])

    if getattr(args, "summary", False) or getattr(args, "table", False):
        slides_summary = []
        for s in slides:
            slides_summary.append({
                "id": s.get("id"),
                "title": s.get("title"),
                "type": s.get("type"),
                "challenge_id": s.get("challenge_id"),
                "content": ed_xml_to_plain_text(s.get("content", ""))[:300],
            })
        render_output({
            "id": lesson.get("id"),
            "title": lesson.get("title"),
            "due_at": lesson.get("due_at"),
            "slides": slides_summary,
        }, args)
    else:
        render_output(res, args)

def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--format", "-f", choices=["json", "table", "ids"], default=argparse.SUPPRESS, help="Output format")
    common_parser.add_argument("--table", "-t", action="store_true", default=argparse.SUPPRESS, help="Shorthand for --format table")
    common_parser.add_argument("--project", "-p", default=argparse.SUPPRESS, help="Comma-separated keys to project (e.g. id,title,category)")
    common_parser.add_argument("--out", "-o", default=argparse.SUPPRESS, help="Buffer full response to disk file and return concise receipt")
    common_parser.add_argument("--limit", "-n", type=int, default=argparse.SUPPRESS, help="Limit number of returned records")

    parser = argparse.ArgumentParser(
        prog="ed_cli.py",
        description="EdStem CLI - High Performance Deterministic Discussion & Course Gateway",
        epilog="Default output is JSON. Use --table, --project, or --out to shield context tokens.",
        parents=[common_parser]
    )
    parser.add_argument("--token", help="Override ED_API_TOKEN")
    parser.add_argument("--base-url", help="Override ED_BASE_URL (default: https://edstem.org/api/)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_user = subparsers.add_parser("user", help="Get authenticated user info", parents=[common_parser])
    p_user.add_argument("--summary", action="store_true", help="Print compact summary")

    p_courses = subparsers.add_parser("courses", help="List enrolled courses", parents=[common_parser])
    p_courses.add_argument("--summary", action="store_true", help="Print clean course list")

    p_threads = subparsers.add_parser("threads", help="List threads in a course", parents=[common_parser])
    p_threads.add_argument("course_id", type=int, help="Course ID")
    p_threads.add_argument("--offset", type=int, default=0, help="Pagination offset")
    p_threads.add_argument("--sort", default="new", choices=["new", "top", "unanswered"], help="Sort order")
    p_threads.add_argument("--filter", help="Thread filter (e.g. unread, starred)")
    p_threads.add_argument("--search", help="Search keyword in titles and content")
    p_threads.add_argument("--summary", action="store_true", help="Compact listing")

    p_thread = subparsers.add_parser("thread", help="View thread and its replies", parents=[common_parser])
    p_thread.add_argument("thread_id", type=int, nargs="?", help="Global thread ID")
    p_thread.add_argument("--course-id", type=int, help="Course ID (when using with --number)")
    p_thread.add_argument("--number", type=int, help="Course-relative thread number")
    p_thread.add_argument("--text-only", action="store_true", help="Render as clean plain text")

    p_post = subparsers.add_parser("post", help="Create a new thread")
    p_post.add_argument("course_id", type=int, help="Course ID")
    p_post.add_argument("--title", required=True, help="Thread title")
    p_post.add_argument("--content", required=True, help="Thread body (markdown or plain text)")
    p_post.add_argument("--category", default="General", help="Category name (default: General)")
    p_post.add_argument("--subcategory", help="Subcategory name")
    p_post.add_argument("--subsubcategory", help="Sub-subcategory name")
    p_post.add_argument("--type", default="post", choices=["post", "question", "announcement"], help="Thread type")
    p_post.add_argument("--private", action="store_true", help="Make thread private (staff-only)")
    p_post.add_argument("--anonymous", action="store_true", help="Post anonymously to peers")
    p_post.add_argument("--pinned", action="store_true", help="Pin thread (staff only)")

    p_reply = subparsers.add_parser("reply", help="Reply to a thread")
    p_reply.add_argument("thread_id", type=int, help="Thread ID")
    p_reply.add_argument("--content", required=True, help="Reply body text")
    p_reply.add_argument("--parent-id", type=int, help="Parent comment ID for nested replies")
    p_reply.add_argument("--anonymous", action="store_true", help="Post anonymously")
    p_reply.add_argument("--private", action="store_true", help="Make comment private")

    p_lock = subparsers.add_parser("lock", help="Lock a thread")
    p_lock.add_argument("thread_id", type=int, help="Thread ID")

    p_unlock = subparsers.add_parser("unlock", help="Unlock a thread")
    p_unlock.add_argument("thread_id", type=int, help="Thread ID")

    p_workspaces = subparsers.add_parser("workspaces", help="List workspaces in a course", parents=[common_parser])
    p_workspaces.add_argument("course_id", type=int, help="Course ID")
    p_workspaces.add_argument("--search", help="Search by workspace title or author")
    p_workspaces.add_argument("--summary", action="store_true", help="Print summary list")

    p_workspace = subparsers.add_parser("workspace", help="Inspect workspace details")
    p_workspace.add_argument("workspace_id", help="Workspace string ID")
    p_workspace.add_argument("--connect", action="store_true", help="Fetch connection ticket")

    p_ws_files = subparsers.add_parser("workspace-files", help="List live files inside workspace container")
    p_ws_files.add_argument("workspace_id", help="Workspace string ID")

    p_ws_cat = subparsers.add_parser("workspace-cat", help="Print file buffer from live workspace container")
    p_ws_cat.add_argument("workspace_id", help="Workspace string ID")
    p_ws_cat.add_argument("file_path", help="File path inside container (e.g. Makefile, archive.h)")

    p_ws_pull = subparsers.add_parser("workspace-pull", help="Download all files from workspace container")
    p_ws_pull.add_argument("workspace_id", help="Workspace string ID")
    p_ws_pull.add_argument("--dest", help="Destination directory path (default: ./workspace_<id>)")

    p_ws_sync = subparsers.add_parser("workspace-sync", help="Sync workspace with a local git repo (watch or single pass)")
    p_ws_sync.add_argument("workspace_id", help="Workspace string ID")
    p_ws_sync.add_argument("--dest", help="Destination directory path (default: ./workspace_<id>)")
    p_ws_sync.add_argument("--push", action="store_true", help="Auto git push on new commits")
    p_ws_sync.add_argument("--once", action="store_true", help="Run once and exit instead of continuous watcher")

    p_lessons = subparsers.add_parser("lessons", help="List modules and lessons in a course", parents=[common_parser])
    p_lessons.add_argument("course_id", type=int, help="Course ID")
    p_lessons.add_argument("--search", help="Search by lesson or module name")
    p_lessons.add_argument("--summary", action="store_true", help="Print summary list")

    p_lesson = subparsers.add_parser("lesson", help="Inspect lesson and challenge content", parents=[common_parser])
    p_lesson.add_argument("lesson_id", type=int, help="Lesson ID")
    p_lesson.add_argument("--summary", action="store_true", help="Print clean summary of slides")

    args = parser.parse_args()

    default_token, default_url = get_config()
    token = args.token or default_token
    base_url = args.base_url or default_url

    client = EdClient(token=token, base_url=base_url)

    cmd_map = {
        "user": cmd_user,
        "courses": cmd_courses,
        "threads": cmd_threads,
        "thread": cmd_thread,
        "post": cmd_post,
        "reply": cmd_reply,
        "lock": cmd_lock,
        "unlock": cmd_unlock,
        "workspaces": cmd_workspaces,
        "workspace": cmd_workspace,
        "workspace-files": cmd_workspace_files,
        "workspace-cat": cmd_workspace_cat,
        "workspace-pull": cmd_workspace_pull,
        "workspace-sync": cmd_workspace_sync,
        "lessons": cmd_lessons,
        "lesson": cmd_lesson,
    }

    handler = cmd_map.get(args.command)
    if handler:
        handler(client, args)

if __name__ == "__main__":
    main()
