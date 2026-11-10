import unittest
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import get_app_dir, get_env_path, get_db_path, get_history_path

class TestCoreHelpers(unittest.TestCase):
    def test_app_paths(self):
        """Verify helper path functions return absolute paths."""
        app_dir = get_app_dir()
        self.assertTrue(os.path.isabs(app_dir))
        
        env_path = get_env_path()
        self.assertTrue(env_path.endswith(".env"))
        
        db_path = get_db_path()
        self.assertTrue(db_path.endswith("contact.db"))
        
        hist_path = get_history_path()
        self.assertTrue(hist_path.endswith("chat_memory.json"))

if __name__ == "__main__":
    unittest.main()
