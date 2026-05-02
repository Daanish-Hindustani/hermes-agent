"""Run Hermes against ProteinMPNN binder scenarios with simulated tools."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from experiments.rfd3_binder_skill_optimization.simulated_tools import SimulatedProteinTools
from experiments.rfd3_binder_skill_optimization.transcript import ToolCall, Transcript

from .dataset import Scenario


SIMULATED_TOOLS = {
    "inspect_structure",
    "rfd3_design",
    "protein_mpnn_design",
    "esmfold_predict",
    "alphafold2_multimer_predict",
}


def run_hermes_scenario(
    *,
    skill_text: str,
    reference_skill_text: str,
    scenario: Scenario,
    model: str = "",
    provider: str | None = None,
    api_mode: str | None = None,
    max_iterations: int = 12,
) -> Transcript:
    from run_agent import AIAgent

    simulator = SimulatedProteinTools(scenario.mock_tools)
    system_message = _system_message(skill_text, reference_skill_text)

    with _patch_protein_tools(simulator):
        agent = AIAgent(
            provider=provider,
            api_mode=api_mode,
            model=model,
            enabled_toolsets=["protein_design"],
            skip_memory=True,
            skip_context_files=True,
            quiet_mode=True,
            max_iterations=max_iterations,
        )
        result = agent.run_conversation(scenario.prompt, system_message=system_message)

    return Transcript(
        tool_calls=[ToolCall(name=call["name"], args=call["args"]) for call in simulator.calls],
        final_response=str(result.get("final_response") or ""),
    )


def run_candidate(
    *,
    skill_text: str,
    reference_skill_text: str,
    scenarios: list[Scenario],
    model: str = "",
    provider: str | None = None,
    api_mode: str | None = None,
) -> dict[str, Transcript]:
    return {
        scenario.id: run_hermes_scenario(
            skill_text=skill_text,
            reference_skill_text=reference_skill_text,
            scenario=scenario,
            model=model,
            provider=provider,
            api_mode=api_mode,
        )
        for scenario in scenarios
    }


def load_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _system_message(skill_text: str, reference_skill_text: str) -> str:
    return (
        "You are evaluating binder-only ProteinMPNN skill behavior. Follow the "
        "candidate ProteinMPNN skill exactly. Use the reference binder workflow "
        "only for context; do not optimize or rewrite it during this run.\n\n"
        "## Candidate protein-mpnn-design skill\n\n"
        f"{skill_text}\n\n"
        "## Reference protein-binder-design skill\n\n"
        f"{reference_skill_text}\n"
    )


@contextmanager
def _patch_protein_tools(simulator: SimulatedProteinTools):
    def dispatch(function_name: str, function_args: Any, **kwargs: Any) -> str:
        if function_name in SIMULATED_TOOLS:
            return simulator.handle(function_name, function_args, **kwargs)
        import model_tools

        return model_tools.handle_function_call(function_name, function_args, **kwargs)

    with patch("run_agent.handle_function_call", dispatch):
        yield

