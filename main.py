import copy
import json
import random
import re
from typing import Dict, Iterable, List


ASSIGNMENT_PATTERN = re.compile(r"(?:^|;)\s*(?:var\s+)?([A-Za-z_]\w*)\s*=")


def iter_preorder_nodes(tree: Dict) -> Iterable[Dict]:
    yield tree
    for child in tree.get("children", []):
        yield from iter_preorder_nodes(child)


def extract_defined_names(action_code: str) -> List[str]:
    return ASSIGNMENT_PATTERN.findall(action_code)


def place_actions_randomly(tree: Dict, actions: List[Dict], seed: int | None = None) -> Dict:
    """Randomly place actions onto preorder tree nodes without breaking dependencies.

    The input tree is expected to use the shape {"name": str, "children": [node, ...]}.
    Each action must be a mapping with "action" and "dependencies" keys. Random placement
    is performed across preorder node positions, but the selected positions always increase
    so the supplied action list still executes in order. A ValueError is raised when the
    tree has too few nodes or when an action depends on names that are not yet available
    during preorder execution.
    """
    placed_tree = copy.deepcopy(tree)
    nodes = list(iter_preorder_nodes(placed_tree))

    if len(nodes) < len(actions):
        raise ValueError("The tree does not have enough nodes for all actions.")

    rng = random.Random(seed)
    scheduled_actions = []
    next_allowed_index = 0

    for action_index, action in enumerate(actions):
        remaining_actions = len(actions) - action_index - 1
        max_index = len(nodes) - remaining_actions - 1
        node_index = rng.randint(next_allowed_index, max_index)
        scheduled_actions.append((node_index, action))
        next_allowed_index = node_index + 1

    for node_index, action in scheduled_actions:
        node = nodes[node_index]
        node.setdefault("_scheduled_actions", []).append(action)

    available_symbols = set()
    for node in iter_preorder_nodes(placed_tree):
        existing_actions = list(node.get("actions", []))
        for existing_action in existing_actions:
            available_symbols.update(extract_defined_names(existing_action))

        scheduled_for_node = node.pop("_scheduled_actions", [])
        if not scheduled_for_node:
            continue

        node.setdefault("actions", [])
        for action in scheduled_for_node:
            missing = [name for name in action.get("dependencies", []) if name not in available_symbols]
            if missing:
                raise ValueError(
                    f"Action {action['action']!r} cannot be placed because dependencies are missing: {missing}"
                )

            node["actions"].append(action["action"])
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
