#!/usr/bin/env python

"""
Generate documentation for a tutorial.

To use, make documentation in the tutorial's 'doc' subdirectory as doxygen
input files (usually in markdown format, .md).

Run this script from the doc directory, as
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
import glob
import re
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

# Absolute path to the top of the repository
TOPDIR = os.path.abspath('..')

# Path to this directory (containing doxygen inputs)
DOXDIR = os.path.abspath(os.path.dirname(__file__))

def get_title():
    """Get the title of the repository by reading the metadata.yaml file"""
    fnames = [os.path.join(TOPDIR, subdir, 'metadata.yaml')
              for subdir in ('support', 'metadata')]
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
    urltop = 'https://integrativemodeling.org'
    # Generate doxygen template
    p = subprocess.Popen(['doxygen', '-s', '-g', '-'], stdout=subprocess.PIPE,
                         universal_newlines=True)
    # Substitute in our custom config
    with open('Doxyfile', 'w') as fh:
        for line in p.stdout:
            if line.startswith('LAYOUT_FILE '):
                line = 'LAYOUT_FILE = %s/layout.xml\n' % DOXDIR
            elif line.startswith('PROJECT_NAME '):
                line = 'PROJECT_NAME = "%s"\n' % title
            elif line.startswith('INPUT '):
                line = 'INPUT = .\n'
            elif line.startswith('SEARCHENGINE '):
                line = 'SEARCHENGINE = NO\n'
            elif line.startswith('TOC_INCLUDE_HEADINGS '):
                line = 'TOC_INCLUDE_HEADINGS = 2\n'
            elif line.startswith('IMAGE_PATH '):
                line = 'IMAGE_PATH = images\n'
            elif line.startswith('HTML_HEADER '):
                line = 'HTML_HEADER = %s/header.html\n' % DOXDIR
            elif line.startswith('HTML_FOOTER '):
                line = 'HTML_FOOTER = %s/footer.html\n' % DOXDIR
            elif line.startswith('GENERATE_LATEX '):
                line = 'GENERATE_LATEX = NO\n'
            elif line.startswith('TAGFILES '):
                line = ('TAGFILES = ref-tags.xml=%s/nightly/doc/ref/ '
                        'manual-tags.xml=%s/nightly/doc/manual/\n'
                        % (urltop, urltop))
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

def get_git_branch():
    return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref',
                                    'HEAD'],
                                   universal_newlines=True).rstrip('\r\n')

def get_git_repo():
    url = subprocess.check_output(['git', 'config', '--get',
                                   'remote.origin.url'],
                                   universal_newlines=True)
    m = re.search('\/(\S+)\.git', url)
    return m.group(1)

def get_pagename(filename, regex):
    with open(filename) as fh:
        for line in fh:
            m = regex.search(line)
            if m:
                return m.group(1)
    raise ValueError("Could not determine page name for file %s" % filename)

def get_page_map():
    m = {}
    page_name_md_re = re.compile('{#(\S+)}')
    for md in glob.glob("*.md"):
        pagename = get_pagename(md, page_name_md_re)
        if pagename == 'mainpage':
            pagename = 'index'
        m['html/%s.html' % pagename] = md
    return m

def add_github_edit_links():
    branch = get_git_branch()
    repo = get_git_repo()
    pagemap = get_page_map()
    for html in glob.glob("html/*.html"):
        if html != 'html/pages.html':
            patch_html(html, repo, pagemap[html], branch)

def patch_html(filename, repo, source, branch):
    edit_link = '  $(\'#main-menu\').append(\'<li style="float:right"><div id="github_edit"><a href="https://github.com/salilab/%s/blob/%s/doc/%s"><i class="fab fa-github"></i> Edit on GitHub</a></div></li>\');\n' % (repo, branch, source)

    with open(filename) as fh:
        contents = fh.readlines()
    patched = False
    with open(filename, 'w') as fh:
        for line in contents:
            fh.write(line)
            if line.startswith("  initMenu('',false,false"):
                patched = True
                fh.write(edit_link)
    if not patched:
        raise ValueError("Failed to patch %s to add GitHub-edit link"
                         % filename)

def main():
    make_doxyfile()
    get_tag_files()
    run_doxygen()
    add_github_edit_links()

if __name__ == '__main__':
    main()
