import unittest
import subprocess
import re
import os
import sys
import utils
import subprocess
import contextlib
import shutil

TOPDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def import_make_docs():
    import importlib.util
    make_docs = os.path.join(TOPDIR, "doxygen", "make-docs.py")
    name = os.path.splitext(make_docs)[0]
    spec = importlib.util.spec_from_file_location(name, make_docs)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

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
    make_file('html', 'index.html', "$(function() {\\n  initMenu('',false,false,'search.php','Search');\\n});\\n<hr class=\\"footer\\"/>\\n")
    make_file('html', 'pages.html', 'foo')
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
    make_file(docdir, "other.md", "Other {#other}\n=====\n\n")
    os.mkdir(support)
    make_file(support, "metadata.yaml", "title: Intro\n")
    return docdir

class Tests(unittest.TestCase):
    def test_complete(self):
        """Test simple complete run of make-docs.py"""
        make_docs = os.path.join(TOPDIR, "doxygen", "make-docs.py")
        with utils.temporary_directory(TOPDIR) as tmpdir:
            docdir = _make_docs(tmpdir)
            make_file(tmpdir, "LICENSE", "Some random license")
            with mock_doxygen(tmpdir):
                subprocess.check_call([make_docs], cwd=docdir)
            with open(os.path.join(docdir, 'html', 'index.html')) as fh:
                contents = fh.read()
            self.assertFalse("creativecommons.org" in contents)
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
            make_file(tmpdir, "LICENSE",
                      "Attribution-ShareAlike 4.0 International")
            with mock_doxygen(tmpdir):
                subprocess.check_call([make_docs, '--branch', 'main'],
                                      cwd=docdir)
            with open(os.path.join(docdir, 'html', 'index.html')) as fh:
                contents = fh.read()
            self.assertTrue("creativecommons.org" in contents)
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
                self.assertTrue('OSError: doxygen failed' in stderr,
                                msg="bad stderr %s" % stderr)

    def test_read_yaml_file(self):
        """Test read_yaml_file"""
        make_docs = import_make_docs()
        with utils.temporary_directory(TOPDIR) as tmpdir:
            make_file(tmpdir, "m.yaml", "bar: baz\ntitle: Intro\nfoo: bar\n")
            t = make_docs.read_yaml_file(os.path.join(tmpdir, 'm.yaml'))
            self.assertEqual(t, "Intro")

    def test_get_pagename(self):
        """Test get_pagename"""
        r = re.compile(r'{#(\S+)}')
        make_docs = import_make_docs()
        with utils.temporary_directory(TOPDIR) as tmpdir:
            make_file(tmpdir, "good.md", "# title {#anchor}\nfoo\nbar")
            make_file(tmpdir, "bad.md", "# title\nfoo\nbar")
            n = make_docs.get_pagename(os.path.join(tmpdir, "good.md"), r)
            self.assertEqual(n, "anchor")
            self.assertRaises(ValueError, make_docs.get_pagename,
                              os.path.join(tmpdir, "bad.md"), r)

if __name__ == '__main__':
    unittest.main()
