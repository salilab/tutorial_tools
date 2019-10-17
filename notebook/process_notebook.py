import json
import re
import argparse
import posixpath
import xml.etree.ElementTree as ET
from inventory import InventoryFile


# Latest IMP stable release
IMP_STABLE_RELEASE = '2.11.1'


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
            # get objects from url/objects.inv
            rl.parse_python_inventory_file('objects.inv', url)
        else:
            yield rl.fix_links(c)


def write_cell(cell, fh):
    for s in cell['source']:
        fh.write(s)
    fh.write('\n')


def generate_files(root):
    rl = RefLinks()
    rl.parse_doxygen_tag_file(
        '.template/ref-tags.xml',
        'https://integrativemodeling.org/%s/doc/ref/' % IMP_STABLE_RELEASE)
    rl.parse_doxygen_tag_file(
        '.template/manual-tags.xml',
        'https://integrativemodeling.org/%s/doc/manual/' % IMP_STABLE_RELEASE)

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



if __name__ == '__main__':
    main()
