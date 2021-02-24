[![Build Status](https://github.com/salilab/tutorial_tools/workflows/build/badge.svg?branch=main)](https://github.com/salilab/tutorial_tools/actions?query=workflow%3Abuild)
[![codecov](https://codecov.io/gh/salilab/tutorial_tools/branch/main/graph/badge.svg)](https://codecov.io/gh/salilab/tutorial_tools)

This repository contains basic tools that are useful for every IMP
tutorial. It is intended to be included in each IMP tutorial repository
as a submodule.

## Setup of a new tutorial

Make a GitHub repository for your tutorial. Then run in the top level
tutorial directory:

    mkdir support
    (cd support && git submodule add https://github.com/salilab/tutorial_tools)

Make a `metadata.yaml` file in the `support` directory to describe the
tutorial, with contents similar to:

    title: My tutorial
    description: >
        Longer description of the tutorial, which
        can span multiple lines.
    depends: [foo, bar]
    show_in_index: false

This metadata is used on the
[IMP tutorial index](https://integrativemodeling.org/tutorials/).

 - `title` provides a short name for the tutorial.
 - `description` gives a longer text.
 - `depends`, if given, lists other tutorials that are recommended for the user
   before this one. GitHub repo names can be used here
   (e.g. `imp_coding_tutorial`) although the `imp_` prefix or `_tutorial`
   suffix are optional (e.g. `coding` would be equivalent). This controls
   the ordering of the tutorial list on the website.
 - `show_in_index: false` prevents the tutorial from showing up in the
   index. Remove this line once the tutorial is ready for public consumption.

Choose a suitable license for the tutorial and put it in a file `LICENSE`.
We recommend the
[CC BY-SA license](https://creativecommons.org/licenses/by-sa/4.0/). One way
to do this is to simply copy
[this LICENSE file](https://github.com/salilab/imp_coding_tutorial/blob/main/LICENSE).

Make a simple `README.md` file. Generally a brief description of the tutorial
and a link to the website (see below) is sufficient content.

## Branches

  - The `main` branch of your tutorial should work with both the latest stable
    IMP release *and* the nightly build.
  - The `develop` branch of your tutorial (if present) only needs to work with
    the IMP nightly build - this is for developing new tutorials.
  - Other branches (if present) are treated like `develop`.

## Testing

Make a `support/test` directory and put one or more Python test scripts
there. These should run the tutorial scripts and check that everything
worked correctly. Note that there is a 20 minute time limit for tests, so
you may need to run shorter simulations (perhaps with a `--test` flag).
Each file should
be executable (with a `#!/usr/bin/env python` first line), and use the
Python `unittest` module.

Then copy a [GitHub Actions](https://github.com/features/actions)
configuration file to the `.github/workflows/` subdirectory under the top level
directory of your tutorial. For the `main` branch of your tutorial, use
`cp support/tutorial_tools/github-main.yml .github/workflows/build.yml`.
For other branches such as `develop`, use `github-develop.yml` instead.

The `build.yml` config file will ensure the tutorial tests
get run every time the tutorial is changed (pushed to GitHub) using both
Python 2 and Python 3, and for the current IMP nightly build and also the
latest stable release (if applicable).

## Tutorial text

The actual text of the tutorial should be written using one or more
files in the `doc` directory. Each should have a `.md` file extension, and
use [doxygen markdown](http://www.doxygen.nl/manual/markdown.html).
Give each file a label, using `mainpage` for the main page, as described
in the [doxygen docs](http://www.doxygen.nl/manual/markdown.html#markdown_dox).

See the existing [IMP coding](https://github.com/salilab/imp_coding_tutorial/tree/main/doc)
or [PMI2](https://github.com/salilab/imp_tutorial/tree/pmi2/doc)
tutorials for examples.

Any references to IMP classes in the text will be automatically linked by
doxygen to the IMP manual (the `main` branch of the tutorial to the most
recent IMP release, and other branches to the IMP nightly build). To add
explicit links to IMP objects or to sections in the IMP manual, use
the `@ref` notation as described in the
[doxygen manual](http://www.doxygen.nl/manual/markdown.html#md_header_id).
(To prevent a word from being automatically linked, prefix it with the
% character. This is often used for "IMP" which otherwise is linked to
the documentation for the IMP (kernel) namespace.)

To include images in the tutorial, put them in an `images` subdirectory and use
the [\image command](http://www.doxygen.nl/manual/commands.html#cmdimage).

To put example code (e.g. C++, Python, or shell) directly in the text, use the
[\code and \endcode commands](http://www.doxygen.nl/manual/commands.html#cmdcode).
To include all or part of a file in the repository, use the
[\include](http://www.doxygen.nl/manual/commands.html#cmdinclude) or
[\snippet](http://www.doxygen.nl/manual/commands.html#cmdsnippet) commands,
respectively. In all cases the code will be syntax highlighted and any
IMP classes or functions will be automatically linked to the IMP manual.
(For `\include` or `\snippet` use the full path to the file, relative to
the top of the repository.)

To format the text, run `../support/tutorial_tools/doxygen/make-docs.py` (it
requires network access and that you have `doxygen` installed) then open
`html/index.html` in a web browser.

The formatted tutorial text for the `main` branch will also be deployed
automatically to `https://integrativemodeling.org/tutorials/<name>` on each
push to GitHub. (`<name>` is the name of the tutorial GitHub repository,
with any `imp_` prefix or `_tutorial` suffix removed). Non-`main` branches
of the tutorial will be found under a subdirectory named for the branch, e.g.
`https://integrativemodeling.org/tutorials/<name>/develop/`.

## Generation from Jupyter Notebook templates (experimental)

Tutorials can also be generated using a slightly-modified Jupyter Notebook
as the input. (This is still in development.)

Given a template notebook, `.template.foo.ipynb`, running the script
`notebook/process_notebook.py foo` will generate:
 - `foo.ipynb`, a standard Jupyter notebook, suitable for general use
 - `foo.py` or `foo.sh`, a simple Python or shell script that can be run
   standalone (to generate a Bash script, install and use a Jupyter Bash kernel
   such as [Calysto Bash](https://github.com/Calysto/calysto_bash))
 - `foo.md`, markdown which is further processed using doxygen to generate HTML
   files in the `html` subdirectory

The template notebook allows for additional functionality not present in
regular Jupyter notebooks:
 - doxygen-style links of the form `[foo](@ref bar)` can be used. `@ref bar`
   will be replaced with the full URL for the identifier `bar`. `bar` can
   be any IMP class, method or module name (e.g. IMP.atom.Selection, IMP::pmi),
   an IMP header (e.g. IMP/Restraint.h, IMP/core/Harmonic.h),
   or any identifier read with `%intersphinx` (see below).
 - The \`\`foo\`\` syntax is shorthand for `[foo](@ref foo)`.
 - The \`\`~x.y.z.foo\`\` syntax is shorthand for `[foo](@ref x.y.z.foo)`. 
 - A line of the form `%intersphinx url` acts like the Sphinx intersphinx
   extension. It fetches a Python inventory file from `url` so that `@ref`
   can also be used to refer to Python objects from that URL. For example,
   after using `%intersphinx https://docs.python.org/3` links can be made
   to Python standard library objects, e.g. `@ref itertools`.
 - The special command `%%include foo` will be replaced with the contents of
   the file `foo`.
 - The special command `[TOC]` will generate a table of contents.
 - Custom anchors can be added to headings, of the form
   `# Heading {#anchor}`.
 - A cell starting with `%%nbexclude` will be excluded from the notebook output
   (`#%%nbexclude` can also be used, which prevents Jupyter from complaining
   about a magic it doesn't understand in a code cell).
 - A cell starting with `%%htmlexclude` (or `#%%htmlexclude`) will be
   excluded from the HTML output.

The notebook should start with a title and `#mainpage` anchor of the form

    My title {#mainpage}
    ========

To include images, put them in an `images` subdirectory. 
It's recommended to use HTML syntax rather than Markdown so that the size and
caption can be precisely controlled in the HTML output, e.g.:

    <img src="images/links.png" width="700px" title="Nup84 file linkage" />

All cell outputs in the template notebook should be cleared. If you want to
include pregenerated outputs in the notebook and HTML output, use the
`%gencelloutputs` magic in any markdown cell in your template notebook. This
will run all of the cells in order and add stdout or matplotlib plots. See the
[cross-linking tutorial](https://github.com/salilab/cross_linking_tutorial)
for an example.

Otherwise, normal Jupyter notebook syntax can be used.

A tutorial can consist of multiple notebooks (see the
[FoXS tutorial](https://github.com/salilab/foxs_tutorial/) for an example).
In this case

 - All the notebooks should be in the same directory.
 - Each notebook should start with a title (as above). Exactly one notebook
   should use the `#mainpage` anchor; every other notebook should use
   a different anchor (usually the name of the file).
 - Anchors should be unique across all notebooks.
 - To link to the notebook `foo`, use the link syntax `[link text](@file foo)`.
 - Outputs are generated using the `process_notebook.py` script as above;
   simply list all notebooks on the command line. For example, given notebooks
   `.template.foo.ipynb` and `.template.bar.ipynb`, running
   the script `process_notebook.py foo bar` will generate all outputs.
