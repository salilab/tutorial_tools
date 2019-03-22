import unittest
import subprocess
import os
import sys
import utils
import subprocess
import contextlib
import shutil

TOPDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def import_make_docs():
    make_docs = os.path.join(TOPDIR, "doxygen", "make-docs.py")
    name = os.path.splitext(make_docs)[0]
    try:
        import importlib.machinery
        return importlib.machinery.SourceFileLoader(name,
                                                    make_docs).load_module()
    except ImportError:
        import imp
        return imp.load_source(name, make_docs)

# Python script to simulate running doxygen
DOXYGEN = """
from __future__ import print_function
import os
import sys

def make_file(subdir, fname, contents):
    with open(os.path.join(subdir, fname), 'w') as fh:
        fh.write(contents)

if len(sys.argv) >= 2 and sys.argv[1] == '-s':
    for name in ('FILE_VERSION_FILTER', 'LAYOUT_FILE', 'PROJECT_NAME',
                 'INPUT', 'SEARCHENGINE', 'TOC_INCLUDE_HEADINGS',
                 'IMAGE_PATH', 'HTML_HEADER', 'HTML_FOOTER', 'GENERATE_LATEX',
                 'TAGFILES', 'EXAMPLE_PATH'):
        print("%-23s=" % name)
else:
    os.mkdir('html')
    make_file('html', 'index.html', "$(function() {\\n  initMenu('',false,false,'search.php','Search');\\n});\\n")
    make_file('html', 'menudata.js', 'foo')
"""

@contextlib.contextmanager
def mock_doxygen(topdir, retval=0):
    """Make a mock 'doxygen' binary and add it to the PATH"""
    bindir = os.path.join(topdir, 'bin')
    os.mkdir(bindir)
    dox = os.path.join(bindir, 'doxygen')
    with open(dox, 'w') as fh:
        fh.write("#!%s\n%ssys.exit(%d)" % (sys.executable, DOXYGEN, retval))
    os.chmod(dox, 493) # 493 = octal 0755, i.e. executable
    oldpath = os.environ['PATH']
    os.environ['PATH'] = bindir + ':' + oldpath
    yield None
    os.environ['PATH'] = oldpath
    shutil.rmtree(bindir)

def make_file(subdir, fname, contents):
    with open(os.path.join(subdir, fname), 'w') as fh:
        fh.write(contents)

def _make_docs(tmpdir):
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
        with utils.temporary_directory(TOPDIR) as tmpdir:
            docdir = _make_docs(tmpdir)
            with mock_doxygen(tmpdir):
                subprocess.check_call([make_docs], cwd=docdir)
            # Check for generated outputs
            os.unlink(os.path.join(docdir, 'manual-tags.xml'))
            os.unlink(os.path.join(docdir, 'ref-tags.xml'))
            os.unlink(os.path.join(docdir, 'Doxyfile'))
            os.unlink(os.path.join(docdir, 'html', 'index.html'))

    def test_custom_branch(self):
        """Test make-docs.py with manually-specified branch"""
        make_docs = os.path.join(TOPDIR, "doxygen", "make-docs.py")
        with utils.temporary_directory(TOPDIR) as tmpdir:
            docdir = _make_docs(tmpdir)
            with mock_doxygen(tmpdir):
                subprocess.check_call([make_docs, '--branch', 'testbranch'],
                                      cwd=docdir)
            # Check for generated outputs
            os.unlink(os.path.join(docdir, 'manual-tags.xml'))

    def test_import(self):
        """Test import of script as a Python module"""
        make_docs = import_make_docs()

    def test_doxygen_failure(self):
        """Test handling of doxygen failure"""
        make_docs = os.path.join(TOPDIR, "doxygen", "make-docs.py")
        with utils.temporary_directory(TOPDIR) as tmpdir:
            docdir = _make_docs(tmpdir)
            with mock_doxygen(tmpdir, retval=1):
                p = subprocess.Popen([make_docs], cwd=docdir,
                                     universal_newlines=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                stdout, stderr = p.communicate()
                self.assertEqual(p.returncode, 1)
                self.assertTrue('IOError: doxygen failed' in stderr)

if __name__ == '__main__':
    unittest.main()
