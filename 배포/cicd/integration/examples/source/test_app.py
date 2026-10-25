import unittest
from app import render_configmap

class ConfigMapTest(unittest.TestCase):
    def test_revision_is_preserved(self):
        revision = "a" * 40
        result = render_configmap(revision)
        self.assertEqual(result["data"]["revision"], revision)
        self.assertEqual(result["kind"], "ConfigMap")
        self.assertEqual(result["metadata"]["name"], "cicd-demo")

    def test_invalid_revision_is_rejected(self):
        for value in ["", "main", "../wrong", None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                render_configmap(value)

if __name__ == "__main__":
    unittest.main()
