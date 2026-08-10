#!/usr/bin/env python3
"""Tests for scripts/validate_strat_testability.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from validate_strat_testability import StratStructuralValidator


# ── Sample Data ───────────────────────────────────────────────────────────────


MINIMAL_STRAT = """## Strategy

### Technical Approach
This is a sample technical approach with sufficient detail to explain what changes
are being made, where they are being made, and why this approach was chosen over
alternatives. It includes concrete implementation details.

### Acceptance Criteria
- [ ] Users can create a new model via the dashboard
- [ ] Users can delete an existing model
- [ ] Changes are reflected in the model list

### Dependencies
- Component A v1.2.0
- Component B v2.0+

### Non-Functional Requirements
- Performance: Response time < 500ms
- Security: RBAC-protected endpoints

### Risks
- Risk 1: Dependency timing
- Risk 2: Schema compatibility
"""

GOOD_STRAT_GWT = """## Strategy

### Technical Approach
Add `POST /api/v1/models` endpoint to create new models in the catalog. The BFF will
validate input, call the model-registry API, and return the created model resource.
Error handling includes validation errors (400), conflicts (409), and backend failures (503).

### Acceptance Criteria
- Given a user has catalog:write permissions, when they POST to `/api/v1/models` with valid model data, then a new model is created in the registry, measured by the model appearing in GET `/api/v1/models` response within 100ms.
- Given a user POSTs invalid model data (missing required fields), when the API validates the request, then a 400 error is returned with field-specific error messages, measured by the response containing validation errors for each missing field.
- Given a model with the same name already exists, when a user POSTs a duplicate, then a 409 Conflict error is returned, measured by the error message indicating the conflicting model name.

### Dependencies
- model-registry v1.5.0+ (for external model support)
- PostgreSQL 13+
- OpenShift 4.14+

### Non-Functional Requirements
- Performance: p95 latency <200ms for model creation
- Security: All operations require catalog:write RBAC permission
- Backwards Compatibility: Existing GET endpoints unchanged

### Risks
- Risk: model-registry latency spikes under load
- Risk: Concurrent creation of same model name
"""

POOR_STRAT = """## Strategy

### Technical Approach
We will add an API for model management. The system will be performant and reliable.

### Acceptance Criteria
- Users can manage models easily
- The system works well
- Good UX

### Dependencies
- Some components TBD

### Non-Functional Requirements
- Should be fast
- Should be secure
"""

OPERATOR_STRAT = """## Strategy

### Technical Approach
Implement MaaSModelRef controller that reconciles ExternalModel provider types. When a
MaaSModelRef CR is created with `.spec.externalModel`, the controller provisions an
Istio VirtualService for egress routing.

### Acceptance Criteria
- Given a platform admin creates a MaaSModelRef CR with `.spec.externalModel.provider=openai`, when the controller reconciles, then an Istio VirtualService is created with routing to api.openai.com, measured by `kubectl get virtualservice` showing the resource.

### Dependencies
- Istio 1.20+
- MaaSModelRef CRD v1alpha1

### Non-Functional Requirements
- Performance: Reconciliation completes within 5s

### Risks
- Risk: Concurrent reconciliation race conditions
"""


# ── Section Detection ─────────────────────────────────────────────────────────


class TestSectionDetection:
    def test_all_sections_present(self):
        validator = StratStructuralValidator(MINIMAL_STRAT)
        result = validator.validate()

        assert result.has_acceptance_criteria
        assert result.has_technical_approach
        assert result.has_dependencies
        assert result.has_nfrs
        assert result.has_risks

    def test_missing_acceptance_criteria(self):
        strat = """### Technical Approach
Content here.
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert not result.has_acceptance_criteria
        assert any("CRITICAL: Missing Acceptance Criteria" in w for w in result.warnings)

    def test_missing_technical_approach(self):
        strat = """### Acceptance Criteria
- [ ] Something
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert not result.has_technical_approach
        assert any("CRITICAL: Missing Technical Approach" in w for w in result.warnings)


# ── Acceptance Criteria Format ────────────────────────────────────────────────


class TestAcceptanceCriteriaFormat:
    def test_given_when_then_format(self):
        validator = StratStructuralValidator(GOOD_STRAT_GWT)
        result = validator.validate()

        assert result.acceptance_criteria_format == "given-when-then"
        assert result.acceptance_criteria_count == 3

    def test_checkbox_format(self):
        validator = StratStructuralValidator(MINIMAL_STRAT)
        result = validator.validate()

        assert result.acceptance_criteria_format == "checkbox"
        assert result.acceptance_criteria_count == 3

    def test_missing_acceptance_criteria(self):
        strat = """### Technical Approach
Content.
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert result.acceptance_criteria_format == "none"
        assert result.acceptance_criteria_count == 0


# ── Quality Indicators ────────────────────────────────────────────────────────


class TestQualityIndicators:
    def test_tbd_counting(self):
        strat = """### Technical Approach
TBD - will add later. This is TBD. Pending details. To be determined.
TBD on approach.
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert result.tbd_count >= 4
        assert any("High number of TBD markers" in w for w in result.warnings)

    def test_error_case_detection(self):
        validator = StratStructuralValidator(GOOD_STRAT_GWT)
        result = validator.validate()

        # "400 error", "409 Conflict error", "validation errors", "fail"
        assert result.error_case_mentions >= 4

    def test_edge_case_detection(self):
        validator = StratStructuralValidator(GOOD_STRAT_GWT)
        result = validator.validate()

        # "concurrent"
        assert result.edge_case_mentions >= 1

    def test_version_detection(self):
        validator = StratStructuralValidator(GOOD_STRAT_GWT)
        result = validator.validate()

        # "v1.5.0+", "13+", "4.14+"
        assert result.version_specifications >= 3


# ── Interaction Type Detection ────────────────────────────────────────────────


class TestInteractionDetection:
    def test_rest_api_detection(self):
        validator = StratStructuralValidator(GOOD_STRAT_GWT)
        result = validator.validate()

        assert 'REST_API' in result.detected_interaction_types
        assert result.concrete_interactions_count >= 2  # POST, GET

    def test_ui_detection(self):
        strat = """### Acceptance Criteria
- User clicks the "Create Model" button on the dashboard
- User fills in the form and submits
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert 'UI' in result.detected_interaction_types

    def test_cli_detection(self):
        strat = """### Acceptance Criteria
- Run `kubectl apply -f model.yaml`
- Run `oc create -f resource.yaml`
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert 'CLI' in result.detected_interaction_types
        assert result.concrete_interactions_count >= 2

    def test_crd_operator_detection(self):
        validator = StratStructuralValidator(OPERATOR_STRAT)
        result = validator.validate()

        assert 'CRD' in result.detected_interaction_types
        assert 'OPERATOR' in result.detected_interaction_types
        assert 'CLI' in result.detected_interaction_types  # kubectl get

    def test_no_interactions_warning(self):
        strat = """### Technical Approach
We will improve the system.

### Acceptance Criteria
- System works well
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert not result.detected_interaction_types
        assert any("No concrete interaction mechanisms detected" in w for w in result.warnings)


# ── Structural Score ──────────────────────────────────────────────────────────


class TestStructuralScore:
    def test_good_strat_high_score(self):
        validator = StratStructuralValidator(GOOD_STRAT_GWT)
        result = validator.validate()

        assert result.structural_score >= 8

    def test_poor_strat_low_score(self):
        validator = StratStructuralValidator(POOR_STRAT)
        result = validator.validate()

        assert result.structural_score <= 5

    def test_minimal_strat_mid_score(self):
        validator = StratStructuralValidator(MINIMAL_STRAT)
        result = validator.validate()

        assert 4 <= result.structural_score <= 7

    def test_empty_strat_zero_score(self):
        validator = StratStructuralValidator("")
        result = validator.validate()

        assert result.structural_score == 0


# ── Warnings ──────────────────────────────────────────────────────────────────


class TestWarnings:
    def test_short_technical_approach_warning(self):
        strat = """### Technical Approach
Add API.

### Acceptance Criteria
- [ ] API works
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert any("Technical Approach is very short" in w for w in result.warnings)

    def test_dependencies_without_versions(self):
        strat = """### Dependencies
- model-registry
- PostgreSQL
- OpenShift
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert result.dependency_count == 3
        assert not result.dependencies_have_versions
        assert any("no version requirements specified" in w for w in result.warnings)

    def test_no_error_cases_warning(self):
        strat = """### Technical Approach
Add endpoint for model creation.

### Acceptance Criteria
- [ ] Models can be created successfully
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert result.error_case_mentions == 0
        assert any("No error cases mentioned" in w for w in result.warnings)

    def test_good_strat_no_critical_warnings(self):
        validator = StratStructuralValidator(GOOD_STRAT_GWT)
        result = validator.validate()

        critical_warnings = [w for w in result.warnings if "CRITICAL" in w]
        assert not critical_warnings


# ── Edge Cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_content(self):
        validator = StratStructuralValidator("")
        result = validator.validate()

        assert result.structural_score == 0
        assert len(result.warnings) >= 2

    def test_only_headers_no_content(self):
        strat = """### Technical Approach

### Acceptance Criteria

### Dependencies
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        assert result.has_technical_approach
        assert result.has_acceptance_criteria
        assert result.has_dependencies
        assert result.technical_approach_word_count == 0
        assert result.acceptance_criteria_count == 0


# ── Integration ───────────────────────────────────────────────────────────────


class TestRealWorldExample:
    def test_rhaistrat_1431_style(self):
        """Test with RHAISTRAT-1431 style content"""
        # Simplified RHAISTRAT-1431
        strat = """## Strategy

### Technical Approach
Deliver a dashboard UI within the existing maas-ui Module Federation plugin for full
MaaSModelRef lifecycle management. The BFF already implements CRUD endpoints at
`/api/v1/maasmodel`. Primary work is building frontend views and extending BFF request
models for ExternalModel fields.

### Acceptance Criteria
- Given a platform admin is on the AI Hub Models page, when they click the MaaS Model Refs tab, then all MaaSModelRef resources in the selected namespace are listed, measured by the list rendering within 2s for up to 200 resources.
- Given a platform admin clicks "Register model ref" and selects Internal type, when they pick an existing LLMInferenceService from the dropdown and submit, then a MaaSModelRef CR is created, measured by `kubectl get maasmodelref` output.

### Dependencies
- RHAISTRAT-1295 (External Model Egress)
- MaaSModelRef CRD schema
- maas-api v2.0+

### Non-Functional Requirements
- Performance: List view < 2s for 200 resources
- Security: Secret values never returned to UI

### Risks
- Risk: Delivery timing dependency
"""
        validator = StratStructuralValidator(strat)
        result = validator.validate()

        # Should have all sections
        assert result.has_acceptance_criteria
        assert result.has_technical_approach
        assert result.has_dependencies

        # Should detect Given-When-Then format
        assert result.acceptance_criteria_format == "given-when-then"
        assert result.acceptance_criteria_count == 2

        # Should detect multiple interaction types
        assert 'UI' in result.detected_interaction_types
        assert 'CRD' in result.detected_interaction_types
        assert 'CLI' in result.detected_interaction_types  # kubectl
        assert 'REST_API' in result.detected_interaction_types  # /api/v1/maasmodel

        # Should have concrete examples
        assert result.concrete_interactions_count >= 2  # /api/v1/maasmodel, kubectl

        # Should detect versions
        assert result.version_specifications >= 1  # v2.0+

        # Should have good score
        assert result.structural_score >= 7

        # Should have no critical warnings
        critical = [w for w in result.warnings if 'CRITICAL' in w]
        assert not critical
