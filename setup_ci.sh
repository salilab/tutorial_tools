#!/bin/bash -e

# Set up an environment to run tests under Travis CI (see toplevel .travis.yml)
# or GitHub Actions (see toplevel .github/workflows/build.yml)

if [ $# -ne 2 ]; then
  echo "Usage: $0 imp_branch python_version"
  exit 1
fi

imp_branch=$1
python_version=$2

# get conda-forge, not main, packages
conda config --remove channels defaults
conda config --add channels conda-forge
if [ ${imp_branch} = "develop" ]; then
  IMP_CONDA="imp-nightly"
else
  IMP_CONDA="imp"
fi

conda create --yes -q -n python${python_version} -c salilab python=${python_version} scipy matplotlib ${IMP_CONDA}
eval "$(conda shell.bash hook)"
conda activate python${python_version}

if [ ${python_version} = "2.7" ]; then
  # pytest-flake8 1.1.0 tries to import contextlib.redirect_stdout, which
  # isn't present in Python 2
  pip install pytest-cov coverage 'pytest-flake8<1.1'
else
  pip install pytest-cov coverage pytest-flake8
fi
