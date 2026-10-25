import unittest
from app import response_text

class AppTest(unittest.TestCase):
    def test_response(self):
        self.assertEqual(response_text(), "CI/CD demo is running\n")

if __name__ == "__main__":
    unittest.main()
