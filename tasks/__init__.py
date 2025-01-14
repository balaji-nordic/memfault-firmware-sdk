#
# Copyright (c) Memfault, Inc.
# See License.txt for details
#

import os
import pathlib

from invoke import Collection, task

from . import esp32, mbed, nrf, nrfconnect, wiced, zephyr
from .macos_ftdi import is_macos

SDK_FW_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK_FW_TASKS_DIR = pathlib.Path(os.path.join(SDK_FW_ROOT, "tasks"))
SDK_FW_TESTS_ROOT = os.path.join(SDK_FW_ROOT, "tests")


@task
def fw_sdk_unit_test(
    ctx,
    coverage=False,
    rule="",
    test_filter=None,
    test_dir=SDK_FW_TESTS_ROOT,
    extra_make_options="",
):
    """Runs unit tests"""
    env_dict = {}
    if is_macos():
        # Search to see if CPPUTEST_HOME is already on the path (i.e in a conda environment)
        # Otherwise, fallback to the default install location used with brew
        env_dict["CPPUTEST_HOME"] = os.environ.get(
            "CPPUTEST_HOME", "/usr/local/Cellar/cpputest/4.0"
        )

    if "CPPUTEST_HOME" in os.environ:
        # override target platform so the test build system can locate the
        # conda-installed cpputest libraries.
        env_dict["TARGET_PLATFORM"] = "lib"

    if coverage:
        rule += " lcov"

    if test_filter:
        env_dict["TEST_MAKEFILE_FILTER"] = test_filter

    make_options = []

    # set output-sync option only if make supports it. macos uses a 12+ year old
    # copy of make by default that doesn't have this option.
    result = ctx.run("make --help", hide=True)
    if "--output-sync" in result.stdout:
        make_options.append("--output-sync=recurse")

    if extra_make_options:
        make_options.append(extra_make_options)

    cpus = 1
    if os.getenv("CIRCLECI"):
        # getting the number of cpus available to the circleci executor from
        # within the docker container is a hassle, so bail and use 2 cpus
        cpus = 2
    else:
        cpus = len(os.sched_getaffinity(0))
    make_options.extend(["-j", str(cpus)])

    env_dict["CPPUTEST_EXE_FLAGS"] = "-c"

    with ctx.cd(test_dir):
        ctx.run(
            "make {} {}".format(" ".join(make_options), rule),
            env=env_dict,
            pty=True,
        )


ns = Collection()
ns.add_task(fw_sdk_unit_test, name="test")
ns.add_collection(mbed)
ns.add_collection(nrf)
ns.add_collection(wiced)
ns.add_collection(esp32)
if os.environ.get("STM32_ENABLED"):
    from . import stm32

    ns.add_collection(stm32)

# Internal tasks are only included if they exist in the SDK
if (SDK_FW_TASKS_DIR / "internal.py").exists():
    from . import internal

    ns.add_collection(internal)


@task(
    pre=[
        mbed.mbed_clean,
        mbed.mbed_build,
        nrf.nrf_clean,
        nrf.nrf_build,
        wiced.wiced_clean,
        wiced.wiced_build,
        esp32.esp32_app_clean,
        esp32.esp32_app_build,
    ]
)
def build_all_demos(ctx):
    """Builds all demo apps (for CI purposes)"""
    pass


ci = Collection("~ci")
ci.add_task(build_all_demos, name="build-all-demos")
ci.add_task(zephyr.zephyr_project_ci_setup)
ci.add_task(nrfconnect.nrfconnect_project_ci_setup)
ns.add_collection(ci)
