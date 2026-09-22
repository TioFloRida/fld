import unittest

from main import place_actions_randomly


class PlaceActionsRandomlyTests(unittest.TestCase):
    def setUp(self):
        self.tree = {
            "name": "root",
            "children": [
                {
                    "name": "left",
                    "children": [
                        {"name": "left.left", "children": []},
                        {"name": "left.right", "children": []},
                    ],
                },
                {
                    "name": "right",
                    "children": [
                        {"name": "right.left", "children": []},
                        {"name": "right.right", "children": []},
                    ],
                },
            ],
        }

    def collect_actions(self, tree):
        ordered = []

        def walk(node):
            ordered.extend(node.get("actions", []))
            for child in node.get("children", []):
                walk(child)

        walk(tree)
        return ordered

    def collect_action_nodes(self, tree):
        names = []

        def walk(node):
            if node.get("actions"):
                names.append(node["name"])
            for child in node.get("children", []):
                walk(child)

        walk(tree)
        return names

    def test_preserves_execution_order_for_seeded_placement(self):
        actions = [
            {"action": "var A = 1;", "dependencies": []},
            {"action": "var B = 2;", "dependencies": []},
            {"action": "C = A + B;", "dependencies": ["A", "B"]},
        ]

        placed = place_actions_randomly(self.tree, actions, seed=3)

        self.assertEqual(
            self.collect_actions(placed),
            ["var A = 1;", "var B = 2;", "C = A + B;"],
        )
        self.assertEqual(len(self.collect_action_nodes(placed)), 3)

    def test_supports_multiline_assignments(self):
        actions = [
            {"action": "A = 1\nB = 2", "dependencies": []},
            {"action": "C = A + B", "dependencies": ["A", "B"]},
        ]

        placed = place_actions_randomly(self.tree, actions, seed=1)
        self.assertEqual(self.collect_actions(placed), ["A = 1\nB = 2", "C = A + B"])

    def test_raises_for_missing_dependencies(self):
        actions = [
            {"action": "C = A + B;", "dependencies": ["A", "B"]},
        ]

        with self.assertRaises(ValueError):
            place_actions_randomly(self.tree, actions, seed=0)

    def test_raises_when_tree_has_too_few_nodes(self):
        small_tree = {"name": "root", "children": []}
        actions = [
            {"action": "var A = 1;", "dependencies": []},
            {"action": "var B = 2;", "dependencies": []},
        ]

        with self.assertRaises(ValueError):
            place_actions_randomly(small_tree, actions, seed=0)


if __name__ == "__main__":
    unittest.main()
