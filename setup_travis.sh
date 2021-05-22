#!/bin/bash -e

# Set up an environment to run tests under Travis CI (see toplevel .travis.yml)
# or GitHub Actions (see toplevel .github/workflows/build.yml)

if [ $# -ne 2 ]; then
  echo "Usage: $0 imp_branch python_version"
  exit 1
fi

imp_branch=$1
python_version=$2
temp_dir=$(mktemp -d)

if [ ${imp_branch} = "develop" ]; then
  IMP_CONDA="imp-nightly"
else
  IMP_CONDA="imp"
fi

cd ${temp_dir}

conda update --yes -q conda
conda create --yes -q -n python${python_version} -c salilab python=${python_version} scipy matplotlib nose ${IMP_CONDA}

rm -rf ${temp_dir}
