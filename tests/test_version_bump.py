import unittest
import statcraft
from statcraft import updater

class TestVersionBump(unittest.TestCase):
    def test_version_115(self):
        self.assertEqual(statcraft.__version__, "115.0.0")
        self.assertEqual(updater.STATCRAFT_VERSION, "115.0.0")

if __name__ == "__main__":
    unittest.main()
