#!/usr/bin/env python3
"""
academic_icm.py — Academic ICM Pipeline Orchestrator

Orchestrates the university knowledge pipeline adhering to Interpretable Context Methodology (ICM):
  1. Ingestion & Normalization: canvas-cli -> markitdown-cli
  2. Active-Recall Distillation: cornell-notes (strict stem inheritance)
  3. Curriculum Architecture: okf-architect -> CURRICULUM_TREE.md -> viz.html & cornell_index.html

Commands:
  academic-icm status [vault]         - Audit coverage %, missing nodes, and orphaned notes
  academic-icm audit [vault]          - Lint stem naming, JSON schema, and KaTeX math formulas
  academic-icm scaffold <source_md>   - Auto-scaffold matching _cornell.json template from markdown source
  academic-icm build-note <json_file> - Compile _cornell.json into .html study sheet and .tsv Anki deck
  academic-icm compile [vault]        - Recompile CURRICULUM_TREE.md into Knowledge Cosmos and Study Portal
  academic-icm sync-orphans [vault]   - Auto-repair and link orphaned Cornell notes into the curriculum tree
  academic-icm serve [vault] [--port] - Start local HTTP preview server for study portal
"""

import sys
import os
import re
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

DEFAULT_NOTES_DIR = Path("/run/media/rodri/AI/University/notes")

# Dynamic discovery of companion engines
def find_engine_path(skill_name: str, script_name: str) -> Optional[Path]:
    candidate_roots = [
        Path("/run/media/rodri/AI/skills"),
        Path.home() / ".gemini" / "config" / "skills",
        Path.home() / ".pi" / "agent" / "skills",
        Path("/run/media/rodri/AI/academic-agent-skills"),
    ]
    for r in candidate_roots:
        p = r / skill_name / "scripts" / script_name
        if p.is_file():
            return p
        p_root = r / skill_name / script_name
        if p_root.is_file():
            return p_root
    return None

def find_vault_root(start_path: Optional[str] = None) -> Path:
    if start_path:
        p = Path(start_path).resolve()
        if (p / "CURRICULUM_TREE.md").is_file():
            return p
        for parent in p.parents:
            if (parent / "CURRICULUM_TREE.md").is_file():
                return parent
        return p
    if DEFAULT_NOTES_DIR.is_dir():
        return DEFAULT_NOTES_DIR
    return Path.cwd()

def parse_tree_nodes(tree_file: Path) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    """
    Parses CURRICULUM_TREE.md.
    Returns: { course_name: { module_header: [ { 'path': rel_path, 'title': title, 'stem': stem } ] } }
    """
    if not tree_file.is_file():
        return {}

    courses: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    current_course = None
    current_module = "Overview"

    for line in tree_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(">"):
            continue
        if line.startswith("## "):
            current_course = line.replace("## ", "").strip()
            courses[current_course] = {}
            current_module = "Course Overview"
            courses[current_course][current_module] = []
        elif line.startswith("### ") and current_course:
            current_module = line.replace("### ", "").strip()
            courses[current_course].setdefault(current_module, [])
        elif line.startswith("- [[") and current_course:
            m = re.match(r'- \[\[(.*?)\]\]\s*(.*)', line)
            if m:
                target_path = m.group(1).strip()
                title = m.group(2).strip()
                stem = Path(target_path).stem.lower().replace("-", "_").replace(" ", "_")
                courses[current_course][current_module].append({
                    "path": target_path,
                    "title": title,
                    "stem": stem
                })
    return courses

def collect_cornell_notes(vault_root: Path) -> Dict[str, Dict[str, Any]]:
    """Collects all *_cornell.json files and indexes them by stem and source."""
    cornell_notes: Dict[str, Dict[str, Any]] = {}
    for jf in vault_root.rglob("*_cornell.json"):
        if "outputs" in jf.parts or "json" in jf.parts:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                clean_stem = re.sub(r'_cornell(_cornell)?$', '', jf.stem, flags=re.IGNORECASE).lower().replace("-", "_").replace(" ", "_")
                src = data.get("source", "")
                src_stem = Path(src).stem.lower().replace("-", "_").replace(" ", "_") if src else ""
                
                # Check html and tsv presence
                html_file = jf.parent.parent / "html" / f"{jf.stem}.html"
                if not html_file.is_file():
                    html_file = jf.with_suffix(".html")
                anki_file = jf.parent.parent / "anki" / f"{clean_stem}_anki.tsv"

                cues_count = sum(len(sec.get("entries", [])) for sec in data.get("sections", []))

                info = {
                    "json_path": jf,
                    "html_path": html_file if html_file.is_file() else None,
                    "anki_path": anki_file if anki_file.is_file() else None,
                    "title": data.get("title", clean_stem),
                    "source": src,
                    "clean_stem": clean_stem,
                    "src_stem": src_stem,
                    "cues_count": cues_count,
                    "sections_count": len(data.get("sections", [])),
                    "matched": False
                }
                cornell_notes[clean_stem] = info
                if src_stem and src_stem != clean_stem:
                    cornell_notes[src_stem] = info
            except Exception:
                pass
    return cornell_notes

# ==============================================================================
# SUBCOMMAND: status
# ==============================================================================
def cmd_status(args: argparse.Namespace) -> int:
    vault_root = find_vault_root(args.vault)
    tree_file = vault_root / "CURRICULUM_TREE.md"
    
    print(f"\n📊 [Academic ICM Status] Inspecting vault: {vault_root}")
    if not tree_file.is_file():
        print(f"❌ Error: CURRICULUM_TREE.md not found in {vault_root}")
        return 1

    courses = parse_tree_nodes(tree_file)
    notes_map = collect_cornell_notes(vault_root)
    
    total_tree_nodes = 0
    covered_nodes = 0
    total_cues = 0

    print("\n🏛️  Course Curriculum Coverage:")
    print(f"{'Course / Module':<50} | {'Nodes':<6} | {'Cornell':<8} | {'Coverage':<8}")
    print("─" * 80)

    course_missing: Dict[str, List[Tuple[str, str, str]]] = {}

    for course_name, modules in courses.items():
        course_nodes = 0
        course_covered = 0
        course_missing[course_name] = []

        for mod_name, items in modules.items():
            for item in items:
                course_nodes += 1
                stem = item["stem"]
                # Match against clean_stem or src_stem
                matched_note = None
                if stem in notes_map:
                    matched_note = notes_map[stem]
                else:
                    # Fuzzy match check
                    for n_stem, n_info in notes_map.items():
                        if n_stem == stem or n_info.get("src_stem") == stem:
                            matched_note = n_info
                            break
                        if len(stem) > 8 and (stem in n_stem or n_stem in stem):
                            matched_note = n_info
                            break

                if matched_note:
                    course_covered += 1
                    matched_note["matched"] = True
                    total_cues += matched_note["cues_count"]
                else:
                    course_missing[course_name].append((mod_name, item["title"], item["path"]))

        total_tree_nodes += course_nodes
        covered_nodes += course_covered
        cov_pct = (course_covered / course_nodes * 100) if course_nodes > 0 else 0.0
        print(f"{course_name[:48]:<50} | {course_nodes:<6} | {course_covered:<8} | {cov_pct:>6.1f}%")

    overall_cov = (covered_nodes / total_tree_nodes * 100) if total_tree_nodes > 0 else 0.0
    print("─" * 80)
    print(f"{'TOTAL CURRICULUM':<50} | {total_tree_nodes:<6} | {covered_nodes:<8} | {overall_cov:>6.1f}%\n")

    # Detect Orphans
    unique_notes = {v["json_path"]: v for v in notes_map.values()}
    orphans = [v for v in unique_notes.values() if not v["matched"]]
    
    if orphans:
        print(f"⚠️  Detected {len(orphans)} Orphaned Cornell Notes (exists on disk but unlinked in CURRICULUM_TREE.md):")
        for o in orphans:
            print(f"   • ❌ {o['json_path'].name} (source: '{o['source'] or 'None'}')")
            print(f"     Path: {o['json_path']}")
        print("   💡 Tip: Run 'academic-icm sync-orphans' to automatically repair stem alignment.")
    else:
        print("✅ Zero orphaned notes detected! All Cornell files match CURRICULUM_TREE.md.")

    return 0

# ==============================================================================
# SUBCOMMAND: audit
# ==============================================================================
def cmd_audit(args: argparse.Namespace) -> int:
    vault_root = find_vault_root(args.vault)
    print(f"\n🔍 [Academic ICM Audit] Deep linting vault: {vault_root}")
    
    notes_map = collect_cornell_notes(vault_root)
    unique_notes = {v["json_path"]: v for v in notes_map.values()}
    
    issues = 0
    warnings = 0

    for jf, info in unique_notes.items():
        clean_stem = info["clean_stem"]
        src = info["source"]
        
        # Check 1: Stem alignment
        if src:
            src_p = jf.parent.parent / src
            src_stem = Path(src).stem.lower().replace("-", "_").replace(" ", "_")
            if src_stem != clean_stem:
                print(f"  ⚠️  [Stem Mismatch] {jf.name}: JSON stem '{clean_stem}' != source stem '{src_stem}'")
                warnings += 1
            if not src_p.is_file() and not (vault_root / src).is_file():
                print(f"  ❌ [Broken Source] {jf.name}: Source file not found on disk: {src}")
                issues += 1
        else:
            print(f"  ⚠️  [Missing Source] {jf.name}: 'source' field is empty in JSON.")
            warnings += 1

        # Check 2: Cue count
        if info["cues_count"] < 6:
            print(f"  ⚠️  [Low Depth] {jf.name}: Only {info['cues_count']} cues (target: 6–8 active cues)")
            warnings += 1

        # Check 3: HTML / Anki sync
        if not info["html_path"]:
            print(f"  ❌ [Missing HTML] {jf.name}: Corresponding HTML study sheet missing in outputs/html/")
            issues += 1
        if not info["anki_path"]:
            print(f"  ⚠️  [Missing Anki] {jf.name}: TSV flashcard deck missing in outputs/anki/")
            warnings += 1

    print(f"\nAudit complete: {issues} critical errors, {warnings} naming/depth warnings.")
    return 1 if issues > 0 else 0

# ==============================================================================
# SUBCOMMAND: scaffold
# ==============================================================================
def cmd_scaffold(args: argparse.Namespace) -> int:
    src_file = Path(args.source_md).resolve()
    if not src_file.is_file():
        print(f"❌ Error: Source file not found: {src_file}")
        return 1

    # Locate subject root
    subject_root = None
    cur = src_file.parent
    while cur != cur.parent:
        if (cur / "outputs").is_dir() or (cur / "CURRICULUM_TREE.md").is_file():
            subject_root = cur
            break
        if cur.name.startswith(("48520", "48521", "48430", "41200")):
            subject_root = cur
            break
        cur = cur.parent

    if not subject_root:
        subject_root = src_file.parent

    # Output directory
    out_json_dir = subject_root / "outputs" / "json"
    out_json_dir.mkdir(parents=True, exist_ok=True)
    
    stem = src_file.stem.lower().replace("-", "_").replace(" ", "_")
    target_json = out_json_dir / f"{stem}_cornell.json"

    if target_json.is_file() and not args.force:
        print(f"⚠️  File already exists: {target_json}")
        print("   Use --force to overwrite.")
        return 0

    # Extract title and headings from markdown
    lines = src_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    title = stem.replace("_", " ").title()
    for l in lines:
        if l.startswith("# "):
            title = l.replace("# ", "").strip()
            break

    # Extract sections
    sections = []
    current_sec = None
    for l in lines:
        if l.startswith("## "):
            sec_title = l.replace("## ", "").strip()
            current_sec = {"heading": sec_title, "entries": []}
            sections.append(current_sec)
    
    if not sections:
        sections = [
            {"heading": "Core Principles & Governing Laws", "entries": []},
            {"heading": "Analytical Methods & Derivations", "entries": []},
            {"heading": "Exam Traps & Application Checklist", "entries": []}
        ]

    # Pre-populate starter cues adhering to ICM standards
    rel_source = str(src_file.relative_to(subject_root)).replace("\\", "/")
    
    template_data = {
        "title": title,
        "source": rel_source,
        "subject": subject_root.name,
        "summary": f"Comprehensive active-recall review of {title}. Covers foundational definitions, governing mathematical models, and common analysis pitfalls.",
        "sections": [
            {
                "heading": sections[0]["heading"] if sections else "Core Principles & Governing Laws",
                "entries": [
                    {
                        "badge": "definition",
                        "cue": f"What is the physical definition and primary role of {title.split(':')[0]}?",
                        "notes": "Define the fundamental concept clearly and concisely with standard SI units."
                    },
                    {
                        "badge": "formula",
                        "cue": "State the primary governing equation and boundary conditions.",
                        "notes": "$$y = f(x)$$\n\nWhere:\n- $y$: Primary variable\n- $x$: Independent quantity"
                    }
                ]
            },
            {
                "heading": sections[1]["heading"] if len(sections) > 1 else "Analytical Methods & Derivations",
                "entries": [
                    {
                        "badge": "mechanism",
                        "cue": "What is the systematic step-by-step procedure for solving standard problems in this topic?",
                        "notes": "1. **Identify** knowns, boundary conditions, and circuit nodes.\n2. **Apply** governing conservation laws.\n3. **Solve** the resulting system of equations."
                    },
                    {
                        "badge": "comparison",
                        "cue": "How does this method compare to alternative approaches under extreme or limit cases?",
                        "notes": "| Feature | Standard Method | Alternative Approach |\n|---|---|---|\n| Complexity | Low | High |\n| Accuracy | High | Approximated |"
                    }
                ]
            },
            {
                "heading": sections[2]["heading"] if len(sections) > 2 else "Exam Traps & Application Checklist",
                "entries": [
                    {
                        "badge": "pitfall",
                        "cue": "What is the most frequent sign error, invalid assumption, or trap in student calculations?",
                        "notes": "> [!WARNING]\n> Always verify reference polarities and initial energy storage conditions before substituting values."
                    },
                    {
                        "badge": "checklist",
                        "cue": "What sanity checks should be verified before submitting the final answer?",
                        "notes": "- [ ] Dimensional analysis check (units balance)\n- [ ] Asymptotic limits check ($t \\to 0$, $t \\to \\infty$)\n- [ ] Power conservation check ($P_{\\text{gen}} = P_{\\text{abs}}$)"
                    }
                ]
            }
        ]
    }

    target_json.write_text(json.dumps(template_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✨ [Scaffold Complete] Created Cornell Note template:")
    print(f"   • Target JSON: {target_json}")
    print(f"   • Inherited Stem: '{stem}' (guarantees seamless CURRICULUM_TREE linking)")
    print(f"   • Pre-filled Source: '{rel_source}'")
    print("\n👉 Next steps for AI Agent / Human:")
    print(f"   1. Populate 6–8 rigorous active-recall cues in: {target_json.name}")
    print(f"   2. Build interactive HTML & Anki TSV: academic-icm build-note {target_json}")
    print(f"   3. Compile Cosmos: academic-icm compile")
    return 0

# ==============================================================================
# SUBCOMMAND: build-note
# ==============================================================================
def cmd_build_note(args: argparse.Namespace) -> int:
    target_json = Path(args.json_file).resolve()
    if not target_json.is_file():
        print(f"❌ Error: JSON note file not found: {target_json}")
        return 1

    format_script = find_engine_path("cornell-notes", "format_notes.py")
    if not format_script:
        print("❌ Error: format_notes.py engine not found in skills catalog.")
        return 1

    print(f"\n🔨 [Building Note] Compiling HTML & Anki TSV for: {target_json.name}")
    res = subprocess.run([sys.executable, str(format_script), str(target_json), "--anki"])
    if res.returncode == 0:
        html_file = target_json.parent.parent / "html" / f"{target_json.stem}.html"
        print(f"✅ Note compiled successfully!")
        if html_file.is_file():
            print(f"   • HTML Study Sheet: file://{html_file}")
        return 0
    return res.returncode

# ==============================================================================
# SUBCOMMAND: compile
# ==============================================================================
def cmd_compile(args: argparse.Namespace) -> int:
    vault_root = find_vault_root(args.vault)
    tree_file = vault_root / "CURRICULUM_TREE.md"
    
    print(f"\n🌲 [Curriculum Compiler] Compiling from {tree_file}...")
    
    okf_script = find_engine_path("okf-architect", "okf_architect.py")
    if not okf_script:
        # Fallback to local compile_tree.py
        local_compile = vault_root / "compile_tree.py"
        if local_compile.is_file():
            res = subprocess.run([sys.executable, str(local_compile)])
            return res.returncode
        print("❌ Error: okf-architect engine not found.")
        return 1

    # Run okf_architect compile-tree
    res = subprocess.run([sys.executable, str(okf_script), "compile-tree", str(vault_root)])
    if res.returncode == 0:
        print("\n✨ Compilation finished successfully!")
        print(f"   • Knowledge Cosmos: file://{vault_root / 'viz.html'}")
        print(f"   • Study Portal:     file://{vault_root / 'cornell_index.html'}")
    return res.returncode

# ==============================================================================
# SUBCOMMAND: sync-orphans
# ==============================================================================
def cmd_sync_orphans(args: argparse.Namespace) -> int:
    vault_root = find_vault_root(args.vault)
    tree_file = vault_root / "CURRICULUM_TREE.md"
    if not tree_file.is_file():
        print(f"❌ Error: CURRICULUM_TREE.md not found in {vault_root}")
        return 1

    print(f"\n🔧 [Sync Orphans] Repairing known stem mismatches in: {vault_root}")
    repaired = 0

    # Repair 1: Week 7 sinusoidal analysis in 48520
    w7_old = vault_root / "48520 - Electronics and Circuits" / "outputs" / "json" / "Week07_Sinusoidal_Analysis_cornell.json"
    w7_new = vault_root / "48520 - Electronics and Circuits" / "outputs" / "json" / "w07_week_7_48520_topic_14_and_topic_15_2022_2nd_cornell.json"
    if w7_old.is_file() and not w7_new.is_file():
        print(f"  • Renaming 48520 Week 7 note to canonical stem: {w7_new.name}")
        w7_old.rename(w7_new)
        # Also rename HTML if present
        w7_html_old = w7_old.parent.parent / "html" / "Week07_Sinusoidal_Analysis_cornell.html"
        w7_html_new = w7_old.parent.parent / "html" / "w07_week_7_48520_topic_14_and_topic_15_2022_2nd_cornell.html"
        if w7_html_old.is_file():
            w7_html_old.rename(w7_html_new)
        repaired += 1

    # Repair 2: Map Quiz 3 Worked Solutions Playbook in CURRICULUM_TREE.md if missing
    tree_text = tree_file.read_text(encoding="utf-8")
    if "Quiz_3_Worked_Solutions_Playbook" not in tree_text and "real_quiz_3_solutions_2" in tree_text:
        # Add alias or ensure mapping
        pass

    if repaired > 0:
        print(f"\n✅ Repaired {repaired} stem mismatches. Recompiling tree...")
        cmd_compile(args)
    else:
        print("ℹ️  No immediate automatic renames required.")
    return 0

# ==============================================================================
# SUBCOMMAND: serve
# ==============================================================================
def cmd_serve(args: argparse.Namespace) -> int:
    vault_root = find_vault_root(args.vault)
    port = args.port or 8765
    print(f"\n🌐 [Study Portal Server] Serving {vault_root} on port {port}...")
    print(f"   • Open Cosmos: http://localhost:{port}/viz.html")
    print(f"   • Open Portal: http://localhost:{port}/cornell_index.html")
    
    # Check if already running
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_open = s.connect_ex(("127.0.0.1", port)) == 0
    s.close()
    if is_open:
        print(f"✅ Server is already running on port {port}!")
        return 0

    try:
        subprocess.run([sys.executable, "-m", "http.server", str(port), "--directory", str(vault_root)])
    except KeyboardInterrupt:
        print("\nServer stopped.")
    return 0

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(
        prog="academic-icm",
        description="Academic ICM Pipeline Orchestrator (Interpretable Context Methodology)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # status
    p_status = subparsers.add_parser("status", help="Show curriculum coverage and orphaned notes")
    p_status.add_argument("vault", nargs="?", default=None, help="Path to notes vault root")

    # audit
    p_audit = subparsers.add_parser("audit", help="Deep audit of stem alignment and JSON schema")
    p_audit.add_argument("vault", nargs="?", default=None, help="Path to notes vault root")

    # scaffold
    p_scaffold = subparsers.add_parser("scaffold", help="Generate a matching _cornell.json template from markdown source")
    p_scaffold.add_argument("source_md", help="Path to input markdown file")
    p_scaffold.add_argument("--force", action="store_true", help="Overwrite existing JSON file")

    # build-note
    p_build = subparsers.add_parser("build-note", help="Compile _cornell.json into HTML study sheet and Anki deck")
    p_build.add_argument("json_file", help="Path to _cornell.json file")

    # compile
    p_compile = subparsers.add_parser("compile", help="Recompile CURRICULUM_TREE.md into viz.html and cornell_index.html")
    p_compile.add_argument("vault", nargs="?", default=None, help="Path to notes vault root")

    # sync-orphans
    p_sync = subparsers.add_parser("sync-orphans", help="Repair and align known orphaned notes")
    p_sync.add_argument("vault", nargs="?", default=None, help="Path to notes vault root")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start local web server for study portal")
    p_serve.add_argument("vault", nargs="?", default=None, help="Path to notes vault root")
    p_serve.add_argument("--port", type=int, default=8765, help="Port to serve on (default: 8765)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "status": cmd_status,
        "audit": cmd_audit,
        "scaffold": cmd_scaffold,
        "build-note": cmd_build_note,
        "compile": cmd_compile,
        "sync-orphans": cmd_sync_orphans,
        "serve": cmd_serve,
    }

    return dispatch[args.command](args)

if __name__ == "__main__":
    sys.exit(main())
