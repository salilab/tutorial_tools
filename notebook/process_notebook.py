import json
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

# Absolute path to the top of the repository
TOPDIR = os.path.abspath('..')

# Path to this directory (containing doxygen inputs)
DOXDIR = os.path.abspath(os.path.dirname(__file__))

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


def write_cell(cell, fh):
    for s in cell['source']:
        fh.write(s)
    fh.write('\n')


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

    # Write Jupyter notebook with full links and our custom magics removed
    with open('%s.ipynb' % root, 'w') as fh:
        json.dump(j, fh, indent=2)

    # Write plain Python script
    with open('%s.py' % root, 'w') as fh:
        for cell in j['cells']:
            if cell['cell_type'] == 'code':
                write_cell(cell, fh)

    # Write markdown suitable for processing with doxygen
    with open('%s.md' % root, 'w') as fh:
        for cell in j['cells']:
            if cell['cell_type'] == 'markdown':
                write_cell(cell, fh)
            elif cell['cell_type'] == 'code':
                fh.write('\\code{.py}\n')
                write_cell(cell, fh)
                fh.write('\\endcode\n')

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


def main():
    args = parse_args()
    branch = args.branch if args.branch else get_git_branch()

    # master branch of tutorials should work with IMP stable release
    # (and so should link to stable docs); other branches use nightly
    imp_version = IMP_STABLE_RELEASE if branch == 'master' else 'nightly'

    tags = get_tag_files(imp_version)

    generate_files(args.filename, tags)


if __name__ == '__main__':
    main()
