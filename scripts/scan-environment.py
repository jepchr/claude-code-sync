#!/usr/bin/env python3
"""
Claude Code Environment Scanner
Reads the local Claude Code configuration and produces a structured
markdown snapshot for cross-machine comparison.

Usage: python3 scan-environment.py <machine-name> [sync-folder-path]
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
CLAUDE_JSON = Path.home() / ".claude.json"


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_machine_info():
    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            return "unknown"

    return {
        "hostname": run(["hostname"]),
        "claude_code_version": run(["claude", "--version"]),
        "node_version": run(["node", "--version"]),
        "python_version": run(["python3", "--version"]),
    }


def scan_skills():
    skills = []
    skills_dir = CLAUDE_DIR / "skills"
    if not skills_dir.exists():
        return skills
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir():
            continue
        skill_md = d / "SKILL.md"
        name = d.name
        description = ""
        if skill_md.exists():
            content = skill_md.read_text()
            if content.startswith("---"):
                try:
                    end = content.index("---", 3)
                    for line in content[3:end].split("\n"):
                        if line.strip().startswith("description:"):
                            description = line.split(":", 1)[1].strip().strip("'\"")
                except ValueError:
                    pass
        skills.append({"name": name, "description": description})
    return skills


def scan_plugins():
    data = read_json(CLAUDE_DIR / "plugins" / "installed_plugins.json")
    plugins = data.get("plugins", data) if isinstance(data, dict) else {}
    result = {}
    for name, entries in plugins.items():
        if isinstance(entries, list) and entries:
            result[name] = entries[0]
        elif isinstance(entries, dict):
            result[name] = entries
    return result


def scan_settings():
    settings = read_json(CLAUDE_DIR / "settings.json")
    return {
        "hooks": settings.get("hooks", {}),
        "env": settings.get("env", {}),
        "enabled_plugins": settings.get("enabledPlugins", {}),
        "always_thinking": settings.get("alwaysThinkingEnabled", False),
        "effort_level": settings.get("effortLevel", "default"),
        "permissions_allow_count": len(settings.get("permissions", {}).get("allow", [])),
        "permissions_deny_count": len(settings.get("permissions", {}).get("deny", [])),
        "status_line": settings.get("statusLine", {}),
    }


def scan_mcp_servers():
    config = read_json(CLAUDE_JSON)
    servers = {}
    for project_path, project_config in config.get("projects", {}).items():
        if not isinstance(project_config, dict):
            continue
        for name, server in project_config.get("mcpServers", {}).items():
            if not isinstance(server, dict):
                continue
            disabled = server.get("disabled", False)
            if "command" in server:
                stype = "stdio"
            elif "url" in server and "sse" in str(server.get("url", "")):
                stype = "sse"
            else:
                stype = "http"
            servers[name] = {"type": stype, "disabled": disabled}
    return servers


def scan_commands():
    commands_dir = CLAUDE_DIR / "commands"
    if not commands_dir.exists():
        return []
    return [f.stem for f in sorted(commands_dir.iterdir()) if f.suffix == ".md"]


def scan_scripts():
    scripts_dir = CLAUDE_DIR / "scripts"
    if not scripts_dir.exists():
        return []
    return [f.name for f in sorted(scripts_dir.iterdir())
            if f.is_file() and not f.name.startswith(".")]


def scan_claude_md():
    result = {}
    paths = {
        "global": CLAUDE_DIR / "CLAUDE.md",
        "home": Path.home() / "CLAUDE.md",
    }
    for label, path in paths.items():
        if path.exists():
            result[label] = path.read_text()
    return result


def format_snapshot(machine_name):
    info = get_machine_info()
    skills = scan_skills()
    plugins = scan_plugins()
    settings = scan_settings()
    mcp = scan_mcp_servers()
    commands = scan_commands()
    scripts = scan_scripts()
    claude_md = scan_claude_md()
    timestamp = datetime.now().isoformat()

    active_mcp = {k: v for k, v in mcp.items() if not v["disabled"]}
    disabled_mcp = {k: v for k, v in mcp.items() if v["disabled"]}

    lines = []
    lines.append("---")
    lines.append(f"machine: {machine_name}")
    lines.append(f"timestamp: {timestamp}")
    lines.append("scanner_version: '1.0'")
    lines.append(f"hostname: {info['hostname']}")
    lines.append(f"claude_code_version: {info['claude_code_version']}")
    lines.append(f"node_version: {info['node_version']}")
    lines.append(f"python_version: {info['python_version']}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Environment Snapshot: {machine_name}")
    lines.append(f"")
    lines.append(f"*Generated {timestamp}*")
    lines.append("")

    # Skills
    lines.append(f"## Skills ({len(skills)} installed)")
    lines.append("")
    if skills:
        lines.append("| Name | Description |")
        lines.append("|------|-------------|")
        for s in skills:
            lines.append(f"| {s['name']} | {s['description']} |")
    else:
        lines.append("*No custom skills installed.*")
    lines.append("")

    # Plugins
    lines.append(f"## Plugins ({len(plugins)} installed)")
    lines.append("")
    if plugins:
        lines.append("| Name | Version | Scope |")
        lines.append("|------|---------|-------|")
        for name, meta in plugins.items():
            lines.append(f"| {name} | {meta.get('version', '?')} | {meta.get('scope', '?')} |")
    lines.append("")

    # MCP Servers
    lines.append(f"## MCP Servers ({len(active_mcp)} active, {len(disabled_mcp)} disabled)")
    lines.append("")
    if active_mcp:
        lines.append("### Active")
        lines.append("| Name | Type |")
        lines.append("|------|------|")
        for name, meta in active_mcp.items():
            lines.append(f"| {name} | {meta['type']} |")
        lines.append("")
    if disabled_mcp:
        lines.append("### Disabled")
        lines.append("| Name | Type |")
        lines.append("|------|------|")
        for name, meta in disabled_mcp.items():
            lines.append(f"| {name} | {meta['type']} |")
        lines.append("")

    # Settings
    lines.append("## Settings")
    lines.append("")
    lines.append(f"- Always thinking: {settings['always_thinking']}")
    lines.append(f"- Effort level: {settings['effort_level']}")
    lines.append(f"- Permissions: {settings['permissions_allow_count']} allowed, {settings['permissions_deny_count']} denied")
    for key, val in settings["env"].items():
        lines.append(f"- {key}: {val}")
    lines.append("")

    # Hooks
    lines.append("## Hooks")
    lines.append("")
    hooks = settings["hooks"]
    if hooks:
        for event, hook_list in hooks.items():
            lines.append(f"### {event}")
            if isinstance(hook_list, list):
                for entry in hook_list:
                    for h in entry.get("hooks", []):
                        htype = h.get("type", "unknown")
                        if htype == "command":
                            lines.append(f"- **command**: `{h.get('command', '?')}`")
                            if h.get("once"):
                                lines.append("  - Runs once per session")
                        elif htype == "prompt":
                            prompt_preview = h.get("prompt", "")[:100].replace("\n", " ")
                            lines.append(f"- **prompt**: {prompt_preview}...")
            lines.append("")
    else:
        lines.append("*No hooks configured.*")
        lines.append("")

    # Custom commands
    lines.append(f"## Custom Commands ({len(commands)})")
    lines.append("")
    for c in commands:
        lines.append(f"- {c}")
    lines.append("")

    # Scripts
    lines.append(f"## Scripts ({len(scripts)})")
    lines.append("")
    for s in scripts:
        lines.append(f"- {s}")
    lines.append("")

    # CLAUDE.md content
    lines.append("## CLAUDE.md Content")
    lines.append("")
    for label, content in claude_md.items():
        lines.append(f"### {label.title()}")
        lines.append("")
        lines.append(content)
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scan-environment.py <machine-name> [sync-folder-path]")
        print("Example: python3 scan-environment.py work ~/Dropbox/claude-code-sync")
        sys.exit(1)

    machine_name = sys.argv[1]

    if len(sys.argv) >= 3:
        sync_dir = Path(sys.argv[2])
    else:
        # Default to iCloud
        sync_dir = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "claude-code-sync"

    output_dir = sync_dir / "raw" / machine_name
    output_dir.mkdir(parents=True, exist_ok=True)

    snapshot = format_snapshot(machine_name)

    output_path = output_dir / "latest.md"
    output_path.write_text(snapshot)

    date_str = datetime.now().strftime("%Y-%m-%d")
    history_path = output_dir / f"snapshot-{date_str}.md"
    history_path.write_text(snapshot)

    print(f"Snapshot written to {output_path}")
    print(f"History copy at {history_path}")


if __name__ == "__main__":
    main()
