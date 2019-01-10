import unittest
import subprocess
import os
import tempfile
import contextlib
import subprocess
import shutil

TOPDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

@contextlib.contextmanager
def temporary_directory(dir=None):
    """Make a temporary directory"""
    tempd = tempfile.mkdtemp(dir=dir)
    yield tempd
    shutil.rmtree(tempd)

def make_file(subdir, fname, contents):
    with open(os.path.join(subdir, fname), 'w') as fh:
        fh.write(contents)

def make_test_docs(tmpdir):
    docdir = os.path.join(tmpdir, 'doc')
    support = os.path.join(tmpdir, 'support')
    os.mkdir(docdir)
    make_file(docdir, "mainpage.md", "Intro {#mainpage}\n=====\n\n")
    os.mkdir(support)
    make_file(support, "metadata.yaml", "title: Intro\n")
    return docdir

class Tests(unittest.TestCase):
    def test_complete(self):
        """Test simple complete run of make-docs.py"""
        make_docs = os.path.join(TOPDIR, "doxygen", "make-docs.py")
        with temporary_directory(TOPDIR) as tmpdir:
            docdir = make_test_docs(tmpdir)
            subprocess.check_call([make_docs], cwd=docdir)
            # Check for generated outputs
            os.unlink(os.path.join(docdir, 'html', 'index.html'))

if __name__ == '__main__':
    unittest.main()
