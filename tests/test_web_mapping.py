import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tundralis.app import INSPECT_ERROR_LOG, app

ROOT = Path(__file__).resolve().parents[1]


class TestWebMapping(unittest.TestCase):
    def test_inspect_renders_original_filename_without_job_prefix(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("File: <strong>Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv</strong>", html)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        stored_filename = html[start: html.index('"', start)]
        self.assertNotEqual(stored_filename, "Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv")
        self.assertTrue(stored_filename.endswith("_Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv"))

    def test_upload_xhr_returns_redirect_url(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("job_id", payload)
        self.assertIn("redirect_url", payload)
        self.assertTrue(payload["redirect_url"].endswith(f"/mapping/{payload['job_id']}"))
        follow = client.get(payload["redirect_url"])
        self.assertEqual(follow.status_code, 200)
        follow_html = follow.get_data(as_text=True)
        self.assertIn("Run KDA", follow_html)
        self.assertIn("Show all candidates", follow_html)

    def test_inspect_renders_column_inspector(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Field inspector", html)
        self.assertIn("Adjust data setup", html)
        self.assertIn("Analysis setup", html)
        self.assertIn("Segments", html)
        self.assertIn("Run KDA", html)
        self.assertIn("Ready to run", html)
        self.assertIn("toggleInspectorButton", html)
        self.assertIn("segmentColumnSearch", html)
        self.assertIn("launchRecodeBuilder", html)
        self.assertIn("semanticOverridesInput", html)
        self.assertIn("Clarify numeric meaning", html)
        self.assertIn("codedCategoryHelperCard", html)
        self.assertIn("Save coded-category labels", html)
        self.assertIn("Use labeled helper in segments", html)
        self.assertIn("Draft starter segment", html)
        self.assertIn("Choose one or more labels to seed an OR segment.", html)
        self.assertIn("Select all", html)
        self.assertIn("Clear", html)
        self.assertIn("rows</span></label>", html)
        self.assertIn("recodeSourceColumnSelector", html)
        self.assertIn("column-selector-search", html)
        self.assertIn("inspectOutcomeButton", html)
        self.assertIn("recommendedOutcomeLabel", html)
        self.assertIn("recommendedOutcomeReason", html)
        self.assertIn("Also considered:", html)
        self.assertNotIn("(12.0)", html)
        self.assertIn("Advanced nested conditions", html)
        self.assertIn("Show advanced", html)
        self.assertIn("segmentTreeCanvas", html)
        self.assertIn("overall_sat", html)
        self.assertIn("high_cardinality", html)
        self.assertIn("client_style_kda.csv", html)

    def test_preview_applies_recode_and_returns_segment_counts(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        inspect_response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        html = inspect_response.get_data(as_text=True)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        filename = html[start: html.index('"', start)]

        response = client.post(
            "/preview",
            json={
                "filename": filename,
                "recode_definitions": [
                    {
                        "type": "map_values",
                        "source_column": "segment",
                        "output_column": "segment_group",
                        "mapping": {
                            "SMB": "Commercial",
                            "Mid-Market": "Commercial",
                            "Enterprise": "Enterprise",
                        },
                    }
                ],
                "segment_definitions": [
                    {
                        "name": "Enterprise only",
                        "tree": {
                            "all": [
                                {"column": "segment_group", "operator": "equals", "value": "Enterprise"}
                            ]
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("segment_group", payload["columns"])
        self.assertEqual(payload["segment_previews"][0]["name"], "Enterprise only")
        self.assertGreater(payload["segment_previews"][0]["matched_count"], 0)

    def test_mapping_page_reloads_recommended_non_numeric_outcome_and_labels(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        job_id = payload["job_id"]
        filename = payload["filename"]

        preview_response = client.post(
            "/preview",
            json={
                "job_id": job_id,
                "filename": filename,
                "target_column": "overall_sat",
                "predictor_columns": ["product_quality_score", "ease_use_score"],
                "display_name_map": {
                    "overall_sat": "Overall satisfaction",
                    "product_quality_score": "Product quality",
                    "ease_use_score": "Ease of use",
                },
            },
        )
        self.assertEqual(preview_response.status_code, 200)

        with patch("tundralis.app._mapping_context") as mocked_context:
            mocked_context.return_value = {
                "job_id": job_id,
                "filename": filename,
                "display_filename": "client_style_kda.csv",
                "columns": ["overall_sat", "product_quality_score", "ease_use_score"],
                "numeric_columns": ["overall_sat", "product_quality_score", "ease_use_score"],
                "inferred_target": "NPS_2",
                "inferred_predictors": ["product_quality_score", "ease_use_score"],
                "predictor_candidates": [],
                "recommendation": {
                    "target": "NPS_2",
                    "predictors": [
                        {"name": "product_quality_score", "kind": "numeric", "warnings": [], "semantic_class": "continuous_numeric", "semantic_confidence": "high"},
                        {"name": "ease_use_score", "kind": "numeric", "warnings": [], "semantic_class": "continuous_numeric", "semantic_confidence": "high"},
                    ],
                    "outcome_candidates": [
                        {"name": "NPS_2", "score": 39.0},
                        {"name": "overall_sat", "score": 31.0},
                    ],
                    "helper_fields": [
                        {"name": "additional_incentive", "reason_labels": ["Administrative/system field"]},
                    ],
                    "candidate_segments": [],
                    "ambiguous_fields": [],
                    "excluded": [],
                    "ambiguity_summary": {"candidate_segments": [], "helper_fields": ["additional_incentive"], "needs_field_semantics": []},
                    "schema_clarity": "described",
                    "driver_pool_count": 2,
                    "driver_shortlist_limit": 24,
                    "usable_rows": 500,
                },
                "column_profiles": {
                    "product_quality_score": {"inferred_type": "numeric", "warnings": []},
                    "ease_use_score": {"inferred_type": "numeric", "warnings": []},
                    "NPS_2": {"inferred_type": "categorical", "warnings": []},
                },
                "column_profile_count": 3,
                "column_profiles_trimmed": False,
                "column_profiles_inline_limit": 25,
                "segment_previews": [],
                "normalized_segment_definitions": [],
                "saved_recode_definitions": [],
                "saved_segment_columns": [],
                "saved_display_name_map": {
                    "NPS_2": "Likelihood to recommend",
                    "product_quality_score": "Product quality",
                    "ease_use_score": "Ease of use",
                },
                "saved_semantic_overrides": {},
            }

            mapping_response = client.get(f"/mapping/{job_id}")

        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn('let currentTarget = "NPS_2"', html)
        self.assertIn('Likelihood to recommend', html)
        self.assertIn('Product quality', html)
        self.assertIn('Ease of use', html)
        self.assertIn('No user-facing helper/admin fields need attention.', html)
        self.assertIn('Field: ${outcome} · Report label: ${outcomeLabel}', html)
        self.assertIn('confirmOutcome.textContent = outcomeLabel || outcomeField;', html)
        self.assertIn('inspectOutcomeButton.textContent = hasResolvedTarget ? (targetLabel || target) :', html)
        self.assertIn('renderRecommendationSummary();', html)

    def test_mapping_page_reloads_saved_draft_state(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        job_id = payload["job_id"]
        filename = payload["filename"]

        preview_response = client.post(
            "/preview",
            json={
                "job_id": job_id,
                "filename": filename,
                "target_column": "overall_sat",
                "predictor_columns": ["product_quality_score", "ease_use_score"],
                "display_name_map": {"overall_sat": "Overall satisfaction"},
                "semantic_overrides": {"overall_sat": "ordinal_numeric", "segment": "labeled_categorical"},
                "recode_definitions": [
                    {
                        "type": "boolean_flag",
                        "source_column": "region",
                        "output_column": "is_apac",
                        "operator": "equals",
                        "value": "APAC",
                    }
                ],
                "segment_definitions": [
                    {
                        "name": "Enterprise only",
                        "tree": {"all": [{"column": "segment", "operator": "equals", "value": "Enterprise"}]},
                    }
                ],
            },
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = client.get(f"/mapping/{job_id}")
        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn('let savedRecodesState = [{', html)
        self.assertIn('"output_column": "is_apac"', html)
        self.assertIn('let savedPredictorSelections = ["product_quality_score", "ease_use_score"]', html)
        self.assertIn('let savedSemanticOverrides = {"overall_sat": "ordinal_numeric", "segment": "labeled_categorical"}', html)
        self.assertIn('schemaConfidenceMeta', html)
        self.assertIn('Object.keys(savedSemanticOverrides || {}).length', html)
        self.assertIn('codedCategoryOutputName', html)
        self.assertIn('preferredSegmentColumns', html)
        self.assertIn('Use labeled helper in segments', html)
        self.assertIn('Draft starter segment', html)
        self.assertIn('Choose one or more labels to seed an OR segment.', html)
        self.assertIn('selectAllHelperLabels', html)
        self.assertIn('clearHelperLabels', html)
        self.assertIn('helperDisplayName', html)
        self.assertIn('suggestSegmentFromLabeledHelper', html)
        self.assertIn('labels.slice(0, 1)', html)
        self.assertIn('chosen.length === 2', html)
        self.assertIn("(+${chosen.length - 2})", html)
        self.assertIn("row.count || 0", html)
        self.assertIn("selectedLabels = Array.from(codedCategoryHelperPanel.querySelectorAll('[data-draft-helper-label]:checked'))", html)
        self.assertIn("input.checked = true", html)
        self.assertIn("input.checked = false", html)
        self.assertIn('hydrateTreeFromDraftRules', html)
        self.assertIn('syncDraftRulesFromTree', html)
        self.assertIn('describeSegmentRule', html)
        self.assertIn('describeSegmentTree', html)
        self.assertIn("key === 'any' ? 'Match any' : 'Match all'", html)
        self.assertIn('<div class="sub small">${escapeHtml(describeSegmentTree(seg.tree))}</div>', html)
        self.assertIn("return nested && nested !== 'No rules saved yet.' ? `(${nested})` : ''", html)
        self.assertNotIn('<pre>${escapeHtml(JSON.stringify(seg.tree, null, 2))}</pre>', html)
        self.assertIn('Loaded segment ${index + 1} into the ${loadedSimple ? \'simple + nested\' : \'nested\'} builder.', html)
        self.assertIn('Editing saved segment', html)
        self.assertIn('Update segment', html)
        self.assertIn('Update nested segment', html)
        self.assertIn('Cancel edit', html)
        self.assertIn('Builder synced for multi-clause editing.', html)
        self.assertIn('labeledHelperSuggestions', html)
        self.assertIn('segmentValueSuggestionCard', html)
        self.assertIn('renderSegmentValueSuggestions', html)
        self.assertIn('Choose a readable helper label below', html)
        self.assertIn('Save coded-category labels', html)
        self.assertIn('Pick an outcome field to continue.', html)
        self.assertNotIn('No numeric outcome available.', html)
        self.assertIn('Overall satisfaction', html)

    def test_mapping_page_reloads_nested_segment_state(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        job_id = payload["job_id"]
        filename = payload["filename"]

        preview_response = client.post(
            "/preview",
            json={
                "job_id": job_id,
                "filename": filename,
                "target_column": "overall_sat",
                "predictor_columns": ["product_quality_score", "ease_use_score"],
                "segment_definitions": [
                    {
                        "name": "Enterprise APAC or Mid-Market EMEA",
                        "tree": {
                            "any": [
                                {
                                    "all": [
                                        {"column": "segment", "operator": "equals", "value": "Enterprise"},
                                        {"column": "region", "operator": "equals", "value": "APAC"},
                                    ]
                                },
                                {
                                    "all": [
                                        {"column": "segment", "operator": "equals", "value": "Mid-Market"},
                                        {"column": "region", "operator": "equals", "value": "EMEA"},
                                    ]
                                },
                            ]
                        },
                    }
                ],
            },
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = client.get(f"/mapping/{job_id}")
        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn('Enterprise APAC or Mid-Market EMEA', html)
        self.assertIn('savedSegmentDefs', html)
        self.assertIn('editingSegmentIndex', html)
        self.assertIn('editingSegmentMode', html)
        self.assertIn('segmentTreeState = treeNodeFromBackend(segment.tree || { all: [] });', html)
        self.assertIn("const nested = describeSegmentTree(child);", html)
        self.assertIn("return nested && nested !== 'No rules saved yet.' ? `(${nested})` : '';", html)
        self.assertNotIn('<pre>${escapeHtml(JSON.stringify(seg.tree, null, 2))}</pre>', html)

    def test_inspect_failure_returns_error_id_and_logs_traceback(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        if INSPECT_ERROR_LOG.exists():
            INSPECT_ERROR_LOG.unlink()

        response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        with patch("tundralis.app.build_prep_bundle", side_effect=ValueError("broken inspect step")):
            mapping_response = client.get(payload["redirect_url"])

        self.assertEqual(mapping_response.status_code, 500)
        html = mapping_response.get_data(as_text=True)
        self.assertIn("Inspect failed", html)
        self.assertTrue(INSPECT_ERROR_LOG.exists())
        log_text = INSPECT_ERROR_LOG.read_text(encoding="utf-8")
        self.assertIn("broken inspect step", log_text)

    def test_inspect_rejects_non_survey_like_file_with_clear_message(self):
        client = app.test_client()
        csv_bytes = (
            b"Date Added,Phone,First name,Last name,Email\n"
            b"2026-01-01,15555550123,Jane,Doe,jane@example.com\n"
            b"2026-01-02,15555550124,John,Smith,john@example.com\n"
        )

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "crm_export.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 500)
        html = response.get_data(as_text=True)
        self.assertIn("This file does not look like survey analysis input", html)
        self.assertIn("does not look like analyzable survey input yet", html)

    def test_inspect_rejects_too_thin_file_with_clear_message(self):
        client = app.test_client()
        csv_bytes = (
            b"Q1,Q2,ResponseId\n"
            b"5,4,R_1\n"
            b"4,5,R_2\n"
        )

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "too_thin.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 500)
        html = response.get_data(as_text=True)
        self.assertIn("This file is too thin for KDA", html)
        self.assertIn("looks too thin for KDA", html)

    def test_results_page_loads_saved_artifacts_for_existing_job(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        job_id = payload["job_id"]
        filename = payload["filename"]

        mapping_state = {
            "target_column": "overall_sat",
            "predictor_columns": ["product_quality_score", "ease_use_score"],
            "segment_columns": [],
            "segment_definitions": [
                {"name": "Enterprise", "tree": {"all": [{"column": "segment", "operator": "equals", "value": "Enterprise"}]}}
            ],
            "recode_definitions": [
                {"type": "boolean_flag", "source_column": "region", "output_column": "is_apac", "operator": "equals", "value": "APAC"}
            ],
            "display_name_map": {"overall_sat": "Overall satisfaction"},
            "semantic_overrides": {},
        }

        with patch("tundralis.app._load_mapping_state", return_value=mapping_state), \
             patch("tundralis.app._mapping_context") as mocked_context, \
             patch("tundralis.app._write_preview_charts", return_value=["importance_bar.png"]):
            mocked_context.return_value = {
                "segment_previews": [{"name": "Enterprise", "matched_count": 120, "matched_pct": 40.0}]
            }
            upload_path = ROOT / "app_runtime" / "uploads" / filename
            upload_path.parent.mkdir(parents=True, exist_ok=True)
            upload_path.write_bytes(csv_bytes)
            job_dir = ROOT / "app_runtime" / "artifacts" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "report.pptx").write_bytes(b"pptx")
            (job_dir / "analysis_run.json").write_text(json.dumps({
                "input_summary": {
                    "rows_modeled": 300,
                    "predictor_columns": ["product_quality_score", "ease_use_score"],
                },
                "model_diagnostics": {
                    "r_squared": 0.41,
                    "adj_r_squared": 0.39,
                    "method_agreement": "high",
                    "nonlinear_signal": "unknown",
                },
                "drivers": [
                    {
                        "driver_label": "Product quality",
                        "classification": "Core Priority",
                        "opportunity": {"rank": 1, "score": 0.88},
                        "performance": {"normalized_mean_0_100": 62.0, "headroom": 0.38},
                        "impact": {"one_point_dv_change": 0.42},
                        "importance": {"share_of_explained_variance": 31.2},
                    },
                    {
                        "driver_label": "Ease of use",
                        "classification": "High-Potential Lever",
                        "opportunity": {"rank": 2, "score": 0.61},
                        "performance": {"normalized_mean_0_100": 71.0, "headroom": 0.29},
                        "impact": {"one_point_dv_change": 0.27},
                        "importance": {"share_of_explained_variance": 18.6},
                    },
                ],
                "segment_summaries": [],
            }), encoding="utf-8")

            response = client.get(f"/results/{job_id}")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Analysis complete", html)
        self.assertIn("client_style_kda.csv", html)
        self.assertIn("Enterprise", html)
        saved_json = (job_dir / "analysis_run.json").read_text(encoding="utf-8")
        self.assertIn("boolean_flag", saved_json)
        self.assertIn("segment_previews", saved_json)

    def test_results_page_404s_when_artifacts_missing(self):
        client = app.test_client()
        response = client.get("/results/notarealjob")
        self.assertEqual(response.status_code, 404)

    def test_mapping_page_includes_recode_create_handler(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        mapping_response = client.get(payload["redirect_url"])
        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn("launchRecodeBuilder?.addEventListener('click'", html)
        self.assertIn("priorIndex !== null ? 'Updated' : 'Created'", html)

    def test_mapping_page_includes_recode_edit_and_remove_handlers(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        mapping_response = client.get(payload["redirect_url"])
        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn("let editingRecodeIndex = null;", html)
        self.assertIn("data-edit-recode", html)
        self.assertIn("data-remove-recode", html)
        self.assertIn("editingRecodeIndex === idx", html)
        self.assertIn("Removed transform", html)

    def test_preview_rejects_invalid_numeric_operator_on_text_column(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        inspect_response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        html = inspect_response.get_data(as_text=True)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        filename = html[start: html.index('"', start)]

        response = client.post(
            "/preview",
            json={
                "filename": filename,
                "segment_definitions": [
                    {
                        "name": "Bad segment",
                        "tree": {
                            "all": [
                                {"column": "segment", "operator": "gt", "value": 5}
                            ]
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn("requires a numeric column", payload["error"])

    def test_run_persists_segment_summaries(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        inspect_response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        html = inspect_response.get_data(as_text=True)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        filename = html[start: html.index('"', start)]
        job_marker = 'name="job_id" value="'
        job_start = html.index(job_marker) + len(job_marker)
        job_id = html[job_start: html.index('"', job_start)]

        response = client.post(
            "/run",
            data={
                "job_id": job_id,
                "filename": filename,
                "target_column": "overall_sat",
                "predictor_columns": [
                    "product_quality_score",
                    "ease_use_score",
                    "support_experience",
                    "value_for_money",
                ],
                "segment_columns": ["segment", "region"],
                "segment_definitions": json.dumps([
                    {
                        "name": "Enterprise only",
                        "tree": {
                            "all": [
                                {"column": "segment", "operator": "equals", "value": "Enterprise"}
                            ]
                        },
                    }
                ]),
                "recode_definitions": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Enterprise only", html)
        self.assertIn("Segment insights", html)
        self.assertIn("Top actions to prioritize", html)
        self.assertIn("Deliverables", html)


if __name__ == "__main__":
    unittest.main()
