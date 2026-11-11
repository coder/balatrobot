"""Manual inference bridge for exact Balatro rollout loop, CPU game only."""
import asyncio, json, sys, hashlib, time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import batro_modal_rl as h
@dataclass
class Sample:
    class Status(Enum):
        COMPLETED = 'completed'
        ABORTED = 'aborted'
    prompt: str = ''
    metadata: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)
    index: int = 0
    group_index: int = 0
    rollout_id: int | None = None
for name in ('slime', 'slime.utils', 'slime.utils.types'):
    sys.modules[name] = ModuleType(name)
sys.modules['slime.utils.types'].Sample = Sample
seed = sys.argv[1]
out = ROOT / 'reports/manual-harness-20260916' / seed
out.mkdir(parents=True, exist_ok=False)
args = SimpleNamespace(hf_checkpoint='Qwen/Qwen3.8-27B', balatro_max_decisions=250, balatro_context_len=49152, max_position_embeddings=49152, sglang_context_length=49152, balatro_segment_tokens=8192, balatro_capture_screenshot=True)
pool = h._get_env_pool()
original_acquire = pool.acquire
env_holder = []
def acquire(s):
    env = original_acquire(s)
    env_holder.append(env)
    proc = env.sandbox.exec('cat', '/opt/balatro-assets/CURRENT'); proc.wait()
    release = proc.stdout.read().strip()
    manifest = {'seed': seed, 'release': release, 'sandbox_id': env.sandbox.object_id, 'started_at': time.time(), 'tokenizer': args.hf_checkpoint, 'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('batro_modal_rl.py','balatrobot.lua','training/manual_harness_player.py')}, 'replacement': 'manual inference and Sample result carrier; no model endpoint or GPU'}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    print('SANDBOX '+json.dumps(manifest), flush=True)
    return env
pool.acquire = acquire
turn = 0
async def manual_action(args, sampling_params, input_ids, state_name):
    global turn
    turn += 1
    tokenizer = h._tokenizer(args.hf_checkpoint)
    full_context = tokenizer.decode(input_ids)
    visible = h._turn_prompt(env_holder[0].state)
    request = {'turn': turn, 'state_name': state_name, 'visible': visible, 'input_tokens':len(input_ids)}
    (out/f'{turn:03}-prompt.txt').write_text(full_context)
    (out/f'{turn:03}-request.json').write_text(json.dumps(request, indent=2))
    (out/'pending.json').write_text(json.dumps(request, indent=2))
    print(f'WAITING turn={turn} state={state_name} path={out}/pending.json', flush=True)
    action_path = out/f'{turn:03}-action.json'
    while not action_path.exists():
        await asyncio.sleep(.2)
    payload = json.loads(action_path.read_text())
    action = payload['action']
    response = json.dumps(action, separators=(',',':'))
    ids = tokenizer(response, add_special_tokens=False)['input_ids']
    if len(ids)>96:
        raise ValueError('Manual action exceeds training response token budget')
    print('ACTION '+response, flush=True)
    return ids, response, 'stop', [0.0]*len(ids)
h._generate_action = manual_action
async def main():
    samples = await h.generate_balatro_episode(args, Sample(prompt=seed,metadata={'balatro_seed':seed}), {}, evaluation=True)
    if not isinstance(samples,list): samples=[samples]
    (out/'result.json').write_text(json.dumps([vars(s) for s in samples], default=lambda x:x.value if isinstance(x,Enum) else str(x)))
    print('RESULT '+json.dumps(samples[0].metadata.get('balatro',samples[0].metadata)),flush=True)
asyncio.run(main())
