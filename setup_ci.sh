#!/bin/bash -e

# Set up an environment to run tests under Travis CI (see toplevel .travis.yml)
# or GitHub Actions (see toplevel .github/workflows/build.yml)

if [ $# -ne 1 ]; then
  echo "Usage: $0 imp_branch"
  exit 1
fi

imp_branch=$1

if [ ${imp_branch} = "develop" ]; then
  IMP_CONDA="imp-nightly"
else
  IMP_CONDA="imp"
fi

eval "$(conda shell.bash hook)"
conda activate test
conda install --yes -q scipy matplotlib pip ${IMP_CONDA}

# Don't try to run with MPI even if mpich is available
echo "import pathlib, IMP.mpi; m=pathlib.Path(IMP.mpi.__file__).parent; m.rename(m.with_stem('mpi.bak'))" | python3

pip install pytest-cov coverage pytest-flake8 'pytest<9'
