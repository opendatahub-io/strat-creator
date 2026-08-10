#!/usr/bin/env python3
"""Structural validation for STRAT test plan readiness.

Performs fast, deterministic checks on STRAT content before LLM semantic validation.
Outputs JSON with structural metrics and warnings for testability reviewer to consume.

Usage:
    python scripts/validate_strat_testability.py artifacts/strat-tasks/RHAISTRAT-1431.md

Output:
    JSON to stdout with structural validation results
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import List, Optional

sys.path.insert(0, os.path.dirname(__file__))


@dataclass
class StructuralValidationResult:
    """Results of structural validation checks"""

    # Section presence
    has_acceptance_criteria: bool
    has_technical_approach: bool
    has_dependencies: bool
    has_nfrs: bool
    has_risks: bool

    # Acceptance criteria format
    acceptance_criteria_format: str  # "given-when-then", "checkbox", "other", "none"
    acceptance_criteria_count: int
    acceptance_criteria_word_count: int

    # Content quality indicators
    tbd_count: int  # "TBD", "to be determined", "will add later"
    placeholder_count: int  # "...", "TODO", "<placeholder>"

    # Technical detail indicators
    error_case_mentions: int
    edge_case_mentions: int
    version_specifications: int

    # Interaction mechanism detection
    detected_interaction_types: List[str]  # ["REST_API", "UI", "CLI", "CRD", "SDK"]
    concrete_interactions_count: int

    # Word counts
    technical_approach_word_count: int

    # Dependency analysis
    dependency_count: int
    dependencies_have_versions: bool

    # Warnings/flags
    warnings: List[str]

    # Overall structural score (0-10, purely deterministic)
    structural_score: int


class StratStructuralValidator:
    """Validates STRAT structure for test plan readiness"""

    # Validation thresholds
    MIN_TECHNICAL_APPROACH_WORDS = 100
    MIN_DETAILED_TECHNICAL_APPROACH_WORDS = 150
    MAX_ACCEPTABLE_TBDS = 5
    MIN_CONCRETE_INTERACTIONS = 3
    MIN_ERROR_MENTIONS = 2
    MIN_EDGE_MENTIONS = 2

    # Section header patterns (pre-compiled)
    SECTION_PATTERNS = {
        'acceptance_criteria': re.compile(r'^#+\s*Acceptance Criteria', re.IGNORECASE | re.MULTILINE),
        'technical_approach': re.compile(r'^#+\s*Technical Approach', re.IGNORECASE | re.MULTILINE),
        'dependencies': re.compile(r'^#+\s*Dependencies', re.IGNORECASE | re.MULTILINE),
        'nfrs': re.compile(r'^#+\s*Non-Functional Requirements', re.IGNORECASE | re.MULTILINE),
        'risks': re.compile(r'^#+\s*Risks', re.IGNORECASE | re.MULTILINE),
    }

    # Gap indicator patterns
    TBD_PATTERNS = [
        r'\bTBD\b',
        r'\bto be determined\b',
        r'\bwill add later\b',
        r'\bto be defined\b',
        r'\bpending\b',
    ]

    PLACEHOLDER_PATTERNS = [
        r'\.\.\.+',
        r'\bTODO\b',
        r'<[^>]*placeholder[^>]*>',
        r'\[TBD\]',
    ]

    # Technical detail patterns
    ERROR_PATTERNS = [
        r'\berror\b',
        r'\bfail(?:ure|s|ed)?\b',
        r'\binvalid\b',
        r'\bexception\b',
        r'\breturns?\s+4\d{2}\b',  # HTTP 4xx
        r'\breturns?\s+5\d{2}\b',  # HTTP 5xx
    ]

    EDGE_CASE_PATTERNS = [
        r'\bedge case\b',
        r'\bboundary\b',
        r'\bconcurren(?:t|cy)\b',
        r'\brace condition\b',
        r'\bdeadlock\b',
        r'\boverload\b',
        r'\bthrottle\b',
        r'\bretry\b',
    ]

    VERSION_PATTERNS = [
        r'v?\d+\.\d+(?:\.\d+)?(?:-[a-z0-9]+)?',  # v1.2.3 or 1.2-alpha
        r'version\s+\d+\.\d+',
        r'>=?\s*\d+\.\d+',
        r'OpenShift\s+4\.\d+',
        r'Kubernetes\s+1\.\d+',
        r'PostgreSQL\s+\d+',
    ]

    # Interaction type detection patterns
    INTERACTION_PATTERNS = {
        'REST_API': [
            r'`(?:GET|POST|PUT|DELETE|PATCH)\s+/[a-z0-9/_\-{}\?&=]+',
            r'/api/v?\d+/[a-z0-9/_\-]+',
        ],
        'UI': [
            r'\bdashboard\b',
            r'\bUI\s+(?:flow|interaction)\b',
            r'\b(?:click|select|fill|submit)\s+.*(?:button|form|field)',
            r'\bpage\s+>\s+',  # Navigation breadcrumb
        ],
        'CLI': [
            r'`kubectl\s+',
            r'`oc\s+',
            r'`odh-cli\s+',
            r'`[a-z]+-cli\s+',
        ],
        'CRD': [
            r'\bCustom\s+Resource\s+Definition\b',
            r'\b[A-Z][a-zA-Z]*(?:Ref|Config|Policy)\b',  # CRD name patterns
            r'\bCR\s+with\s+spec\b',
            r'\.spec\.',
            r'\.status\.',
        ],
        'OPERATOR': [
            r'\bcontroller\s+reconciles\b',
            r'\boperator\s+(?:handles|manages)\b',
            r'\breconciliation\s+logic\b',
        ],
        'SDK': [
            r'`client\.[a-z]+\.',
            r'\bSDK\s+method\b',
            r'\bprogrammatic\s+(?:API|interface)\b',
        ],
        'CONFIG': [
            r'\bConfigMap\b',
            r'\bconfiguration\s+file\b',
            r'\.yaml\s+with\s+fields',
        ],
    }

    # Acceptance criteria format pattern (pre-compiled)
    GIVEN_WHEN_THEN_PATTERN = re.compile(r'\b(?:Given|When|Then|Measured by)\b', re.IGNORECASE)

    def __init__(self, strat_content: str):
        self.content = strat_content
        self.content_lower = strat_content.lower()

    def _extract_section(self, section_name: str) -> Optional[str]:
        """Extract content of a specific section"""
        pattern = self.SECTION_PATTERNS.get(section_name)
        if not pattern:
            return None

        match = pattern.search(self.content)
        if not match:
            return None

        # Determine the header level of this section
        header_match = re.match(r'^(#+)', self.content[match.start():match.end()], re.MULTILINE)
        if header_match:
            header_level = len(header_match.group(1))
        else:
            header_level = 2  # Default assumption

        start = match.end()
        # Find next section header at SAME or HIGHER level (not subsections)
        # Header level N should stop at headers with N or fewer hashes
        next_pattern = rf'\n^#{{1,{header_level}}}\s+[^\s]'
        next_section = re.search(next_pattern, self.content[start:], re.MULTILINE)
        end = start + next_section.start() if next_section else len(self.content)

        return self.content[start:end]

    def _count_patterns(self, patterns: List[str], text: Optional[str] = None) -> int:
        """Count occurrences of regex patterns"""
        if text is None:
            text = self.content_lower

        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, text, re.IGNORECASE))
        return count

    def _detect_interaction_types(self) -> tuple[List[str], int]:
        """Detect which interaction types are present and count concrete examples"""
        detected = set()
        concrete_count = 0

        for interaction_type, patterns in self.INTERACTION_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, self.content, re.IGNORECASE | re.MULTILINE)
                if matches:
                    detected.add(interaction_type)
                    # Count concrete examples (backtick-wrapped or with paths)
                    concrete_count += sum('`' in str(m) or '/' in str(m) for m in matches)

        return list(detected), concrete_count

    def _analyze_acceptance_criteria(self, ac_section: Optional[str]) -> tuple[str, int, int]:
        """Analyze acceptance criteria format and count"""
        if not ac_section:
            return "none", 0, 0

        # Check for Given-When-Then format
        gwt_matches = len(self.GIVEN_WHEN_THEN_PATTERN.findall(ac_section))
        if gwt_matches >= 4:  # At least one full Given-When-Then-Measured cycle
            # Count criteria by "Given" occurrences
            # Handle: "- Given", "* Given", "1. Given", "2) Given", or plain "Given"
            criteria_count = len(re.findall(r'^\s*(?:[-*]|\d+[.)])?\s*Given\b', ac_section, re.IGNORECASE | re.MULTILINE))
            word_count = len(ac_section.split())
            return "given-when-then", criteria_count, word_count

        # Check for checkbox format
        checkbox_count = len(re.findall(r'-\s*\[\s*\]', ac_section))
        if checkbox_count >= 1:
            word_count = len(ac_section.split())
            return "checkbox", checkbox_count, word_count

        # Other format - count bullet points
        criteria_count = len(re.findall(r'^\s*[-*]\s+', ac_section, re.MULTILINE))
        word_count = len(ac_section.split())
        return "other", criteria_count, word_count

    def _calculate_structural_score(self, data: dict) -> int:
        """Calculate overall structural score (0-10) based on presence and quality"""
        score = 0

        # Required sections (0-4 points)
        if data['has_acceptance_criteria']:
            score += 1
        if data['has_technical_approach']:
            score += 1
        if data['has_dependencies']:
            score += 1
        if data['has_nfrs'] or data['has_risks']:
            score += 1

        # Content completeness (0-2 points)
        # Only award points if there's actual content (not empty STRAT)
        tbd_total = data['tbd_count'] + data['placeholder_count']
        has_content = data['technical_approach_word_count'] > 0 or data['acceptance_criteria_count'] > 0

        if has_content and tbd_total == 0:
            score += 2
        elif has_content and tbd_total <= 2:
            score += 1
        # Empty content gets 0 points (no content bonus)

        # Technical detail (0-2 points)
        if data['technical_approach_word_count'] >= self.MIN_DETAILED_TECHNICAL_APPROACH_WORDS:
            score += 1
        if data['error_case_mentions'] >= self.MIN_ERROR_MENTIONS or data['edge_case_mentions'] >= self.MIN_EDGE_MENTIONS:
            score += 1

        # Interaction mechanisms (0-2 points)
        if data['detected_interaction_types']:
            score += 1
        if data['concrete_interactions_count'] >= self.MIN_CONCRETE_INTERACTIONS:
            score += 1

        return min(score, 10)

    def validate(self) -> StructuralValidationResult:
        """Run all structural validation checks"""
        warnings = []

        # Check section presence
        has_ac = bool(self._extract_section('acceptance_criteria'))
        has_ta = bool(self._extract_section('technical_approach'))
        has_deps = bool(self._extract_section('dependencies'))
        has_nfrs = bool(self._extract_section('nfrs'))
        has_risks = bool(self._extract_section('risks'))

        # Extract sections
        ac_section = self._extract_section('acceptance_criteria')
        ta_section = self._extract_section('technical_approach')
        deps_section = self._extract_section('dependencies')

        # Analyze acceptance criteria
        ac_format, ac_count, ac_word_count = self._analyze_acceptance_criteria(ac_section)

        # Count quality indicators
        tbd_count = self._count_patterns(self.TBD_PATTERNS)
        placeholder_count = self._count_patterns(self.PLACEHOLDER_PATTERNS)
        error_mentions = self._count_patterns(self.ERROR_PATTERNS)
        edge_mentions = self._count_patterns(self.EDGE_CASE_PATTERNS)
        version_count = self._count_patterns(
            self.VERSION_PATTERNS,
            (deps_section or '') + (ta_section or '')
        )

        # Detect interactions
        interaction_types, concrete_count = self._detect_interaction_types()

        # Word counts
        ta_word_count = len(ta_section.split()) if ta_section else 0

        # Dependencies
        dep_count = len(re.findall(r'^\s*[-*]', deps_section, re.MULTILINE)) if deps_section else 0
        deps_have_versions = version_count > 0 if dep_count > 0 else False

        # Generate warnings using data-driven rules
        warning_rules = [
            (not has_ac, "CRITICAL: Missing Acceptance Criteria section"),
            (has_ac and ac_count == 0, "Acceptance Criteria section exists but is empty"),
            (not has_ta, "CRITICAL: Missing Technical Approach section"),
            (has_ta and ta_word_count < self.MIN_TECHNICAL_APPROACH_WORDS, f"Technical Approach is very short ({ta_word_count} words) - may lack detail for test plan generation"),
            (tbd_count > self.MAX_ACCEPTABLE_TBDS, f"High number of TBD markers ({tbd_count}) - indicates incomplete STRAT"),
            (not interaction_types, "CRITICAL: No concrete interaction mechanisms detected (API, UI, CLI, CRD, etc.) - test plan Section 4 will be empty"),
            (interaction_types and concrete_count == 0, "Interaction types mentioned but no concrete examples (specific endpoints, commands, CR specs)"),
            (error_mentions == 0, "No error cases mentioned - test plan will lack error scenario coverage"),
            (edge_mentions == 0, "No edge cases mentioned - test plan may miss boundary conditions and concurrency scenarios"),
            (dep_count > 0 and not deps_have_versions, "Dependencies listed but no version requirements specified - test environment will have TBDs"),
        ]

        warnings = [msg for condition, msg in warning_rules if condition]

        # Build result dict for scoring
        result_dict = {
            'has_acceptance_criteria': has_ac,
            'has_technical_approach': has_ta,
            'has_dependencies': has_deps,
            'has_nfrs': has_nfrs,
            'has_risks': has_risks,
            'acceptance_criteria_format': ac_format,
            'acceptance_criteria_count': ac_count,
            'acceptance_criteria_word_count': ac_word_count,
            'tbd_count': tbd_count,
            'placeholder_count': placeholder_count,
            'error_case_mentions': error_mentions,
            'edge_case_mentions': edge_mentions,
            'version_specifications': version_count,
            'detected_interaction_types': interaction_types,
            'concrete_interactions_count': concrete_count,
            'technical_approach_word_count': ta_word_count,
            'dependency_count': dep_count,
            'dependencies_have_versions': deps_have_versions,
            'warnings': warnings,
            'structural_score': 0,  # Calculate below
        }

        result_dict['structural_score'] = self._calculate_structural_score(result_dict)

        return StructuralValidationResult(**result_dict)


def validate_strat_file(strat_file: str) -> StructuralValidationResult:
    """Validate a STRAT file and return results"""
    with open(strat_file, 'r') as f:
        content = f.read()
    validator = StratStructuralValidator(content)
    return validator.validate()


def main():
    parser = argparse.ArgumentParser(
        description='Validate STRAT structure for test plan readiness')
    parser.add_argument('strat_file', help='Path to STRAT markdown file')
    args = parser.parse_args()

    result = validate_strat_file(args.strat_file)
    print(json.dumps(asdict(result), indent=2))


if __name__ == '__main__':
    main()
