This repository contains basic tools that are useful for every IMP
tutorial. It is intended to be included in each IMP tutorial repository
as a submodule.

To set up in a new tutorial, run in the top level tutorial directory:

    mkdir support
    (cd support && git submodule add https://github.com/salilab/tutorial_tools)
    ln -sf support/tutorial_tools/travis-template.yml .travis.yml

Then make a `support/test` directory and put one or more Python test scripts
there. These should run the tutorial scripts (perhaps with a `--test` flag
to run faster) and check that everything worked correctly. Each file should
be executable (with a `#!/usr/bin/env python`) first line), and use the
Python `unittest` module. The `.travis.yml` config file will ensure these tests
get run every time you change the tutorial using both Python 2 and Python 3,
and for both the current IMP nightly build and the latest stable release.
