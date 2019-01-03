#!/usr/bin/env python

"""
Generate documentation for a tutorial.

To use, make documentation in the tutorial's 'doc' subdirectory as doxygen
input files (usually in markdown format, .md).

Run this script as
../support/tutorial_tools/doxygen/make-docs.py

It will generate a doxygen configuration file (Doxyfile) and download
additional files to make links to the IMP documentation (ref-tags.xml
and manual-tags.xml), then run doxygen to make documentation in the
doc/html/ subdirectory.

The documentation can be rebuilt by just running 'doxygen Doxyfile'.
"""

from __future__ import print_function
import subprocess
import os
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

def get_title():
    """Get the title of the repository by reading the metadata.yaml file"""
    fnames = ('../support/metadata.yaml', '../metadata/metadata.yaml')
    for fname in fnames:
        if os.path.exists(fname):
            return read_yaml_file(fname)
    raise ValueError("Could not find metadata; tried %s"
                     % ", ".join(fnames))

def read_yaml_file(fname):
    # Avoid 'import yaml' since it isn't in the standard library
    for line in open(fname):
        if line.startswith('title:'):
            return line.split(':', 1)[1].strip()

def make_doxyfile():
    title = get_title()
    pth = '../support/tutorial_tools/doxygen'
    # Generate doxygen template
    p = subprocess.Popen(['doxygen', '-s', '-g', '-'], stdout=subprocess.PIPE,
                         universal_newlines=True)
    # Substitute in our custom config
    with open('Doxyfile', 'w') as fh:
        for line in p.stdout:
            if line.startswith('LAYOUT_FILE '):
                line = 'LAYOUT_FILE = %s/layout.xml\n' % pth
            elif line.startswith('PROJECT_NAME '):
                line = 'PROJECT_NAME = "%s"\n' % title
            elif line.startswith('INPUT '):
                line = 'INPUT = .\n'
            elif line.startswith('IMAGE_PATH '):
                line = 'IMAGE_PATH = images\n'
            elif line.startswith('HTML_HEADER '):
                line = 'HTML_HEADER = %s/header.html\n' % pth
            elif line.startswith('HTML_FOOTER '):
                line = 'HTML_FOOTER = %s/footer.html\n' % pth
            elif line.startswith('GENERATE_LATEX '):
                line = 'GENERATE_LATEX = NO\n'
            elif line.startswith('TAGFILES '):
                line = ('TAGFILES = ref-tags.xml=../../nightly/doc/ref/ '
                        'manual-tags.xml=../../nightly/doc/manual/\n')
            fh.write(line)
    ret = p.wait()
    if ret != 0:
        raise IOError("doxygen failed")

def get_tag_files():
    # todo: handle IMP stable build as well as nightly build
    for tag in ('manual-tags.xml', 'ref-tags.xml'):
        get_tag_file(tag)

def get_tag_file(fname):
    urltop = 'https://integrativemodeling.org/nightly/doc'
    response = urlopen('%s/%s' % (urltop, fname))
    with open(fname, 'wb') as fh:
        fh.write(response.read())

def run_doxygen():
    subprocess.check_call(['doxygen', 'Doxyfile'])

def main():
    make_doxyfile()
    get_tag_files()
    run_doxygen()

if __name__ == '__main__':
    main()
