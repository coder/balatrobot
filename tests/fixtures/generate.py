import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import httpx
from tqdm import tqdm

from balatrobot.state import InstanceNotFoundError, StateFile, StateFileNotFound

FIXTURES_DIR = Path(__file__).parent

# JSON-RPC 2.0 request ID counter
_request_id: int = 0


@dataclass
class FixtureSpec:
    paths: list[Path]
    setup: list[tuple[str, dict]]


def api(client: httpx.Client, method: str, params: dict) -> dict:
    """Send a JSON-RPC 2.0 request to BalatroBot."""
    global _request_id
    _request_id += 1

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": _request_id,
    }

    response = client.post("/", json=payload)
    response.raise_for_status()
    data = response.json()

    # Handle JSON-RPC 2.0 error responses
    if "error" in data:
        return {"error": data["error"]}

    return data.get("result", {})


def corrupt_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"CORRUPTED_SAVE_FILE_FOR_TESTING\x00\x01\x02")


def load_fixtures_json() -> dict:
    with open(FIXTURES_DIR / "fixtures.json") as f:
        return json.load(f)


def steps_to_setup(steps: list[dict]) -> list[tuple[str, dict]]:
    return [(step["method"], step["params"]) for step in steps]


def steps_to_key(steps: list[dict]) -> str:
    return json.dumps(steps, sort_keys=True, separators=(",", ":"))


def aggregate_fixtures(json_data: dict) -> list[FixtureSpec]:
    setup_to_paths: dict[str, list[Path]] = defaultdict(list)
    setup_to_steps: dict[str, list[dict]] = {}

    for group_name, fixtures in json_data.items():
        if group_name == "$schema":
            continue

        for fixture_name, steps in fixtures.items():
            path = FIXTURES_DIR / group_name / f"{fixture_name}.jkr"
            key = steps_to_key(steps)
            setup_to_paths[key].append(path)
            if key not in setup_to_steps:
                setup_to_steps[key] = steps

    fixtures = []
    for key, paths in setup_to_paths.items():
        steps = setup_to_steps[key]
        setup = steps_to_setup(steps)
        fixtures.append(FixtureSpec(paths=paths, setup=setup))

    return fixtures


def generate_fixture(client: httpx.Client, spec: FixtureSpec, pbar: tqdm) -> bool:
    primary_path = spec.paths[0]
    relative_path = primary_path.relative_to(FIXTURES_DIR)

    try:
        for method, params in spec.setup:
            response = api(client, method, params)
            if isinstance(response, dict) and "error" in response:
                error_msg = response["error"].get("message", str(response["error"]))
                pbar.write(f"  Error: {relative_path} - {error_msg}")
                return False

        primary_path.parent.mkdir(parents=True, exist_ok=True)
        response = api(client, "save", {"path": str(primary_path)})
        if isinstance(response, dict) and "error" in response:
            error_msg = response["error"].get("message", str(response["error"]))
            pbar.write(f"  Error: {relative_path} - {error_msg}")
            return False

        for dest_path in spec.paths[1:]:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(primary_path.read_bytes())

        return True

    except Exception as e:  # noqa: BLE001 - report any failure and continue
        pbar.write(f"  Error: {relative_path} failed: {e}")
        return False


def main() -> int:
    print("BalatroBot Fixture Generator")

    try:
        info = StateFile.resolve()
    except (StateFileNotFound, InstanceNotFoundError) as e:
        print(f"Error: {e}")
        print(
            "Make sure Balatro is running (balatrobot serve --settings turbo --debug --render headfull)"
        )
        return 1

    host, port = info.host, info.port
    print(f"Connecting to {host}:{port}\n")

    json_data = load_fixtures_json()
    fixtures = aggregate_fixtures(json_data)
    print(f"Loaded {len(fixtures)} unique fixture configurations\n")

    try:
        with httpx.Client(
            base_url=f"http://{host}:{port}",
            timeout=httpx.Timeout(60.0, read=10.0),
        ) as client:
            success = 0
            failed = 0

            with tqdm(
                total=len(fixtures), desc="Generating fixtures", unit="fixture"
            ) as pbar:
                for spec in fixtures:
                    if generate_fixture(client, spec, pbar):
                        success += 1
                    else:
                        failed += 1
                    pbar.update(1)

            api(client, "menu", {})

            corrupted_path = FIXTURES_DIR / "load" / "corrupted.jkr"
            corrupt_file(corrupted_path)
            success += 1

            print(f"\nSummary: {success} generated, {failed} failed")
            return 1 if failed > 0 else 0

    except httpx.ConnectError:
        print(f"Error: Could not connect to Balatro at {host}:{port}")
        print("Make sure Balatro is running with BalatroBot mod loaded")
        return 1
    except httpx.TimeoutException:
        print(f"Error: Connection timeout to Balatro at {host}:{port}")
        return 1
    except Exception as e:  # noqa: BLE001 - top-level error reporting
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
