import json,sys,time
from pathlib import Path
folder=Path(__file__).resolve().parents[1]/'reports/manual-harness-20260916'/sys.argv[1]
pending=folder/'pending.json'
if len(sys.argv)>2:
    old=json.loads(pending.read_text())['turn']
    action=json.loads(sys.argv[2]); note=sys.argv[3] if len(sys.argv)>3 else ''
    target=folder/f'{old:03}-action.json'
    assert not target.exists()
    target.write_text(json.dumps({'action':action,'reason':note},indent=2))
    for _ in range(300):
        if (folder/'result.json').exists():
            r=json.loads((folder/'result.json').read_text())[0]
            print(json.dumps(r['metadata'].get('balatro',r['metadata']),indent=2));sys.exit()
        try:
            if json.loads(pending.read_text())['turn']>old: break
        except json.JSONDecodeError: pass
        time.sleep(.1)
p=json.loads(pending.read_text());print('TURN',p['turn'],'TOKENS',p['input_tokens'])
text=p['visible']; print(text.split('Legal actions now: ',1)[1].split('Gamestate:',1)[0]); state=json.loads(text.split('Gamestate:\n',1)[1]); state.pop('deck',None); state.pop('owned_deck',None); state.pop('run_state',None); state.pop('discard',None); state.pop('hand_stats',None); state.pop('deck_type',None); state.pop('stake',None); state.pop('owned_vouchers',None); state.pop('blind_state',None);
lastfile=folder/'last-display.json'; oldstate=json.loads(lastfile.read_text()) if lastfile.exists() else {}; lastfile.write_text(json.dumps(state)); displayed={k:v for k,v in state.items() if k in ('phase','ante','round','money','blind','hand','hand_groups','consumables','shop','pack','packs','play_commit') or oldstate.get(k)!=v}; print(json.dumps(displayed,separators=(',',':')))
