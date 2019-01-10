import unittest
import subprocess
import os
import sys
import tempfile
import contextlib
import subprocess
import shutil

TOPDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Python script to simulate running doxygen
DOXYGEN = """
from __future__ import print_function
import os
import sys

if len(sys.argv) >= 2 and sys.argv[1] == '-s':
    for name in ('FILE_VERSION_FILTER', 'LAYOUT_FILE', 'PROJECT_NAME',
                 'INPUT', 'SEARCHENGINE', 'TOC_INCLUDE_HEADINGS',
                 'IMAGE_PATH', 'HTML_HEADER', 'HTML_FOOTER', 'GENERATE_LATEX',
                 'TAGFILES'):
        print("%-23s=" % name)
    sys.exit(0)

def make_file(subdir, fname, contents):
    with open(os.path.join(subdir, fname), 'w') as fh:
        fh.write(contents)

os.mkdir('html')
make_file('html', 'index.html', "$(function() {\\n  initMenu('',false,false,'search.php','Search');\\n});\\n")
"""

@contextlib.contextmanager
def temporary_directory(dir=None):
    """Make a temporary directory"""
    tempd = tempfile.mkdtemp(dir=dir)
    yield tempd
    shutil.rmtree(tempd)

@contextlib.contextmanager
def mock_doxygen(topdir):
    """Make a mock 'doxygen' binary and add it to the PATH"""
    bindir = os.path.join(topdir, 'bin')
    os.mkdir(bindir)
    dox = os.path.join(bindir, 'doxygen')
    with open(dox, 'w') as fh:
        fh.write("#!%s\n%s" % (sys.executable, DOXYGEN))
    os.chmod(dox, 493) # 493 = octal 0755, i.e. executable
    oldpath = os.environ['PATH']
    os.environ['PATH'] = bindir + ':' + oldpath
    yield None
    os.environ['PATH'] = oldpath
    shutil.rmtree(bindir)

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
            with mock_doxygen(tmpdir):
                subprocess.check_call([make_docs], cwd=docdir)
            # Check for generated outputs
            os.unlink(os.path.join(docdir, 'manual-tags.xml'))
            os.unlink(os.path.join(docdir, 'ref-tags.xml'))
            os.unlink(os.path.join(docdir, 'Doxyfile'))
            os.unlink(os.path.join(docdir, 'html', 'index.html'))

if __name__ == '__main__':
    unittest.main()
