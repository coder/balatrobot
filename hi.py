import itertools

def build(adapters):
    units = iter(())
    for lora_name, tensors in adapters:
        prefixed = (f"{lora_name}:{t}" for t in tensors)
        units = itertools.chain(units, prefixed)
    return list(units)  # consumption happens here, after the loop

print(build([("A", ["w1", "w2"]), ("B", ["w1", "w2"])]))
# prints ['B:w1', 'B:w2', 'B:w1', 'B:w2']
# even though we want ['A:w1', 'A:w2', 'B:w1', 'B:w2']
