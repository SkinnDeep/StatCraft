"""StatCraft Connect — Reusable Connected Workflows (Phase 7).

Enables saving, parameterizing, validating, and replaying connected statistical
workflows across worksheets with column mapping, assumption auditing, and output convergence comparison.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .model import Worksheet
from .recipes import run, columns as recipe_columns


class WorkflowValidationError(Exception):
    """Raised when a worksheet fails column or assumption requirements for a workflow."""
    pass


@dataclass
class WorkflowStep:
    """A single executable step in a connected analysis chain."""
    step_id: str
    action: str
    parameters: Dict[str, Any]
    role_bindings: Dict[str, str] = field(default_factory=dict)  # role -> col_name
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectedWorkflow:
    """A reusable, durable workflow chain connecting StatCraft, JMP, and R steps."""
    workflow_id: str
    title: str
    description: str
    created_at: str
    steps: List[WorkflowStep]
    source_worksheet_name: str
    baseline_metrics: Dict[str, Any] = field(default_factory=dict)
    assumptions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at,
            "source_worksheet_name": self.source_worksheet_name,
            "baseline_metrics": self.baseline_metrics,
            "assumptions": self.assumptions,
            "steps": [asdict(s) for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectedWorkflow":
        steps = [
            WorkflowStep(
                step_id=s.get("step_id", str(uuid.uuid4())[:8]),
                action=s.get("action", ""),
                parameters=copy.deepcopy(s.get("parameters", {})),
                role_bindings=copy.deepcopy(s.get("role_bindings", {})),
                metadata=copy.deepcopy(s.get("metadata", {})),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            workflow_id=data.get("workflow_id", f"wf-{uuid.uuid4().hex[:10]}"),
            title=data.get("title", "Connected Workflow"),
            description=data.get("description", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            steps=steps,
            source_worksheet_name=data.get("source_worksheet_name", ""),
            baseline_metrics=copy.deepcopy(data.get("baseline_metrics", {})),
            assumptions=copy.deepcopy(data.get("assumptions", {})),
        )


def create_workflow_from_entry(
    entry: Dict[str, Any],
    worksheet: Worksheet,
    title: Optional[str] = None,
    description: str = "",
) -> ConnectedWorkflow:
    """Create a reproducible ConnectedWorkflow from a fitted history entry."""
    recipe = entry.get("recipe", {})
    action = recipe.get("action", "")
    params = copy.deepcopy(recipe.get("parameters", {}))
    result = entry.get("result", {})

    role_bindings: Dict[str, str] = {}
    if "response_index" in params and 0 <= params["response_index"] < len(worksheet.columns):
        role_bindings["response"] = worksheet.columns[params["response_index"]].name

    if "predictor_indices" in params:
        p_names = [worksheet.columns[i].name for i in params["predictor_indices"] if 0 <= i < len(worksheet.columns)]
        for idx, nm in enumerate(p_names):
            role_bindings[f"predictor_{idx}"] = nm

    if "factor_indices" in params:
        f_names = [worksheet.columns[i].name for i in params["factor_indices"] if 0 <= i < len(worksheet.columns)]
        for idx, nm in enumerate(f_names):
            role_bindings[f"factor_{idx}"] = nm

    for single_param, role_name in (
        ("index", "variable"),
        ("index1", "sample_1"),
        ("index2", "sample_2"),
        ("time_index", "time"),
        ("event_index", "event"),
        ("factor_index", "factor"),
        ("exposure_index", "exposure"),
    ):
        val = params.get(single_param)
        if isinstance(val, int) and 0 <= val < len(worksheet.columns):
            role_bindings[role_name] = worksheet.columns[val].name

    for list_param, role_prefix in (
        ("response_indices", "resp_list"),
        ("covariate_indices", "covariate"),
        ("fixed_indices", "fixed"),
        ("random_indices", "random"),
    ):
        if list_param in params and isinstance(params[list_param], (list, tuple)):
            for idx, ci in enumerate(params[list_param]):
                if isinstance(ci, int) and 0 <= ci < len(worksheet.columns):
                    role_bindings[f"{role_prefix}_{idx}"] = worksheet.columns[ci].name

    step = WorkflowStep(
        step_id=f"step-1",
        action=action,
        parameters=params,
        role_bindings=role_bindings,
        metadata={"original_title": entry.get("title", "")},
    )

    baseline: Dict[str, Any] = {}
    if "r_squared" in result:
        baseline["r_squared"] = result.get("r_squared")
    if "adjusted_r_squared" in result:
        baseline["adjusted_r_squared"] = result.get("adjusted_r_squared")
    if "residual_stdev" in result:
        baseline["residual_stdev"] = result.get("residual_stdev")
    if "f" in result:
        baseline["f_statistic"] = result.get("f")
    if "count" in result:
        baseline["count"] = result.get("count")

    # Baseline coefficients
    coefs = result.get("coefficients", [])
    if coefs:
        baseline["coefficients"] = copy.deepcopy(coefs)

    wf_title = title or f"Workflow — {entry.get('title', action)}"

    return ConnectedWorkflow(
        workflow_id=f"wf-{uuid.uuid4().hex[:10]}",
        title=wf_title,
        description=description or f"Automated workflow capturing {action} across worksheets.",
        created_at=datetime.now().isoformat(),
        steps=[step],
        source_worksheet_name=getattr(worksheet, "name", "Data"),
        baseline_metrics=baseline,
        assumptions={
            "min_observations": baseline.get("count", 3),
            "require_numeric": True,
        },
    )


def validate_workflow_compatibility(
    workflow: ConnectedWorkflow,
    target_worksheet: Worksheet,
) -> Tuple[bool, Dict[str, int], List[str], List[str]]:
    """Verify whether a target worksheet satisfies the workflow's column requirements.

    Returns:
        (is_compatible, role_to_column_index_map, missing_roles, warnings)
    """
    col_names_map = {col.name.casefold(): idx for idx, col in enumerate(target_worksheet.columns)}
    mapped: Dict[str, int] = {}
    missing: List[str] = []
    warnings: List[str] = []

    for step in workflow.steps:
        for role, expected_name in step.role_bindings.items():
            clean_expected = expected_name.casefold()
            if clean_expected in col_names_map:
                mapped[role] = col_names_map[clean_expected]
            else:
                missing.append(f"{role} (expected '{expected_name}')")

    min_obs = workflow.assumptions.get("min_observations", 0)
    if target_worksheet.row_count < min_obs:
        warnings.append(
            f"Worksheet has {target_worksheet.row_count} rows, which is less than the baseline sample of {min_obs}."
        )

    return (len(missing) == 0, mapped, missing, warnings)


def replay_workflow(
    workflow: ConnectedWorkflow,
    target_worksheet: Worksheet,
    presenter: Any,
    column_mapping: Optional[Dict[str, int]] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Replay a connected workflow on a target worksheet and report convergence against baseline."""
    compatible, auto_mapping, missing, warnings = validate_workflow_compatibility(workflow, target_worksheet)
    effective_mapping = column_mapping or auto_mapping

    if missing and not column_mapping:
        raise WorkflowValidationError(
            f"Cannot replay workflow '{workflow.title}'. Missing required columns:\n"
            + "\n".join(f" - {m}" for m in missing)
        )

    # Switch worksheet context if needed
    orig_ws = presenter.worksheet
    presenter.worksheet = target_worksheet

    replayed_entries = []

    try:
        for step in workflow.steps:
            params = copy.deepcopy(step.parameters)

            # Re-map positional column indices according to resolved roles
            if "response_index" in params and "response" in effective_mapping:
                params["response_index"] = effective_mapping["response"]

            if "predictor_indices" in params:
                new_preds = []
                for idx in range(len(params["predictor_indices"])):
                    role_key = f"predictor_{idx}"
                    if role_key in effective_mapping:
                        new_preds.append(effective_mapping[role_key])
                if new_preds:
                    params["predictor_indices"] = new_preds

            if "factor_indices" in params:
                new_facts = []
                for idx in range(len(params["factor_indices"])):
                    role_key = f"factor_{idx}"
                    if role_key in effective_mapping:
                        new_facts.append(effective_mapping[role_key])
                if new_facts:
                    params["factor_indices"] = new_facts

            for single_param, role_name in (
                ("index", "variable"),
                ("index1", "sample_1"),
                ("index2", "sample_2"),
                ("time_index", "time"),
                ("event_index", "event"),
                ("factor_index", "factor"),
                ("exposure_index", "exposure"),
            ):
                if single_param in params and role_name in effective_mapping:
                    params[single_param] = effective_mapping[role_name]

            for list_param, role_prefix in (
                ("response_indices", "resp_list"),
                ("covariate_indices", "covariate"),
                ("fixed_indices", "fixed"),
                ("random_indices", "random"),
            ):
                if list_param in params and isinstance(params[list_param], (list, tuple)):
                    remapped = [effective_mapping[f"{role_prefix}_{i}"] for i in range(len(params[list_param])) if f"{role_prefix}_{i}" in effective_mapping]
                    if remapped:
                        params[list_param] = remapped

            # Execute step through Presenter/Recipes
            recipe = {"action": step.action, "parameters": params}
            entry = run(presenter, recipe)
            replayed_entries.append(entry)

    finally:
        if not overwrite:
            presenter.worksheet = orig_ws

    # Assess convergence & parameter shift against baseline
    convergence: Dict[str, Any] = {"converged": True, "shifts": []}
    if replayed_entries and workflow.baseline_metrics:
        last_result = replayed_entries[-1].get("result", {})
        base_r2 = workflow.baseline_metrics.get("r_squared")
        curr_r2 = last_result.get("r_squared")
        if base_r2 is not None and curr_r2 is not None:
            r2_shift = curr_r2 - base_r2
            convergence["shifts"].append({
                "metric": "R-Squared",
                "baseline": base_r2,
                "current": curr_r2,
                "difference": r2_shift,
                "status": "Improved" if r2_shift > 0.05 else ("Degraded" if r2_shift < -0.05 else "Consistent"),
            })

        base_s = workflow.baseline_metrics.get("residual_stdev")
        curr_s = last_result.get("residual_stdev")
        if base_s is not None and curr_s is not None:
            s_ratio = curr_s / base_s if base_s > 0 else 1.0
            convergence["shifts"].append({
                "metric": "Residual Std Error (s)",
                "baseline": base_s,
                "current": curr_s,
                "ratio": s_ratio,
                "status": "Stable" if 0.8 <= s_ratio <= 1.25 else "Shifted Variance",
            })

    return {
        "success": True,
        "workflow_id": workflow.workflow_id,
        "workflow_title": workflow.title,
        "entries": replayed_entries,
        "warnings": warnings,
        "convergence": convergence,
    }
