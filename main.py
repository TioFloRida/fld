import copy
import json
import random
import re
from typing import Dict, Iterable, List


DECLARATION_PATTERN = re.compile(r"^\s*var\s+([A-Za-z_]\w*)\s*=")


def iter_preorder_nodes(tree: Dict) -> Iterable[Dict]:
    yield tree
    for child in tree.get("children", []):
        yield from iter_preorder_nodes(child)


def extract_defined_names(action_code: str) -> List[str]:
    match = DECLARATION_PATTERN.match(action_code)
    return [match.group(1)] if match else []


def place_actions_randomly(tree: Dict, actions: List[Dict], seed: int | None = None) -> Dict:
    placed_tree = copy.deepcopy(tree)
    nodes = list(iter_preorder_nodes(placed_tree))

    if len(nodes) < len(actions):
        raise ValueError("The tree does not have enough nodes for all actions.")

    rng = random.Random(seed)
    chosen_indexes = sorted(rng.sample(range(len(nodes)), len(actions)))
    scheduled_actions = sorted(zip(chosen_indexes, actions), key=lambda item: item[0])

    available_symbols = set()
    for node_index, action in scheduled_actions:
        missing = [name for name in action.get("dependencies", []) if name not in available_symbols]
        if missing:
            raise ValueError(
                f"Action {action['action']!r} cannot be placed because dependencies are missing: {missing}"
            )

        node = nodes[node_index]
        node.setdefault("actions", []).append(action["action"])
        available_symbols.update(extract_defined_names(action["action"]))

    return placed_tree


if __name__ == "__main__":
    tree = {
        "name": "iota",
        "children": [
            {
                "name": "beta",
                "children": [
                    {
                        "name": "gamma",
                        "children": [
                            {
                                "name": "zeta",
                                "children": [
                                    {
                                        "name": "kappa",
                                        "children": [
                                            {"name": "alpha", "children": []},
                                            {"name": "delta", "children": []},
                                        ],
                                    }
                                ],
                            },
                            {
                                "name": "eta",
                                "children": [{"name": "theta", "children": []}],
                            },
                        ],
                    },
                    {"name": "epsilon", "children": []},
                ],
            }
        ],
    }

    actions = [
        {"action": "var A = 10;", "dependencies": []},
        {"action": "var B = 20;", "dependencies": []},
        {"action": "var C = 30;", "dependencies": []},
        {"action": "var D = 40;", "dependencies": []},
        {"action": "D = A + B + C;", "dependencies": ["A", "B", "C"]},
    ]

    result = place_actions_randomly(tree, actions, seed=7)
    print(json.dumps(result, indent=2))
