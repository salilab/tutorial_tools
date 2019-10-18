import json
import glob
import os
import re
import time
import argparse
import posixpath
import subprocess
import xml.etree.ElementTree as ET
from inventory import InventoryFile
from urllib.request import urlopen


# Latest IMP stable release
IMP_STABLE_RELEASE = '2.11.1'

# Path to doxygen directory (containing doxygen inputs)
DOXDIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                      '..', 'doxygen'))

# Path to templates
TEMPLATE = ".template"


def file_age(fname):
    """Return time in seconds since `fname` was last changed"""
    return time.time() - os.stat(fname).st_mtime


def get_cached_url(url, local):
    cache = os.path.join(TEMPLATE, '.cache')
    if not os.path.exists(cache):
        os.mkdir(cache)
    fname = os.path.join(cache, local)
    # Use file if it already exists and is less than a day old
    if not os.path.exists(fname) or file_age(fname) > 86400:
        response = urlopen(url)
        with open(fname, 'wb') as fh:
            fh.write(response.read())
    return fname


class RefLinks(object):
    """Handle doxygen-style @ref links in markdown"""
    backtick_link = re.compile(r'``([^\s`]+)``')
    ref_link = re.compile('@ref\s+([^\s)]+)')

    def __init__(self):
        #: Mapping from identifier to URL
        self.refs = {}

    def parse_python_inventory_file(self, filename, urltop):
        """Read a Python inventory (intersphinx) file to get @ref targets"""
        with open(filename, 'rb') as fh:
            invdata = InventoryFile.load(fh, urltop, posixpath.join)
        for k, v in invdata.items():
            if k.startswith('py:'):
                for ident, info in v.items():
                    self.refs[ident] = info[2]

    def parse_doxygen_tag_file(self, filename, urltop):
        """Read a doxygen tag file to get @ref targets"""
        root = ET.parse(filename).getroot()
        # Get URLs for every class and namespace:
        for c in root:
            if (c.tag == 'compound'
                and c.attrib.get('kind') in ('class', 'namespace')):
                name = c.find('name').text
                url = urltop + c.find('filename').text
                self.refs[name] = url

    def _replace_backtick_link(self, m):
        txt = m.group(1)
        if txt.startswith('~'):
            short_txt = txt.split('.')[-1].split('::')[-1]
            return '[%s](@ref %s)' % (short_txt, txt[1:])
        else:
            return '[%s](@ref %s)' % (txt, txt)

    def _replace_ref_link(self, m):
        ref = m.group(1)
        link = self.refs.get(ref) or self.refs.get(ref.replace('.', '::'))
        if not link:
            raise ValueError("Bad @ref link to %s" % ref)
        return link

    def fix_links(self, c):
        """Modify and return `c` to replace any @ref links with URLs"""
        c = re.sub(self.backtick_link, self._replace_backtick_link, c)
        return re.sub(self.ref_link, self._replace_ref_link, c)


def patch_source(source, rl):
    for c in source:
        if c.startswith('%intersphinx'):
            url = c.split()[1]
            objfile_url = posixpath.join(url, 'objects.inv')
            objfile = get_cached_url(url=objfile_url,
                local=objfile_url.replace(':', '').replace('/', ''))
            rl.parse_python_inventory_file(objfile, url)
        else:
            yield rl.fix_links(c)

non_jupyter_constructs = re.compile('\[TOC\]|\{#[^\s}]+\}|%%(html|nb)exclude')
def remove_non_jupyter(source, rl):
    for c in source:
        yield re.sub(non_jupyter_constructs, '', c)


def write_cell(cell, fh):
    for s in cell['source']:
        if (not s.startswith('%%htmlexclude')
            and not s.startswith('%%nbexclude')):
            fh.write(s)
    fh.write('\n')


def get_cell_subset(cells, excludestr):
    for cell in cells:
        if not cell['source'] or excludestr not in cell['source'][0]:
            yield cell


def get_only_html_cells(cells):
    return get_cell_subset(cells, excludestr='%%htmlexclude')


def get_only_notebook_cells(cells):
    return get_cell_subset(cells, excludestr='%%nbexclude')


def generate_files(root, tags):
    rl = RefLinks()
    for t in tags:
        rl.parse_doxygen_tag_file(t.xml_filename, t.doctop)

    # Read in the template
    with open('.template/%s.ipynb' % root) as fh:
        j = json.load(fh)

    # Handle our custom magics and @ref links
    for cell in j['cells']:
        if cell['cell_type'] == 'markdown':
            cell['source'] = list(patch_source(cell['source'], rl))

    # Write plain Python script
    with open('%s.py' % root, 'w') as fh:
        for cell in j['cells']:
            if cell['cell_type'] == 'code':
                write_cell(cell, fh)

    # Write markdown suitable for processing with doxygen
    with open('%s.md' % root, 'w') as fh:
        for cell in get_only_html_cells(j['cells']):
            if cell['cell_type'] == 'markdown':
                write_cell(cell, fh)
            elif cell['cell_type'] == 'code':
                fh.write('\\code{.py}\n')
                write_cell(cell, fh)
                fh.write('\\endcode\n')

    # Remove constructs that Jupyter doesn't understand from the JSON
    j['cells'] = list(get_only_notebook_cells(j['cells']))
    for cell in j['cells']:
        if cell['cell_type'] == 'markdown':
            cell['source'] = list(remove_non_jupyter(cell['source'], rl))

    # Write Jupyter notebook
    with open('%s.ipynb' % root, 'w') as fh:
        json.dump(j, fh, indent=2)


def get_git_branch():
    return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref',
                                    'HEAD'],
                                   universal_newlines=True).rstrip('\r\n')


class TagFile(object):
    """Represent a doxygen XML tag file"""

    def __init__(self, doctype, imp_version):
        # Path to top of IMP documentation
        self._urltop = 'https://integrativemodeling.org/%s/doc' % imp_version
        self.imp_version = imp_version

        # doctype should be 'manual' or 'ref'
        self.doctype = doctype

        # URL for the documentation
        self.doctop = '%s/%s/' % (self._urltop, doctype)

    def download(self):
        """Get the tag file from the web site and put it on the local disk"""
        local = "%s-%s-tags.xml" % (self.doctype, self.imp_version)
        remote = "%s/%s-tags.xml" % (self._urltop, self.doctype)
        self.xml_filename = get_cached_url(local=local, url=remote)


def get_tag_files(imp_version):
    tags = [TagFile(doctype, imp_version) for doctype in ('manual', 'ref')]
    for t in tags:
        t.download()
    return tags


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build tutorial docs from a Jupyter notebook template")
    parser.add_argument("filename",
        help="Root name of the notebook template (e.g. 'foo' to use "
             ".template/foo.ipynb)")
    parser.add_argument("--branch",
                  default=None,
                  help="Override automatically-determined git branch")
    return parser.parse_args()


def make_doxyfile(root, tags):
    tagfiles = " ".join(("%s=%s" % (t.xml_filename, t.doctop)) for t in tags)
    title = "IMP Tutorial"
    # Generate doxygen template
    p = subprocess.Popen(['doxygen', '-s', '-g', '-'], stdout=subprocess.PIPE,
                         universal_newlines=True)
    # Substitute in our custom config
    with open('Doxyfile', 'w') as fh:
        for line in p.stdout:
            if line.startswith('LAYOUT_FILE '):
                line = 'LAYOUT_FILE = "%s/layout.xml"\n' % DOXDIR
            elif line.startswith('PROJECT_NAME '):
                line = 'PROJECT_NAME = "%s"\n' % title
            elif line.startswith('INPUT '):
                line = 'INPUT = %s.md\n' % root
            elif line.startswith('SEARCHENGINE '):
                line = 'SEARCHENGINE = NO\n'
            elif line.startswith('TOC_INCLUDE_HEADINGS '):
                line = 'TOC_INCLUDE_HEADINGS = 2\n'
            elif line.startswith('IMAGE_PATH '):
                line = 'IMAGE_PATH = .\n'
            elif line.startswith('EXAMPLE_PATH '):
                line = 'EXAMPLE_PATH = ..\n'
            elif line.startswith('HTML_HEADER '):
                line = 'HTML_HEADER = "%s/header.html"\n' % DOXDIR
            elif line.startswith('HTML_FOOTER '):
                line = 'HTML_FOOTER = "%s/footer.html"\n' % DOXDIR
            elif line.startswith('GENERATE_LATEX '):
                line = 'GENERATE_LATEX = NO\n'
            elif line.startswith('AUTOLINK_SUPPORT '):
                # Don't make links from the text (only from code samples)
                line = 'AUTOLINK_SUPPORT = NO\n'
            elif line.startswith('TAGFILES '):
                line = 'TAGFILES = %s\n' % tagfiles
            fh.write(line)
    ret = p.wait()
    if ret != 0:
        raise OSError("doxygen failed")


def run_doxygen():
    subprocess.check_call(['doxygen', 'Doxyfile'])
    if not os.path.exists('html/images'):
        os.symlink('../.template/images', 'html/images')


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


def add_html_links(branch):
    license_link = get_license_link()
    repo = get_git_repo()
    pagemap = get_page_map()
    for html in glob.glob("html/*.html"):
        if html != 'html/pages.html':
            patch_html(html, repo, pagemap[html], branch, license_link)



def main():
    args = parse_args()
    branch = args.branch if args.branch else get_git_branch()

    # master branch of tutorials should work with IMP stable release
    # (and so should link to stable docs); other branches use nightly
    imp_version = IMP_STABLE_RELEASE if branch == 'master' else 'nightly'

    tags = get_tag_files(imp_version)

    generate_files(args.filename, tags)
    make_doxyfile(args.filename, tags)
    run_doxygen()
    add_html_links(branch)
    fix_menu_links(imp_version)


if __name__ == '__main__':
    main()