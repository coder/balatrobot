"""Harbor on Flash Eval: a task per task of a Harbor dataset, and one unmodified Harbor trial per trial.

Harbor starts the task's Sandboxes in the release's App, tagged with the job and the attempt so that the platform ends
any it leaves running, runs the agent in them, then the tests, and the trial scores the reward the tests write. The
agent reaches the target through the model relay with a key for this trial alone, from the runner or, for an agent
installed in the task's Sandbox, at the relay's public URL, so Harbor's files, which become the trial's artifacts, never
hold the target's credentials. This module is the only Harbor-specific code; each
evaluation chooses its dataset and the fields of its tasks.
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self

import modal_evals as evals
from pydantic import ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from harbor.models.trial.config import AgentConfig
    from harbor.models.trial.result import TrialResult as HarborTrialResult

# Harbor's agents a job may run. Terminus 2 and the oracle run in the runner; the others are common coding agents that
# Harbor installs into the task's Sandbox, which call the target from there.
Agent = Literal[
    "terminus-2",
    "oracle",
    "claude-code",
    "openhands-sdk",
    "mini-swe-agent",
    "opencode",
]
# The parameters only Terminus 2 reads.
TERMINUS_PARAMS = ("temperature", "max_turns")


@dataclass(frozen=True)
class AgentRelease:
    """The release of an installed agent that every trial of a Flash Eval release installs, rather than the latest one
    Harbor installs otherwise, so that jobs compare: `version`, and the packages its installer resolves with uv or npm
    as they were published by `packages_as_of`."""

    version: str
    packages_as_of: str


PACKAGES_AS_OF = "2026-10-20T00:00:00Z"
AGENT_RELEASES = {
    "claude-code": AgentRelease("2.1.304", PACKAGES_AS_OF),
    "openhands-sdk": AgentRelease("1.56.0", PACKAGES_AS_OF),
    # LiteLLM 1.106.0, of 2026-10-18, imports `mcp` without depending on it, which fails mini-SWE-agent at start.
    "mini-swe-agent": AgentRelease("2.4.6", "2026-10-17T00:00:00Z"),
    "opencode": AgentRelease("1.19.3", PACKAGES_AS_OF),
}
# Where Terminus 2 finds its key to the model, for this process's trial.
AGENT_KEY_VARIABLE = "OPENAI_API_KEY"
# The Agent Trajectory Interchange Format, in which Harbor's agents record each step.
ATIF_MEDIA_TYPE = "application/vnd.harbor.atif+json"
# The context window agents assume when the target doesn't report its model's, and their longest answer.
DEFAULT_CONTEXT_LENGTH = 131_072
MAX_OUTPUT_TOKENS = 16_384
# The files of Harbor's trial directory a trial saves first, then the rest in order, up to this many.
FIRST_ARTIFACTS = (
    "agent/trajectory.json",
    "result.json",
    "exception.txt",
    "verifier/reward.json",
    "verifier/ctrf.json",
    "verifier/test-stdout.txt",
    "trial.log",
)
MAX_SAVED_FILES = 150
# A Sandbox the trial starts outlives the trial's deadline by at most this long, should nothing end it sooner, within
# the longest timeout Modal gives a Sandbox.
SANDBOX_GRACE_SECONDS = 120
MAX_SANDBOX_TIMEOUT_SECONDS = 24 * 60 * 60
# Harbor's defaults for what a task's task.toml leaves out: building an environment, setting up Terminus 2 or the
# oracle, running each of the tests' collect hooks, and running the tests.
HARBOR_BUILD_TIMEOUT_SECONDS = 600
HARBOR_AGENT_SETUP_TIMEOUT_SECONDS = 360
HARBOR_COLLECT_TIMEOUT_SECONDS = 60
HARBOR_VERIFIER_TIMEOUT_SECONDS = 600
# Time a trial spends outside Harbor's limits: starting Sandboxes, their healthchecks, and saving the trial's files.
TRIAL_OVERHEAD_SECONDS = 15 * 60

# The target turned the agent away, which every trial would meet, so the trial fails rather than scoring 0.
TARGET_REFUSED = frozenset(
    {
        "AgentAuthenticationError",
        "ApiKeyRejectedError",
        "ApiProviderResourceNotFoundError",
        "ApiUsageLimitError",
        "AuthenticationError",
        "ModelNotFoundError",
    }
)
# The environment or the target failed before the tests could run, in a way another attempt may not.
RETRYABLE = frozenset(
    {
        "AgentSetupTimeoutError",
        "ApiConnectionClosedError",
        "ApiConnectionError",
        "ApiInternalServerError",
        "ApiOverloadedError",
        "ApiRateLimitError",
        "ApiResponseStalledError",
        "EnvironmentStartTimeoutError",
        "HealthcheckError",
        "NetworkConnectionError",
        "SandboxBuildFailedError",
        "SandboxLikelyOutOfMemoryError",
    }
)

# LiteLLM fetches its model prices from the internet as it starts, and without network access, as DeepSWE's agents
# work, the failed fetch can crash it; this keeps it to the prices it ships with.
LITELLM_OFFLINE = {"LITELLM_LOCAL_MODEL_COST_MAP": "True"}

Tokens = Annotated[int, evals.Unit("tokens")]


class HarborParams(evals.Params):
    agent: Agent = Field(
        default="terminus-2",
        description=(
            "Agent that solves each task using the target as its model. Claude Code requires the Anthropic Messages"
            " API, which vLLM serves. oracle runs the reference solutions to validate the tasks, not the target."
        ),
    )
    temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
        description="Sampling temperature. Terminus 2 only. Defaults to the target's setting.",
    )
    max_turns: int | None = Field(
        default=None,
        ge=1,
        le=10_000,
        description="Maximum number of model calls. Terminus 2 only. Unlimited if not set.",
    )
    context_length: int | None = Field(
        default=None,
        ge=4_096,
        le=10_000_000,
        description=(
            "Context window size, in tokens. Defaults to the size the target reports, or"
            f" {DEFAULT_CONTEXT_LENGTH:,}. Ignored by OpenHands."
        ),
    )

    # Submission validates parameters against the schema, so the schema states the rule the validator below enforces.
    model_config = ConfigDict(
        json_schema_extra={
            "if": {
                "properties": {"agent": {"not": {"const": "terminus-2"}}},
                "required": ["agent"],
            },
            "then": {
                "properties": {name: {"type": "null"} for name in TERMINUS_PARAMS}
            },
        }
    )

    @model_validator(mode="after")
    def only_terminus_takes_its_settings(self) -> Self:
        named = [name for name in TERMINUS_PARAMS if getattr(self, name) is not None]
        if self.agent != "terminus-2" and named:
            raise ValueError(
                f"{', '.join(named)} applies only to terminus-2, not {self.agent}"
            )
        return self


class HarborResult(evals.TrialResult):
    """What Harbor reports of a trial, as its own job summaries count it: the tests' reward, whether the trial ended
    in an error and which, how long the agent worked, and the tokens it used. Each test's output is among the trial's
    files."""

    # From 0 to 1, so the mean over tasks reads as the share solved.
    reward: Annotated[evals.Ratio, evals.HigherIsBetter, evals.Label("Solved")]
    # A trial that ended in an exception, as Harbor counts its errors, such as an agent that timed out.
    errored: Annotated[bool, evals.LowerIsBetter, evals.Label("Errors")]
    exception: Annotated[str, evals.Label("Exception")] | None
    agent_seconds: Annotated[evals.Seconds, evals.Label("Agent time")] | None
    input_tokens: Annotated[Tokens, evals.Label("Input tokens")] | None
    cached_input_tokens: Annotated[Tokens, evals.Label("Cached input tokens")] | None
    output_tokens: Annotated[Tokens, evals.Label("Output tokens")] | None


def task_time_limit(name: str, config: dict[str, Any]) -> float:
    """The longest a trial of a task may take under its own time limits, from its task.toml, as Harbor applies them:
    building its environment, setting up the agent, the agent, the tests' collect hooks, and the tests. Tests that run
    in an environment of their own, as they do once they declare one unless they say otherwise, start it within the
    same build timeout as the agent's."""
    if config.get("steps"):
        raise ValueError(
            f"Task {name!r} has steps, which the Harbor adapter doesn't run"
        )
    agent = config.get("agent", {})
    if agent.get("timeout_sec") is None:
        raise ValueError(
            f"Task {name!r} sets no agent timeout, so nothing bounds a trial of it"
        )
    build = config.get("environment", {}).get(
        "build_timeout_sec", HARBOR_BUILD_TIMEOUT_SECONDS
    )
    verifier = config.get("verifier", {})
    separate = (
        verifier.get(
            "environment_mode", "separate" if "environment" in verifier else "shared"
        )
        == "separate"
    )
    return (
        build * (2 if separate else 1)
        + HARBOR_AGENT_SETUP_TIMEOUT_SECONDS
        + agent["timeout_sec"]
        + sum(
            hook.get("timeout_sec", HARBOR_COLLECT_TIMEOUT_SECONDS)
            for hook in verifier.get("collect", [])
        )
        + verifier.get("timeout_sec", HARBOR_VERIFIER_TIMEOUT_SECONDS)
    )


async def run_trial[R: HarborResult](
    ctx: evals.TrialContext[HarborParams, Any],
    task_directory: Path,
    result_type: type[R] = HarborResult,  # type: ignore[assignment]
) -> R:
    """One Harbor trial of the task in `task_directory`, its artifacts saved, as Flash Eval counts it; the tests'
    other rewards fill the fields `result_type` adds."""
    from harbor.models.trial.config import EnvironmentConfig, TaskConfig, TrialConfig
    from harbor.trial.trial import Trial

    # The container serves later trials, which read the key the agent's key replaces, as a target's Secret may set it.
    target_key = os.environ.get(AGENT_KEY_VARIABLE)
    trials_dir = Path(tempfile.mkdtemp(prefix="harbor-trials-"))
    try:
        config = TrialConfig(
            task=TaskConfig(path=task_directory),
            trials_dir=trials_dir,
            agent=await _agent(ctx),
            environment=EnvironmentConfig(
                type="modal",
                kwargs={
                    # The release's App holds the trial's Sandboxes, and their tags let the platform end them.
                    "app_name": ctx.app_name,
                    "labels": ctx.sandbox_tags,
                    "sandbox_timeout_secs": min(
                        MAX_SANDBOX_TIMEOUT_SECONDS,
                        max(
                            60, int(ctx.deadline - time.time()) + SANDBOX_GRACE_SECONDS
                        ),
                    ),
                },
            ),
        )
        result = await (await Trial.create(config)).run()
        _save_artifacts(ctx, trials_dir / result.trial_name)
    finally:
        if target_key is None:
            os.environ.pop(AGENT_KEY_VARIABLE, None)
        else:
            os.environ[AGENT_KEY_VARIABLE] = target_key
        shutil.rmtree(trials_dir, ignore_errors=True)
    return harbor_result(result, result_type)


async def _agent(ctx: evals.TrialContext[HarborParams, Any]) -> AgentConfig:
    from harbor.models.trial.config import AgentConfig

    params = ctx.params
    if params.agent == "oracle":
        return AgentConfig(name="oracle")
    if params.agent == "terminus-2":
        return _terminus(ctx)
    access = await ctx.target.sandbox_access()
    context_length = _context_length(params, access)
    model_name, env, options = installed_agent_settings(
        params.agent, access.base_url, access.api_key, access.model, context_length
    )
    release = AGENT_RELEASES[params.agent]
    # Harbor sets the environment in the agent's setup too, where uv and npm resolve its packages.
    env |= {
        "UV_EXCLUDE_NEWER": release.packages_as_of,
        "npm_config_before": release.packages_as_of,
    }
    return AgentConfig(
        name=params.agent,
        model_name=model_name,
        # Harbor sets these in each of the agent's commands, and leaves their values out of the files it writes.
        env=env,
        kwargs=options | {"version": release.version},
        # A task whose agent runs without network access, as DeepSWE's do, still reaches the relay.
        extra_allowed_hosts=[urllib.parse.urlsplit(access.base_url).hostname or ""],
    )


def installed_agent_settings(
    agent: str, target_url: str, api_key: str, model: str, context_length: int
) -> tuple[str, dict[str, str], dict[str, object]]:
    """How Harbor's agent `agent`, installed in the task's Sandbox, calls `model` at `target_url`, the target's base URL
    as the relay mirrors it, with `api_key`, and keeps its history within `context_length` where it takes a window:
    its model name, its environment, and its options."""
    base_url = target_url if target_url.endswith("/v1") else f"{target_url}/v1"
    max_output_tokens = min(MAX_OUTPUT_TOKENS, context_length // 4)
    match agent:
        case "claude-code":
            # Claude Code calls `<base>/v1/messages`, which reaches the target's Messages API, beside its chat
            # completions, only when the target's version path is `/v1` or none.
            path = urllib.parse.urlsplit(target_url).path
            if path and not path.endswith("/v1"):
                raise evals.TrialError(
                    "TARGET_UNSUPPORTED",
                    f"Claude Code needs a target whose base URL ends in /v1, not {path!r}, to reach its Messages API",
                )
            anthropic = {
                "ANTHROPIC_API_KEY": api_key,
                "ANTHROPIC_BASE_URL": base_url.removesuffix("/v1"),
            }
            # Claude Code assumes a model it doesn't know has a 200,000-token window.
            return (
                model,
                {**anthropic, "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(context_length)},
                {},
            )
        case "openhands-sdk":
            return (
                f"openai/{model}",
                {"LLM_API_KEY": api_key, "LLM_BASE_URL": base_url, **LITELLM_OFFLINE},
                {},
            )
        case "mini-swe-agent":
            # LiteLLM knows neither the target's model's window nor its price, which mini-SWE-agent otherwise counts as
            # an error.
            registry = {
                f"openai/{model}": {
                    "max_input_tokens": context_length - max_output_tokens,
                    "max_output_tokens": max_output_tokens,
                    "input_cost_per_token": 0.0,
                    "output_cost_per_token": 0.0,
                    "litellm_provider": "openai",
                    "mode": "chat",
                }
            }
            env = {
                "OPENAI_API_KEY": api_key,
                "OPENAI_BASE_URL": base_url,
                "MSWEA_COST_TRACKING": "ignore_errors",
                **LITELLM_OFFLINE,
            }
            return f"openai/{model}", env, {"litellm_model_registry": registry}
        case "opencode":
            # OpenCode's `openai` provider speaks the Responses API, so the target is a provider of its own.
            provider = {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": base_url, "apiKey": "{env:TARGET_API_KEY}"},
                "models": {
                    model: {
                        "limit": {
                            "context": context_length,
                            "output": max_output_tokens,
                        }
                    }
                },
            }
            return (
                f"target/{model}",
                {"TARGET_API_KEY": api_key},
                {"opencode_config": {"provider": {"target": provider}}},
            )
    raise ValueError(f"{agent!r} isn't an agent installed in the task's Sandbox")


def _terminus(ctx: evals.TrialContext[HarborParams, Any]) -> AgentConfig:
    from harbor.models.trial.config import AgentConfig

    params = ctx.params
    access = ctx.target.scoped_access()
    base_url = (
        access.base_url if access.base_url.endswith("/v1") else f"{access.base_url}/v1"
    )
    # LiteLLM, which Terminus 2 calls the model with from this process, reads the key from the environment, so
    # Harbor's files never record it.
    os.environ[AGENT_KEY_VARIABLE] = access.api_key
    context_length = _context_length(params, access)
    max_output_tokens = min(MAX_OUTPUT_TOKENS, context_length // 4)
    options: dict[str, object] = {
        "api_base": base_url,
        "model_info": {
            "max_input_tokens": context_length - max_output_tokens,
            "max_output_tokens": max_output_tokens,
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        },
        # A recording needs asciinema in the task's Image, which it need not have.
        "record_terminal_session": False,
    }
    if params.temperature is not None:
        options["temperature"] = params.temperature
    if params.max_turns is not None:
        options["max_turns"] = params.max_turns
    return AgentConfig(
        name="terminus-2", model_name=f"openai/{access.model}", kwargs=options
    )


def _context_length(params: HarborParams, access: evals.ScopedAccess) -> int:
    return (
        params.context_length
        or _reported_context_length(access)
        or DEFAULT_CONTEXT_LENGTH
    )


def _reported_context_length(access: evals.ScopedAccess) -> int | None:
    """The context window the target's `/models` reports for the model, as `max_model_len` (vLLM, SGLang) or
    `context_length`, if it reports one."""
    base_url = (
        access.base_url if access.base_url.endswith("/v1") else f"{access.base_url}/v1"
    )
    request = urllib.request.Request(
        f"{base_url}/models", headers={"Authorization": f"Bearer {access.api_key}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            models = json.loads(response.read()).get("data", [])
    except (OSError, ValueError, AttributeError):
        return None
    lengths = [
        entry.get(field)
        for entry in models
        if isinstance(entry, dict) and entry.get("id") == access.model
        for field in ("max_model_len", "context_length")
    ]
    return next(
        (length for length in lengths if isinstance(length, int) and length > 0), None
    )


def _media_type(path: str) -> str:
    if path == "agent/trajectory.json":
        return ATIF_MEDIA_TYPE
    if path.endswith((".log", ".pane", ".txt", ".md", ".sh", ".py", ".patch", ".diff")):
        return "text/plain"
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _save_artifacts(
    ctx: evals.TrialContext[HarborParams, Any], trial_dir: Path
) -> None:
    """Save Harbor's trial files, the trajectory, result, and tests' output first, up to `MAX_SAVED_FILES`."""
    if not trial_dir.is_dir():
        return
    files = {
        path.relative_to(trial_dir).as_posix(): path
        for path in trial_dir.rglob("*")
        if path.is_file()
    }
    first = [name for name in FIRST_ARTIFACTS if name in files]
    ordered = first + sorted(name for name in files if name not in first)
    for name in ordered[:MAX_SAVED_FILES]:
        ctx.save_file(name, files[name], media_type=_media_type(name))


def _seconds(started_at: datetime | None, finished_at: datetime | None) -> float | None:
    if started_at is None or finished_at is None:
        return None
    return (finished_at - started_at).total_seconds()


def harbor_result[R: HarborResult](
    result: HarborTrialResult, result_type: type[R] = HarborResult
) -> R:  # type: ignore[assignment]
    """The trial as Flash Eval counts it.

    A trial whose tests wrote a reward is that reward. One without, because the agent or the tests failed, scores 0,
    as Harbor's own metrics count it, unless the target turned the agent away, which fails the trial, or the
    environment or the target failed in a way another attempt may not, which retries it. A trial whose agent never
    started measured nothing, so whatever failed, it retries.
    """
    exception = result.exception_info
    rewards = (result.verifier_result.rewards if result.verifier_result else None) or {}
    if not rewards and exception is not None:
        detail = f"{exception.exception_type}: {exception.exception_message}"[:2000]
        if exception.exception_type in TARGET_REFUSED:
            raise evals.TrialError("TARGET_REFUSED", detail)
        if exception.exception_type in RETRYABLE or result.agent_execution is None:
            raise evals.TrialError("HARBOR_TRIAL_INTERRUPTED", detail, retryable=True)
    agent = result.agent_result
    reward = rewards.get("reward", next(iter(rewards.values()), 0.0))
    extra = {
        name: rewards[name]
        for name in result_type.model_fields
        if name in rewards and name not in HarborResult.model_fields
    }
    return result_type(
        **extra,
        reward=min(max(float(reward), 0.0), 1.0),
        errored=exception is not None,
        exception=None if exception is None else exception.exception_type,
        agent_seconds=_seconds(
            result.agent_execution.started_at, result.agent_execution.finished_at
        )
        if result.agent_execution
        else None,
        input_tokens=agent.n_input_tokens if agent else None,
        cached_input_tokens=agent.n_cache_tokens if agent else None,
        output_tokens=agent.n_output_tokens if agent else None,
    )
