"""Unit tests for skill directory structure — symlinks, script references."""
import os
import py_compile
import re

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

SCRIPT_REF_PATTERN = re.compile(
    r'(?:python3|bash)\s+\$\{CLAUDE_SKILL_DIR\}/scripts/(\S+)')
SYSPATH_PATTERN = re.compile(
    r"sys\.path\.insert\(0,\s*'\$\{CLAUDE_SKILL_DIR\}/scripts'\)")
IMPORT_PATTERN = re.compile(
    r'from\s+(\w+)\s+import')


def _discover_skills():
    """Find all skill dirs that contain a SKILL.md."""
    results = []
    for name in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, name)
        skill_md = os.path.join(skill_path, "SKILL.md")
        if os.path.isdir(skill_path) and os.path.isfile(skill_md):
            with open(skill_md) as f:
                content = f.read()
            results.append((name, skill_path, content))
    return results


def _skills_referencing_scripts():
    """Skills whose SKILL.md references ${CLAUDE_SKILL_DIR}/scripts/."""
    return [(name, path, content) for name, path, content
            in _discover_skills()
            if "${CLAUDE_SKILL_DIR}/scripts/" in content]


def _extract_script_refs(content):
    """Extract script filenames from SKILL.md content."""
    return list(set(SCRIPT_REF_PATTERN.findall(content)))


def _extract_module_refs(content):
    """Extract module names from sys.path.insert + import patterns."""
    modules = set()
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if SYSPATH_PATTERN.search(line):
            for j in range(i, min(i + 3, len(lines))):
                m = IMPORT_PATTERN.search(lines[j])
                if m:
                    modules.add(m.group(1))
    return list(modules)


ALL_SKILLS_WITH_SCRIPT_REFS = _skills_referencing_scripts()


# ─── Symlink Presence ────────────────────────────────────────────────────────


class TestSymlinkPresence:

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_SCRIPT_REFS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_SCRIPT_REFS])
    def test_skill_has_scripts_symlink(self, skill_name, skill_path, content):
        scripts_link = os.path.join(skill_path, "scripts")
        assert os.path.islink(scripts_link), (
            f"Skill '{skill_name}' references scripts via CLAUDE_SKILL_DIR "
            f"but has no scripts symlink. "
            f"Add: ln -s ../strategy-common/scripts "
            f".claude/skills/{skill_name}/scripts")


# ─── Symlink Chain Resolution ────────────────────────────────────────────────


class TestSymlinkChain:

    def test_strategy_common_resolves_to_project_scripts(self):
        common_scripts = os.path.join(SKILLS_DIR, "strategy-common", "scripts")
        assert os.path.islink(common_scripts)
        resolved = os.path.realpath(common_scripts)
        assert resolved == os.path.realpath(SCRIPTS_DIR)

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_SCRIPT_REFS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_SCRIPT_REFS])
    def test_symlink_resolves_to_project_scripts(self, skill_name,
                                                  skill_path, content):
        scripts_link = os.path.join(skill_path, "scripts")
        if not os.path.islink(scripts_link):
            pytest.skip(f"symlink missing (covered by TestSymlinkPresence)")
        resolved = os.path.realpath(scripts_link)
        assert resolved == os.path.realpath(SCRIPTS_DIR), (
            f"Skill '{skill_name}' scripts symlink resolves to {resolved}, "
            f"expected {os.path.realpath(SCRIPTS_DIR)}")

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_SCRIPT_REFS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_SCRIPT_REFS])
    def test_symlink_target_is_directory(self, skill_name, skill_path, content):
        scripts_link = os.path.join(skill_path, "scripts")
        if not os.path.islink(scripts_link):
            pytest.skip(f"symlink missing (covered by TestSymlinkPresence)")
        assert os.path.isdir(scripts_link), (
            f"Skill '{skill_name}' scripts symlink is dangling")


# ─── Referenced Scripts Exist ────────────────────────────────────────────────


class TestReferencedScripts:

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_SCRIPT_REFS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_SCRIPT_REFS])
    def test_all_referenced_scripts_exist(self, skill_name, skill_path,
                                           content):
        scripts = _extract_script_refs(content)
        for script in scripts:
            script_path = os.path.join(SCRIPTS_DIR, script)
            assert os.path.isfile(script_path), (
                f"Skill '{skill_name}' references {script} but it does not "
                f"exist at {script_path}")

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_SCRIPT_REFS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_SCRIPT_REFS])
    def test_all_referenced_modules_exist(self, skill_name, skill_path,
                                           content):
        modules = _extract_module_refs(content)
        for module in modules:
            module_path = os.path.join(SCRIPTS_DIR, f"{module}.py")
            assert os.path.isfile(module_path), (
                f"Skill '{skill_name}' imports {module} via CLAUDE_SKILL_DIR "
                f"but {module}.py does not exist at {SCRIPTS_DIR}")


# ─── Script Quality ──────────────────────────────────────────────────────────


def _all_referenced_py_scripts():
    """Collect unique .py scripts referenced across all skills."""
    scripts = set()
    for _, _, content in ALL_SKILLS_WITH_SCRIPT_REFS:
        for s in _extract_script_refs(content):
            if s.endswith(".py"):
                scripts.add(s)
    return sorted(scripts)


def _all_referenced_sh_scripts():
    """Collect unique .sh scripts referenced across all skills."""
    scripts = set()
    for _, _, content in ALL_SKILLS_WITH_SCRIPT_REFS:
        for s in _extract_script_refs(content):
            if s.endswith(".sh"):
                scripts.add(s)
    return sorted(scripts)


# ─── $ARGUMENTS Framing ─────────────────────────────────────────────────────

RUNTIME_ARGS_HEADER = "## Runtime Arguments"
RUNTIME_ARGS_MARKER = (
    "The value below was substituted by the skill runner at invocation time."
)
RUNTIME_ARGS_VALIDATE_MARKER = "Validate before use:"


def _skills_using_arguments():
    """Skills whose SKILL.md contains $ARGUMENTS."""
    return [(name, path, content) for name, path, content
            in _discover_skills()
            if "$ARGUMENTS" in content]


def _extract_runtime_args_section(content):
    """Extract the body of the ## Runtime Arguments section.

    Tracks fenced code block state so that a ``## Runtime Arguments``
    heading inside a fenced block is not falsely recognised as the real
    section start.  Requires exactly one unfenced section.
    """
    lines = content.split("\n")
    section_lines = []
    in_section = False
    in_fence = False
    section_count = 0
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            if in_section:
                section_lines.append(line)
            continue
        # Only recognise headings when NOT inside a fenced block.
        if not in_fence:
            if line.strip() == RUNTIME_ARGS_HEADER:
                section_count += 1
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
        if in_section:
            section_lines.append(line)
    assert section_count <= 1, (
        f"Found {section_count} unfenced '{RUNTIME_ARGS_HEADER}' sections; "
        f"expected at most 1")
    return "\n".join(section_lines)


ALL_SKILLS_WITH_ARGUMENTS = _skills_using_arguments()


class TestArgumentsFraming:
    """Verify that $ARGUMENTS is wrapped in a clearly-labelled Runtime Arguments
    section so the LLM agent never misinterprets the substituted value as a
    placeholder or instruction reference (RHAIFIRST-399)."""

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_ARGUMENTS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_ARGUMENTS])
    def test_has_runtime_arguments_section(self, skill_name, skill_path,
                                           content):
        assert RUNTIME_ARGS_HEADER in content, (
            f"Skill '{skill_name}' uses $ARGUMENTS but is missing a "
            f"'{RUNTIME_ARGS_HEADER}' section. Wrap $ARGUMENTS in a "
            f"Runtime Arguments section — see RHAIFIRST-399.")

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_ARGUMENTS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_ARGUMENTS])
    def test_has_substitution_marker_in_section(self, skill_name, skill_path,
                                                content):
        section = _extract_runtime_args_section(content)
        assert RUNTIME_ARGS_MARKER in section, (
            f"Skill '{skill_name}' uses $ARGUMENTS but the "
            f"'{RUNTIME_ARGS_HEADER}' section is missing the substitution "
            f"marker text. The marker must appear inside the Runtime "
            f"Arguments section — see RHAIFIRST-399.")

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_ARGUMENTS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_ARGUMENTS])
    def test_has_arguments_token_in_section(self, skill_name, skill_path,
                                            content):
        section = _extract_runtime_args_section(content)
        # Require $ARGUMENTS on its own line (with optional surrounding
        # whitespace) so that substring occurrences in prose (e.g.
        # "The value is called $ARGUMENTS") are not falsely matched.
        assert re.search(r"(?m)^\s*\$ARGUMENTS\s*$", section), (
            f"Skill '{skill_name}' uses $ARGUMENTS but the token does not "
            f"appear on a standalone line inside the "
            f"'{RUNTIME_ARGS_HEADER}' section. "
            f"The $ARGUMENTS substitution must be on its own line within "
            f"the Runtime Arguments section — see RHAIFIRST-399.")

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_ARGUMENTS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_ARGUMENTS])
    def test_has_validation_instruction(self, skill_name, skill_path, content):
        section = _extract_runtime_args_section(content)
        assert RUNTIME_ARGS_VALIDATE_MARKER in section, (
            f"Skill '{skill_name}' is missing the validation instruction "
            f"in the '{RUNTIME_ARGS_HEADER}' section. Add a "
            f"'{RUNTIME_ARGS_VALIDATE_MARKER}' instruction to prevent "
            f"unvalidated input from reaching shell commands.")
        # Assert the actual security-critical language is present, not
        # just the marker.  Skills must spell out the rejection rule.
        assert "shell metacharacters" in section, (
            f"Skill '{skill_name}' validation block in "
            f"'{RUNTIME_ARGS_HEADER}' must mention 'shell metacharacters' "
            f"so the LLM knows what to reject.")
        assert "do not pass unvalidated input to shell commands" in section, (
            f"Skill '{skill_name}' validation block in "
            f"'{RUNTIME_ARGS_HEADER}' must contain 'do not pass unvalidated "
            f"input to shell commands'.")

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             ALL_SKILLS_WITH_ARGUMENTS,
                             ids=[s[0] for s in ALL_SKILLS_WITH_ARGUMENTS])
    def test_no_arguments_in_inline_prose(self, skill_name, skill_path,
                                          content):
        """$ARGUMENTS must not appear in inline prose — only inside the
        Runtime Arguments section or in non-executable code blocks.

        Executable (bash/sh) fenced blocks are still inspected because
        raw $ARGUMENTS in a shell snippet is a security concern.
        """
        lines = content.split("\n")
        in_fence = False
        fence_is_executable = False
        in_runtime_section = False
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_fence:
                    # Opening fence — check if it is bash/sh.
                    in_fence = True
                    lang = stripped[3:].strip().split()[0] if stripped[3:].strip() else ""
                    fence_is_executable = lang in ("bash", "sh")
                else:
                    # Closing fence.
                    in_fence = False
                    fence_is_executable = False
                continue
            # Only recognise H2 headings when NOT inside a fence.
            if not in_fence:
                if stripped == RUNTIME_ARGS_HEADER:
                    in_runtime_section = True
                    continue
                if in_runtime_section and line.startswith("## "):
                    in_runtime_section = False
            # Skip lines inside the Runtime Arguments section.
            if in_runtime_section:
                continue
            # Skip non-executable fenced blocks (e.g. markdown examples).
            if in_fence and not fence_is_executable:
                continue
            if "$ARGUMENTS" in line:
                violations.append(f"  line {i}: {stripped}")
        assert not violations, (
            f"Skill '{skill_name}' has $ARGUMENTS in inline prose "
            f"(outside non-executable code blocks and Runtime Arguments "
            f"section). "
            f"These references get substituted and confuse the LLM. "
            f"Use 'the runtime arguments' instead:\n"
            + "\n".join(violations))


# ─── Script Quality ──────────────────────────────────────────────────────────


class TestScriptQuality:

    @pytest.mark.parametrize("script", _all_referenced_py_scripts())
    def test_python_scripts_have_valid_syntax(self, script):
        script_path = os.path.join(SCRIPTS_DIR, script)
        if not os.path.isfile(script_path):
            pytest.skip(f"{script} not found (covered by TestReferencedScripts)")
        py_compile.compile(script_path, doraise=True)

    @pytest.mark.parametrize("script", _all_referenced_sh_scripts())
    def test_shell_scripts_are_executable(self, script):
        script_path = os.path.join(SCRIPTS_DIR, script)
        if not os.path.isfile(script_path):
            pytest.skip(f"{script} not found (covered by TestReferencedScripts)")
        assert os.access(script_path, os.X_OK), (
            f"{script} is not executable. Run: chmod +x scripts/{script}")
