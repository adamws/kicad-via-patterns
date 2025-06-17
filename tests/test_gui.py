import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def run_process(args, package_path):
    env = os.environ.copy()
    return subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        cwd=package_path,
        env=env,
    )


def run_gui_test(tmpdir, screen_manager, window_name, gui_callback) -> None:
    with screen_manager as mgr:
        p = gui_callback()

        is_ok = mgr.screenshot(window_name, f"{tmpdir}/report/screenshot.png")
        try:
            outs, errs = p.communicate("q\n", timeout=1)
        except subprocess.TimeoutExpired:
            logger.error("Process timeout expired")
            p.kill()
            outs, errs = p.communicate()

        logger.info(f"Process stdout: {outs}")
        logger.info(f"Process stderr: {errs}")

        assert outs.endswith("exit ok\n")
        assert errs == ""
        assert is_ok


def test_main_dialog(tmpdir, package_path, package_name, screen_manager) -> None:
    def _callback():
        return run_process(
            ["python3", "-m", f"{package_name}.dialog", "main"],
            package_path,
        )

    run_gui_test(tmpdir, screen_manager, "Via Patterns", _callback)


def test_rotation_dialog(tmpdir, package_path, package_name, screen_manager) -> None:
    def _callback():
        return run_process(
            ["python3", "-m", f"{package_name}.dialog", "rotate"], package_path
        )

    run_gui_test(tmpdir, screen_manager, "Adjust rotation", _callback)
