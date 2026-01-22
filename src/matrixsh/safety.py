# matrixsh_project/src/matrixsh/safety.py

from __future__ import annotations

import re

YES = {"y", "yes", "ok", "s", "si", "sì", "oui", "ja"}
NO = {"n", "no", "non", "nah", "nope"}


def is_yes(text: str) -> bool:
    return text.strip().lower() in YES


def is_no(text: str) -> bool:
    return text.strip().lower() in NO


def looks_like_natural_language(s: str) -> bool:
    """
    Heuristic: If it looks like a sentence/question rather than a shell command,
    treat it as natural language.
    """
    t = s.strip()
    if not t:
        return False

    # if contains shell operators, likely a command
    if any(x in t for x in ["|", "&&", "||", ">", "<", ";"]):
        return False

    # starts with flags/path prefixes
    if t.startswith(("-", "/", ".")):
        return False

    # common commands
    if re.match(r"^(cd|dir|ls|pwd|echo|cat|type)\b", t, re.IGNORECASE):
        return False

    # very short = likely command
    if len(t) <= 3:
        return False

    # multi-word sentence
    spaces = t.count(" ")
    if spaces >= 2:
        return True

    # common question/phrase openers (EN/IT)
    if re.match(
        r"^(how|what|why|where|when|can|could|should|come|cosa|perche|perché|dove|quando)\b",
        t,
        re.IGNORECASE,
    ):
        return True

    return False


def is_command_not_found(stderr: str, mode: str) -> bool:
    """Detect 'not recognized/command not found' across shells."""
    e = (stderr or "").lower()

    if mode == "cmd":
        return ("is not recognized as an internal or external command" in e) or ("non è riconosciuto" in e)

    if mode == "powershell":
        return ("is not recognized as the name of a cmdlet" in e) or ("non è riconosciuto come nome di cmdlet" in e)

    # bash/zsh
    return ("command not found" in e) or ("not found" in e)


def denylist_match(command: str) -> str | None:
    """
    Return a reason string if the command is forbidden to execute under any circumstance.
    This is a safety valve for format/disk/bootloader/registry/system-critical ops.
    """
    c = command.strip().lower()

    patterns: list[tuple[str, str]] = [
        # Windows disk/format/boot
        (r"\bformat(\.com)?\b", "Refusing to run disk format."),
        (r"\bdiskpart\b", "Refusing to run disk partitioning tool."),
        (r"\bbcdedit\b", "Refusing to run boot configuration edits."),
        (r"\bbootrec\b", "Refusing to run boot repair commands."),
        # Windows registry
        (r"\breg(\.exe)?\s+(add|delete|import|load|unload)\b", "Refusing to modify Windows Registry."),
        # Linux/mac destructive storage
        (r"\bmkfs\.", "Refusing filesystem creation (mkfs)."),
        (r"\bdd\s+if=", "Refusing raw disk writes (dd)."),
        (r"\bparted\b|\bgdisk\b|\bfdisk\b", "Refusing disk partition tools."),
        # system shutdown/reboot
        (r"\bshutdown\b|\breboot\b|\binit\s+0\b", "Refusing shutdown/reboot."),
        # package manager mass removal (potentially destructive)
        (r"\bapt\s+remove\b|\bapt\s+purge\b|\byum\s+remove\b|\bdnf\s+remove\b|\bbrew\s+uninstall\b", "Refusing package removal."),
    ]

    for pat, reason in patterns:
        if re.search(pat, c):
            return reason

    return None
