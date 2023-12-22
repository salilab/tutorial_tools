#!/usr/bin/env python3

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
import argparse
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

# Latest IMP stable release
IMP_STABLE_RELEASE = '2.20.0'

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
    with open(fname) as fh:
        for line in fh:
            if line.startswith('title:'):
                return line.split(':', 1)[1].strip()

def make_doxyfile(tags):
    tagfiles = " ".join(("%s=%s" % (t.xml_filename, t.doctop)) for t in tags)
    title = get_title()
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
            elif line.startswith('EXAMPLE_PATH '):
                line = 'EXAMPLE_PATH = ..\n'
            elif line.startswith('HTML_HEADER '):
                line = 'HTML_HEADER = %s/header.html\n' % DOXDIR
            elif line.startswith('HTML_FOOTER '):
                line = 'HTML_FOOTER = %s/footer.html\n' % DOXDIR
            elif line.startswith('GENERATE_LATEX '):
                line = 'GENERATE_LATEX = NO\n'
            elif line.startswith('TAGFILES '):
                line = 'TAGFILES = %s\n' % tagfiles
            fh.write(line)
    ret = p.wait()
    if ret != 0:
        raise OSError("doxygen failed")

class TagFile(object):
    """Represent a doxygen XML tag file"""

    def __init__(self, doctype, imp_version):
        # Path to top of IMP documentation
        self._urltop = 'https://integrativemodeling.org/%s/doc' % imp_version

        # doctype should be 'manual' or 'ref'
        self.doctype = doctype

        # URL for the documentation
        self.doctop = '%s/%s/' % (self._urltop, doctype)

    def download(self):
        """Get the tag file from the web site and put it on the local disk"""
        fname = "%s-tags.xml" % self.doctype
        response = urlopen('%s/%s' % (self._urltop, fname))
        with open(fname, 'wb') as fh:
            fh.write(response.read())
        # Path to the XML tag file on the local disk
        self.xml_filename = fname


def get_tag_files(imp_version):
    tags = [TagFile(doctype, imp_version) for doctype in ('manual', 'ref')]
    for t in tags:
        t.download()
    return tags

def run_doxygen():
    subprocess.check_call(['doxygen', 'Doxyfile'])

def get_git_branch():
    return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref',
                                    'HEAD'],
                                   universal_newlines=True).rstrip('\r\n')

def get_git_repo():
    url = subprocess.check_output(['git', 'config', '--get',
                                   'remote.origin.url'],
                                   universal_newlines=True).rstrip('\r\n')
    pth, repo = os.path.split(url)
    if repo.endswith('.git'):
        repo = repo[:-4]
    return repo

def get_pagename(filename, regex):
    with open(filename) as fh:
        for line in fh:
            m = regex.search(line)
            if m:
                return m.group(1)
    raise ValueError("Could not determine page name for file %s" % filename)

def get_page_map():
    m = {}
    page_name_md_re = re.compile(r'{#(\S+)}')
    for md in glob.glob("*.md"):
        pagename = get_pagename(md, page_name_md_re)
        if pagename == 'mainpage':
            pagename = 'index'
        m['html/%s.html' % pagename] = md
    return m

def get_license():
    fname = '../LICENSE'
    if not os.path.exists(fname):
        return ''
    with open(fname) as fh:
        return fh.read()

def get_license_link():
    license = get_license()
    if 'Attribution-ShareAlike 4.0 International' in license:
        return """
<div class="doxlicense">
  <a href="https://creativecommons.org/licenses/by-sa/4.0/"
     title="This work is available under the terms of the Creative Commons Attribution-ShareAlike 4.0 International license">
    <img src="https://integrativemodeling.org/tutorials/by-sa.svg" alt="CC BY-SA logo">
  </a>
</div>"""
    else:
        return ''

def add_html_links(branch):
    license_link = get_license_link()
    repo = get_git_repo()
    pagemap = get_page_map()
    for html in glob.glob("html/*.html"):
        if html != 'html/pages.html':
            patch_html(html, repo, pagemap[html], branch, license_link)

def patch_html(filename, repo, source, branch, license_link):
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
            if line.startswith('<hr class="footer"'):
                fh.write(license_link)
    if not patched:
        raise ValueError("Failed to patch %s to add GitHub-edit link"
                         % filename)

def fix_menu_links(imp_version):
    # The generated html/menudata.js contains links to the IMP nightly build.
    # Patch this if necessary to make the links go to the stable release
    # instead.
    if imp_version == 'nightly':
        return
    fname = 'html/menudata.js'
    with open(fname, 'r') as fh:
        contents = fh.read()
    with open(fname, 'w') as fh:
        fh.write(contents.replace('nightly', imp_version))

def parse_args():
    parser = argparse.ArgumentParser(description="Build tutorial docs")
    parser.add_argument("--branch",
                  default=None,
                  help="Override automatically-determined git branch")
    return parser.parse_args()

def main():
    args = parse_args()
    branch = args.branch if args.branch else get_git_branch()

    # main branch of tutorials should work with IMP stable release
    # (and so should link to stable docs); other branches use nightly
    imp_version = IMP_STABLE_RELEASE if branch == 'main' else 'nightly'

    tags = get_tag_files(imp_version)
    make_doxyfile(tags)
    run_doxygen()
    add_html_links(branch)
    fix_menu_links(imp_version)

if __name__ == '__main__':
    main()
