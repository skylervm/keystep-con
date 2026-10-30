"""Run upstream emulator assertions with explicit per-model constants.

Only these repository-owned offline suites are loaded. The assertions and real
stock firmware routines stay unchanged. This avoids maintaining duplicate suites
when upstream adds tests. Actual input hashes are checked before execution.
"""
import argparse
import ast
from pathlib import Path
import sys
import types

from firmware_models import CHROMA_LED_FLUSH_CALLS, MODELS, model_address

ROOT = Path(__file__).resolve().parents[1]


class ModelConstants(ast.NodeTransformer):
    def __init__(self, model):
        self.model = model

    def visit_Constant(self, node):
        if type(node.value) is int:
            value = node.value
            if value == 0xFEC and self.model == "chroma":
                value = 0x1000
            else:
                value = model_address(value, self.model)
            return ast.copy_location(ast.Constant(value), node)
        return node


def load_suite(name, model):
    # No arbitrary source paths: callers below choose only known offline suites.
    path = ROOT / "tools" / (name + ".py")
    tree = ModelConstants(model).visit(ast.parse(path.read_text()))
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=tuple(MODELS), required=True)
    args = parser.parse_args()
    MODELS[args.model].read_stock(ROOT / "firmware")
    path = ROOT / "firmware/patched" / ("kscon_" + MODELS[args.model].main_entry)
    pad = load_suite("test_pad_hooks", args.model)
    if args.model == "chroma":
        pad.LED_FLUSH_CALLS = CHROMA_LED_FLUSH_CALLS
    pad.run(path)
    load_suite("kspemu", args.model)
    names = load_suite("test_names_hooks", args.model)
    names.run(path)
    names.chord_pads(path)
    print(f"PASS: complete offline hook suites for {args.model}")


if __name__ == "__main__":
    main()
