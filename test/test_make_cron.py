import unittest
import subprocess
import utils
import os

TOPDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class Tests(unittest.TestCase):
    def test_complete(self):
        """Test simple complete run of make-cron.py"""
        make_cron = os.path.join(TOPDIR, "make-cron.py")
        subprocess.check_call([make_cron])


if __name__ == '__main__':
    unittest.main()
