import tempfile
import contextlib
import shutil
import os
import sys

@contextlib.contextmanager
def temporary_directory(dir=None):
    """Make a temporary directory"""
    tempd = tempfile.mkdtemp(dir=dir)
    yield tempd
    shutil.rmtree(tempd)

if 'coverage' in sys.modules:
    import atexit
    # Collect coverage information from subprocesses
    __site_tmpdir = tempfile.mkdtemp()
    with open(os.path.join(__site_tmpdir, 'sitecustomize.py'), 'w') as fh:
        fh.write("""
import coverage
import atexit

_cov = coverage.coverage(branch=True, data_suffix=True, auto_data=True,
                         data_file='%s/.coverage')
_cov.start()

def _coverage_cleanup(c):
    c.stop()
atexit.register(_coverage_cleanup, _cov)
""" % os.getcwd())

    os.environ['PYTHONPATH'] = __site_tmpdir

    def __cleanup(d):
        shutil.rmtree(d, ignore_errors=True)
    atexit.register(__cleanup, __site_tmpdir)
