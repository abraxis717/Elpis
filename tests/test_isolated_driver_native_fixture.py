from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import sysconfig

import pytest

from elpis_fractal_spine.isolated_driver import IsolatedProvider, SupervisorPolicy
from test_isolated_driver_authority import PACKAGE, PROVIDER, make_wheel, wheel_files
from test_isolated_driver_supervisor import assert_clean, request

C_SOURCE = r'''
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pthread.h>
static long counter = 0;
static PyObject *next_value(PyObject *self, PyObject *args) {
    (void)self; (void)args;
    return PyLong_FromLong(++counter);
}
static void *compute(void *arg) {
    long *value = (long *)arg;
    for (long i = 0; i < 50000; ++i) *value += 1;
    return NULL;
}
static PyObject *threads(PyObject *self, PyObject *args) {
    (void)self; (void)args;
    pthread_t workers[4];
    long values[4] = {0, 0, 0, 0};
    int created = 0;
    Py_BEGIN_ALLOW_THREADS
    for (int i = 0; i < 4; ++i) {
        if (pthread_create(&workers[i], NULL, compute, &values[i]) != 0) break;
        ++created;
    }
    for (int i = 0; i < created; ++i) pthread_join(workers[i], NULL);
    Py_END_ALLOW_THREADS
    if (created != 4) return PyErr_Format(PyExc_RuntimeError, "pthread_create denied");
    return PyLong_FromLong(values[0] + values[1] + values[2] + values[3]);
}
static PyMethodDef methods[] = {
    {"next_value", next_value, METH_NOARGS, "Increment process-global C state."},
    {"threads", threads, METH_NOARGS, "Real native computation threads."},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef definition = {PyModuleDef_HEAD_INIT, "_state", NULL, -1, methods};
PyMODINIT_FUNC PyInit__state(void) { return PyModule_Create(&definition); }
'''


def test_two_workers_native_process_globals_and_pthreads(tmp_path):
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("environment blocker: C compiler unavailable")
    source = tmp_path / "native_fixture.c"
    extension = tmp_path / ("_state" + sysconfig.get_config_var("EXT_SUFFIX"))
    source.write_text(C_SOURCE)
    result = subprocess.run([compiler, "-shared", "-fPIC", "-O2", "-pthread",
                             "-I" + sysconfig.get_path("include"), str(source), "-o", str(extension)],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    plugin = PROVIDER.replace("counter += 1", "counter = _state.next_value()")
    plugin += "\nfrom . import _state\nassert _state.threads() == 200000\n"
    path, authority = make_wheel(tmp_path, files=wheel_files(plugin, extras={PACKAGE + "/" + extension.name: extension.read_bytes()}))
    assert not any(name.startswith(PACKAGE) for name in sys.modules)
    a = IsolatedProvider(authority=authority, wheel_path=path, runtime_context={}, policy=SupervisorPolicy(tmp_path))
    b = IsolatedProvider(authority=authority, wheel_path=path, runtime_context={}, policy=SupervisorPolicy(tmp_path))
    try:
        a.start()
        b.start()
        assert a.receipt.child_pid != b.receipt.child_pid
        assert a.receipt.sandbox.seccomp and b.receipt.sandbox.seccomp
        assert a.execute(request()).output_payload == (1,)
        assert a.execute(request()).output_payload == (2,)
        assert b.execute(request()).output_payload == (1,)
        assert a.execute(request()).output_payload == (3,)
        a.close()
        assert_clean(a)
        assert b.execute(request()).output_payload == (2,)
    finally:
        a.close()
        b.close()
    assert_clean(b)
    assert not any(name.startswith(PACKAGE) for name in sys.modules)
