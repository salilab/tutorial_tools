#!/usr/bin/env python3

import json
import base64
import sys
import io
import glob
import os
import re
import time
import argparse
import posixpath
import subprocess
import xml.etree.ElementTree as ET
from inventory import InventoryFile
import urllib.request


# Latest IMP stable release
IMP_STABLE_RELEASE = '2.17.0'

# Path to doxygen directory (containing doxygen inputs)
DOXDIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                      '..', 'doxygen'))

# Top of repository
def _get_topdir():
    parents = 0
    path = '.git'
    while not os.path.exists(path):
        path = os.path.join('..', path)
        parents += 1
        if parents > 20:
            raise ValueError("Could not determine top directory of repository")
    return path[:-4]
TOPDIR = os.path.abspath(_get_topdir())

# Template prefix
TEMPLATE = ".template."

# Cache directory
CACHE = ".cache"


def file_age(fname):
    """Return time in seconds since `fname` was last changed"""
    return time.time() - os.stat(fname).st_mtime


def get_cached_url(url, local):
    if not os.path.exists(CACHE):
        os.mkdir(CACHE)
    fname = os.path.join(CACHE, local)
    # Use file if it already exists and is less than a day old
    if not os.path.exists(fname) or file_age(fname) > 86400:
        # python.org doesn't allow retrieving objects.inv without a user-agent
        # string, so provide one
        r = urllib.request.Request(url, headers={'User-Agent': 'urllib'})
        response = urllib.request.urlopen(r)
        with open(fname, 'wb') as fh:
            fh.write(response.read())
    return fname


class RefLinks(object):
    """Handle doxygen-style @ref links in markdown"""
    include_re = re.compile(r'%%include\s+([^\s)]+)')
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
                base = c.find('base')
                if base is not None:
                    base = base.text
                url = urltop + c.find('filename').text
                self.refs[name] = url
                self._add_member_tags(c, name, base, urltop)
            elif c.tag == 'compound' and c.attrib.get('kind') == 'page':
                self._add_page_tags(c, urltop)
            elif c.tag == 'compound' and c.attrib.get('kind') == 'file':
                self._add_file_tags(c, urltop)

    def _add_file_tags(self, page, urltop):
        """Add doxygen tags for file objects"""
        namespace = None
        for child in page:
            if child.tag == 'namespace':
                namespace = child.text
            if (namespace and child.tag == 'member'
                and child.attrib.get('kind') == 'typedef'):
                name = child.find('name').text
                anchorfile = child.find('anchorfile').text
                url = urltop + anchorfile + '#' + child.find('anchor').text
                self.refs[namespace + '::' + name] = url
        name = page.find('name').text
        if name.endswith('.h'):
            fullname = 'IMP/' + name
            filename = page.find('filename').text
            self.refs[fullname] = urltop + filename + '.html'

    def _add_page_tags(self, page, urltop):
        """Add doxygen tags for page anchors"""
        name = page.find('name').text
        filename = page.find('filename').text
        self.refs[name] = urltop + filename + '.html'
        for child in page:
            if child.tag == 'docanchor':
                url = urltop + child.attrib['file'] + '.html#' + child.text
                self.refs[child.text] = url

    def _add_member_tags(self, cls, clsname, clsbase, urltop):
        """Add doxygen tags for class or namespace members"""
        # doxygen tag files sometimes include tags for the base class under
        # the <compound> tag for a derived class. Work around this by checking
        # to see if the file linked to matches the name of the base class.
        if clsbase:
            base_suffix = clsbase.replace('::', '_1_1') + '.html'
        for meth in cls:
            if (meth.tag == 'member' and meth.attrib.get('kind') == 'function'):
                methname = meth.find('name').text
                anchorfile = meth.find('anchorfile').text
                url = (urltop + anchorfile + '#' + meth.find('anchor').text)
                self.refs[clsname + '::' + methname] = url
                if clsbase and anchorfile.endswith(base_suffix):
                    self.refs[clsbase + '::' + methname] = url

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

    def _include_file(self, m):
        filename = m.group(1)
        with open(filename) as fh:
            return fh.read()

    def fix_links(self, c):
        """Modify and return `c` to replace any @ref links with URLs,
           and any %%include magics with file contents"""
        c = re.sub(self.include_re, self._include_file, c)
        c = re.sub(self.backtick_link, self._replace_backtick_link, c)
        return re.sub(self.ref_link, self._replace_ref_link, c)


def patch_source(source, rl):
    for c in source:
        if c.startswith('%gencelloutputs'):
            pass
        elif c.startswith('%intersphinx'):
            url = c.split()[1]
            objfile_url = posixpath.join(url, 'objects.inv')
            objfile = get_cached_url(url=objfile_url,
                local=objfile_url.replace(':', '').replace('/', ''))
            rl.parse_python_inventory_file(objfile, url)
        else:
            yield rl.fix_links(c)


_file_link_re = re.compile('@file\s+([^\s)]+)')
non_jupyter_constructs = re.compile('#?%%(html|nb|colab)(exclude|only)')
jupyter_anchor_re = re.compile('\s*\{#([^\s}]+)\}')
def patch_jupyter(source, rl, toc, is_markdown):
    if is_markdown:
        for c in source:
            if '[TOC]' in c:
                for md in toc.get_markdown():
                    yield md
            else:
                if not non_jupyter_constructs.match(c):
                    nc = re.sub(jupyter_anchor_re, '<a id="\\1"></a>', c)
                    nc = _file_link_re.sub('\\1.ipynb', nc)
                    yield nc
    else:
        for c in source:
            if not non_jupyter_constructs.match(c):
                yield c


_triple_backtick_re = re.compile('```(\S+)')
def write_cell(cell, fh):
    all_contents = []
    def tb_sub(m):
        # Jupyter markdown expects a language name, e.g. ```python
        # but Doxygen expects a file extension, e.g. ```py
        # so map one to the other
        lang = m.group(1)
        lang_replace = {'python': 'py', 'c++': 'cpp'}
        lang = lang_replace.get(lang, lang)
        return '```' + lang
    for s in cell['source']:
        # Colab-only code cells shouldn't end up in the .py output
        if s.startswith('#%%colabonly'):
            return []
        if (not re.match('#?%%(html|nb|colab)(exclude|only)', s)
            and not s.startswith('%matplotlib')):
            contents = _file_link_re.sub('\\1.html', s)
            contents = _triple_backtick_re.sub(tb_sub, contents)
            fh.write(contents)
            all_contents.append(contents)
    fh.write('\n')
    return all_contents


class CellOutputWriter(object):
    def __init__(self, topdir):
        self.imgdir = os.path.join(topdir, 'matplotlib')
        # Make sure img files have unique names
        self.counter = 0

    def write_image(self, contents):
        self.counter += 1
        if not os.path.exists(self.imgdir):
            os.makedirs(self.imgdir)
        img = "%d.png" % self.counter
        with open(os.path.join(self.imgdir, img), 'wb') as fh:
            fh.write(base64.b64decode(contents))
        return img

    def write(self, cell, fh):
        for out in cell['outputs']:
            if out['output_type'] == 'stream':
                fh.write('<div class="output">\n')
                fh.write('Output\n')
                fh.write('\\verbatim\n')
                fh.write("".join(out['text']))
                fh.write('\\endverbatim\n')
                fh.write('</div>\n')
            elif out['output_type'] == 'display_data':
                if 'image/png' in out['data']:
                    img = self.write_image(out['data']['image/png'])
                    fh.write('<div class="output">\n')
                    fh.write('<img src="matplotlib/%s" />\n' % img)
                    fh.write('</div>\n')


def get_cell_subset(cells, excludestr, onlytype):
    for cell in cells:
        if not cell['source'] or excludestr not in cell['source'][0]:
            m = re.search('%%(\S+)only', cell['source'][0])
            if not m or m.group(1) == onlytype:
                yield cell


def get_only_html_cells(cells):
    return get_cell_subset(cells, excludestr='%%htmlexclude',
                           onlytype='html')


def get_only_notebook_cells(cells):
    return get_cell_subset(cells, excludestr='%%nbexclude',
                           onlytype='nb')


def get_only_colab_cells(cells):
    return get_cell_subset(cells, excludestr='%%colabexclude',
                           onlytype='colab')


class ScriptWriter(object):
    def __init__(self, output):
        pass

    def get_filename(self, root):
        return root + '.' + self.file_ext

    def postprocess(self, script_filename):
        # make executable
        os.chmod(script_filename, 0o755)

    def write(self, root, cells):
        code_cells = [c for c in cells if c['cell_type'] == 'code']
        if not code_cells:
            return
        fname = self.get_filename(root)
        with open(fname, 'w') as fh:
            self.write_header(fh)
            first = True
            for cell in code_cells:
                if not first:
                    fh.write('\n')
                self.process_contents(write_cell(cell, fh), cell)
                first = False
        self.postprocess(fname)

    def process_contents(self, contents, cell):
        pass


class PlotWrapper(object):
    def __init__(self, orig_plot, writer):
        self.orig_plot = orig_plot
        self.writer = writer

    def __call__(self, *args, **keys):
        self.orig_plot(*args, **keys)
        self.writer.add_plot()


class PythonScriptWriter(ScriptWriter):
    file_ext = 'py'

    def __init__(self, output):
        self.output = output
        if output:
            import matplotlib
            matplotlib.use('agg')
            import matplotlib.pyplot as plt
            self.plt = plt
            p = PlotWrapper(plt.plot, self)
            plt.plot = p
            p = PlotWrapper(plt.show, self)
            plt.show = p
            self._context = {}

    def write_header(self, fh):
        fh.write("#!/usr/bin/env python3\n\n")

    def add_plot(self):
        self.plot = True

    def savefig(self):
        f = io.BytesIO()
        self.plt.savefig(f)
        return f.getvalue()

    def process_contents(self, contents, cell):
        if not self.output:
            return
        # Run cell and capture stdout
        self.plot = False
        o = sys.stdout
        sio = io.StringIO()
        try:
            sys.stdout = sio
            exec("".join(contents), self._context)
        finally:
            sys.stdout = o
        if self.plot:
            plot_contents = self.savefig()
            b64contents = base64.b64encode(plot_contents).decode('utf-8')
            cell['outputs'] = [
                    {'data': { "image/png": b64contents},
                     'metadata': {'needs_background': 'light'},
                     'output_type': 'display_data'}]
            self.plt.close('all')
        else:
            output = sio.getvalue().rstrip('\r\n').split("\n")
            if output and output != [""]:
                cell['outputs'] = [
                    {'name': 'stdout', 'output_type': 'stream',
                     'text': [line + "\n" for line in output]}]


class BashScriptWriter(ScriptWriter):
    file_ext = 'sh'

    def write_header(self, fh):
        fh.write("#!/bin/sh -e\n\n")


class TableOfContents(object):
    anchor_re = re.compile('(#+)\s+(.*?)\s*\{#([^\s}]+)\}')
    noanchor_re = re.compile('(#+)\s+(.*?)\s*$')

    def __init__(self, filenum):
        self._auto_toc = 0 # autogenerated anchors for titles without them
        self.filenum = filenum
        self.entries = [] # list of (level, title, anchor) tuples

    def add_missing_anchors(self, source):
        """Auto-generate anchors if they're missing"""
        for s in source:
            if not self.anchor_re.match(s):
                m = self.noanchor_re.match(s)
                if m:
                    self._auto_toc += 1
                    anchor = "autotoc%dv%d" % (self.filenum, self._auto_toc)
                    yield '%s %s {#%s}' % (m.group(1), m.group(2), anchor)
                else:
                    yield s
            else:
                yield s

    def parse_cell(self, source):
        # Don't include %%nbexclude cells in TOC
        if source and '%%nbexclude' in source[0]:
            return
        def get_sections(source):
            for s in source:
                m = self.anchor_re.match(s)
                if m:
                    yield len(m.group(1)), m.group(2), m.group(3)
        for level, title, anchor in get_sections(source):
            if self.entries and level > self.entries[-1][0] + 1:
                raise ValueError("A level-%d heading (%s) cannot follow a "
                    "level-%d heading (%s)"
                    % (level, title, self.entries[-1][0], self.entries[-1][1]))
            elif not self.entries and level != 1:
                raise ValueError(
                    "Top-level section (%s) is not a level one heading "
                    "(use '# title {#anchor}')" % title)
            self.entries.append((level, title, anchor))

    def get_markdown(self):
        yield "**Table of contents**\n"
        yield "\n"
        for level, title, anchor in self.entries:
            yield '%s- [%s](#%s)\n' % (' ' * level, title, anchor)


class FileGenerator(object):
    def __init__(self, tags):
        self.tags = tags
        self._file_counter = 0

    def generate_files(self, root, output_writer):
        self._file_counter += 1
        _generate_files(root, self.tags, self._file_counter, output_writer)


def _generate_files(root, tags, file_counter, output_writer):
    gen_output = False
    rl = RefLinks()
    for t in tags:
        rl.parse_doxygen_tag_file(t.xml_filename, t.doctop)

    toc = TableOfContents(file_counter)

    # Read in the template
    with open('%s%s.ipynb' % (TEMPLATE, root)) as fh:
        j = json.load(fh)

    # Make sure all outputs are empty
    for cell in j['cells']:
        if cell.get('outputs'):
            raise ValueError("Please clear all cell outputs first!")

    kernel = j['metadata']['kernelspec']
    language = kernel['language']

    # Handle our custom magics and @ref links
    for cell in j['cells']:
        if cell['cell_type'] == 'markdown':
            cell['source'] = list(toc.add_missing_anchors(cell['source']))
            toc.parse_cell(cell['source'])
            gen_output = gen_output or any(c.startswith('%gencelloutputs')
                                           for c in cell['source'])
            cell['source'] = list(patch_source(cell['source'], rl))

    # Write plain Python or Bash script
    # This also populates cell outputs if gen_output is set
    writer = {'python': PythonScriptWriter,
              'bash': BashScriptWriter}[language](gen_output)
    writer.write(root, j['cells'])

    # Write markdown suitable for processing with doxygen
    with open('%s.md' % root, 'w') as fh:
        for cell in get_only_html_cells(j['cells']):
            if cell['cell_type'] == 'markdown':
                write_cell(cell, fh)
                fh.write('\n')
            elif cell['cell_type'] == 'code':
                fh.write('\\code{.py}\n')
                write_cell(cell, fh)
                fh.write('\\endcode\n')
                if gen_output and cell['outputs']:
                    output_writer.write(cell, fh)

    def write_jupyter(fname, cells):
        # Remove or modify constructs that Jupyter doesn't understand
        # from the JSON
        j['cells'] = cells
        for cell in j['cells']:
            cell['source'] = list(
                patch_jupyter(cell['source'], rl, toc,
                              cell['cell_type'] == 'markdown'))

        # Write Jupyter notebook
        with open(fname, 'w') as fh:
            json.dump(j, fh, indent=2)

    nb_cells = list(get_only_notebook_cells(j['cells']))
    colab_cells = list(get_only_colab_cells(j['cells']))
    write_jupyter('%s.ipynb' % root, nb_cells)
    if colab_cells != nb_cells:
        write_jupyter('%s-colab.ipynb' % root, colab_cells)


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
    parser.add_argument("filename", nargs="+",
        help="Root name of the notebook template(s) (e.g. 'foo' to use "
             "%sfoo.ipynb)" % TEMPLATE)
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
                line = 'INPUT = %s\n' % " ".join("%s.md" % m for m in root)
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
    if not os.path.exists('html/images') and os.path.exists('images'):
        os.symlink('../images', 'html/images')


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
        if md == "README.md":
            continue
        pagename = get_pagename(md, page_name_md_re)
        if pagename == 'mainpage':
            pagename = 'index'
        m['html/%s.html' % pagename] = md
    return m


def get_license():
    fname = os.path.join(TOPDIR, 'LICENSE')
    if not os.path.exists(fname):
        return ''
    with open(fname, 'rb') as fh:
        return fh.read()


def get_license_link():
    license = get_license()
    if b'Attribution-ShareAlike 4.0 International' in license:
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
    # Path to Jupyter notebook relative to the top of the repo
    path = os.path.relpath(os.getcwd(), TOPDIR)
    edit_link = '  $(\'#main-menu\').append(\'<li style="float:right"><div id="github_edit"><a href="https://github.com/salilab/%s/blob/%s/%s/.template.%s.ipynb"><i class="fab fa-github"></i> Edit on GitHub</a></div></li>\');\n' % (repo, branch, path, source[:-3])

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

    # main branch of tutorials should work with IMP stable release
    # (and so should link to stable docs); other branches use nightly
    imp_version = IMP_STABLE_RELEASE if branch == 'main' else 'nightly'

    tags = get_tag_files(imp_version)

    cow = CellOutputWriter('html')
    g = FileGenerator(tags)
    for f in args.filename:
        g.generate_files(f, output_writer=cow)
    make_doxyfile(args.filename, tags)
    run_doxygen()
    add_html_links(branch)
    fix_menu_links(imp_version)


if __name__ == '__main__':
    main()
