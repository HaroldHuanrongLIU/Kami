"""Public-site fact drift checks for Kami.

The hosted pages, README, and llms.txt intentionally repeat install and product
facts in multiple languages. This module keeps those facts tied to the shared
registry and public constants so `build.py --check` catches drift before CI.
"""
from __future__ import annotations

import html
import re
from collections.abc import Mapping

from shared import (
    CLAUDE_CODE_INSTALL_COMMANDS,
    CLAUDE_CODE_MIN_VERSION,
    CLAUDE_DESKTOP_PACKAGE_URL,
    CODEX_PLUGIN_INSTALL_COMMANDS,
    DIAGRAM_TEMPLATES,
    GENERIC_AGENT_INSTALL_COMMAND,
    PUBLIC_DOCUMENT_TEMPLATE_KINDS,
    ROOT,
    public_document_template_count,
    public_document_template_kinds,
)

FULL_PUBLIC_FACT_FILES = (
    "README.md",
    "llms.txt",
    "index.html",
    "index-zh.html",
    "index-ja.html",
    "index-ko.html",
    "index-tw.html",
)
REDIRECT_SITE_FILE = "index-en.html"
SITE_SURFACE_ABSENT = "__site_surface_absent__"

_TEMPLATE_COUNT_PATTERNS = (
    r"\b8 document template",
    r"\bEight document template",
    r"八种文档模板",
    r"八種文件範本",
    r"8種類のドキュメントテンプレート",
    r"8가지 문서 템플릿",
)

def _normalize(text: str) -> str:
    return html.unescape(text)


def _contains_template_count(text: str, expected: int) -> bool:
    if expected != 8:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _TEMPLATE_COUNT_PATTERNS)


def _contains_diagram_count(text: str, expected: int) -> bool:
    patterns = [
        rf"\b{expected}\s+(?:inline\s+SVG\s+)?diagram",
        rf"{expected}\s*(?:种|種).*?(?:图表|圖表)",
        rf"{expected}種.*?図表",
        rf"{expected}가지.*?다이어그램",
    ]
    if expected == 18:
        patterns.append(r"\bEighteen\s+inline\s+SVG")
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _file_texts(files: Mapping[str, str] | None) -> tuple[dict[str, str], list[str]]:
    if files is not None:
        return dict(files), []

    texts: dict[str, str] = {}
    issues: list[str] = []
    site_files = (*FULL_PUBLIC_FACT_FILES, REDIRECT_SITE_FILE)
    if not any((ROOT / rel).exists() for rel in site_files):
        return {SITE_SURFACE_ABSENT: ""}, []
    for rel in site_files:
        path = ROOT / rel
        if not path.exists():
            issues.append(f"{rel}: missing public fact file")
            continue
        texts[rel] = path.read_text(encoding="utf-8", errors="replace")
    return texts, issues


def site_fact_issues(files: Mapping[str, str] | None = None) -> list[str]:
    texts, issues = _file_texts(files)
    if SITE_SURFACE_ABSENT in texts:
        return []

    kinds = public_document_template_kinds()
    if kinds != PUBLIC_DOCUMENT_TEMPLATE_KINDS:
        missing = sorted(PUBLIC_DOCUMENT_TEMPLATE_KINDS - kinds)
        extra = sorted(kinds - PUBLIC_DOCUMENT_TEMPLATE_KINDS)
        detail = []
        if missing:
            detail.append(f"missing public kinds: {', '.join(missing)}")
        if extra:
            detail.append(f"extra public kinds: {', '.join(extra)}")
        issues.append("registry: public document template kinds drifted" + (f" ({'; '.join(detail)})" if detail else ""))

    template_count = public_document_template_count()
    diagram_count = len(DIAGRAM_TEMPLATES)

    for rel in FULL_PUBLIC_FACT_FILES:
        raw = texts.get(rel)
        if raw is None:
            if files is not None:
                issues.append(f"{rel}: missing public fact file")
            continue
        text = _normalize(raw)

        if CLAUDE_CODE_MIN_VERSION not in text:
            issues.append(f"{rel}: missing Claude Code minimum version {CLAUDE_CODE_MIN_VERSION}")
        for command in CLAUDE_CODE_INSTALL_COMMANDS:
            if command not in text:
                issues.append(f"{rel}: missing Claude Code install command `{command}`")
        for command in CODEX_PLUGIN_INSTALL_COMMANDS:
            if command not in text:
                issues.append(f"{rel}: missing Codex install command `{command}`")
        if GENERIC_AGENT_INSTALL_COMMAND not in text:
            issues.append(f"{rel}: missing generic agent install command `{GENERIC_AGENT_INSTALL_COMMAND}`")

        if "kami.zip" not in text:
            issues.append(f"{rel}: missing Claude Desktop package name kami.zip")
        if rel != "llms.txt" and CLAUDE_DESKTOP_PACKAGE_URL not in text:
            issues.append(f"{rel}: missing Claude Desktop package URL {CLAUDE_DESKTOP_PACKAGE_URL}")

        if not _contains_template_count(text, template_count):
            issues.append(f"{rel}: missing public document template count {template_count}")
        if not _contains_diagram_count(text, diagram_count):
            issues.append(f"{rel}: missing diagram count {diagram_count}")

    redirect = texts.get(REDIRECT_SITE_FILE)
    if redirect is None:
        if files is not None:
            issues.append(f"{REDIRECT_SITE_FILE}: missing redirect page")
    else:
        text = _normalize(redirect)
        for required in ('http-equiv="refresh"', "url=./", 'content="noindex"', 'rel="canonical"'):
            if required not in text:
                issues.append(f"{REDIRECT_SITE_FILE}: missing redirect marker `{required}`")
        if CLAUDE_CODE_MIN_VERSION in text or "kami.zip" in text:
            issues.append(f"{REDIRECT_SITE_FILE}: redirect page should not carry product fact copy")

    return issues


def check_site_facts(verbose: bool = False) -> int:
    if not any((ROOT / rel).exists() for rel in (*FULL_PUBLIC_FACT_FILES, REDIRECT_SITE_FILE)):
        print("OK: public site facts skipped (site files absent)")
        return 0

    issues = site_fact_issues()
    if not issues:
        scanned = len(FULL_PUBLIC_FACT_FILES) + 1
        print(f"OK: public site facts in sync across {scanned} file(s)")
        return 0

    print(f"\n[site-fact-drift] {len(issues)}")
    for issue in issues:
        print(f"  {issue}")
    if verbose:
        print("  source: shared public constants and template registries")
    return 1
