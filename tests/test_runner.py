import os
import sys
import time
import unittest
import zipfile

from repodock.fetch import FetchError, extract
from repodock.runner import Job, Runner

from helpers import PY, TempDir, wait_for, write_files


def py(code: str) -> str:
    return f'"{PY}" -c "{code}"'


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.runner = Runner()

    def tearDown(self):
        self.runner.stop_all()
        self.tmp.cleanup()

    def test_runs_in_folder_and_captures_output(self):
        write_files(self.tmp.path, {"hello.txt": "hi"})
        job = self.runner.start("a", "run", py("print(open('hello.txt').read()); import sys; sys.exit(3)"), self.tmp.path)
        wait_for(lambda: not job.running)
        lines = [line for _, line in job.output()]
        self.assertIn("hi", lines)
        self.assertEqual(job.exit_code, 3)
        self.assertEqual(lines[-1], "Exited with code 3.")

    def test_terminal_window(self):
        # On Windows the program gets its own console window; elsewhere the flag is ignored.
        job = self.runner.start("t", "run", py("import time; open('started', 'w').write('1'); time.sleep(60)"), self.tmp.path, terminal=True)
        wait_for(lambda: (self.tmp.path / "started").exists(), 30)
        lines = [line for _, line in job.output()]
        self.assertEqual("Running in its own terminal window." in lines, sys.platform.startswith("win"))
        self.assertTrue(job.running)
        self.assertTrue(self.runner.stop("t"))
        wait_for(lambda: not job.running, 20)

    def test_stop_kills_the_whole_tree(self):
        # The shell starts Python, which starts another Python: Stop must end them all.
        child = (f"import subprocess; p = subprocess.Popen([r'{PY}', '-c', 'import time; time.sleep(60)']); "
                 f"open('pid', 'w').write(str(p.pid)); print('ready', flush=True); import time; time.sleep(60)")
        job = self.runner.start("b", "run", f'"{PY}" -c "{child}"', self.tmp.path)
        wait_for(lambda: any(line == "ready" for _, line in job.output()), 30)
        started = time.time()
        self.assertTrue(self.runner.stop("b"))
        wait_for(lambda: not job.running, 20)
        self.assertLess(time.time() - started, 15)
        self.assertEqual(job.output()[-1][1], "Stopped.")
        self.assertFalse(self.runner.stop("b"))
        if os.name == "posix":
            grandchild = int((self.tmp.path / "pid").read_text())

            def gone():
                try:
                    os.kill(grandchild, 0)
                except ProcessLookupError:
                    return True
                # A zombie waiting for its parent to reap it counts as gone.
                try:
                    with open(f"/proc/{grandchild}/stat") as fh:
                        return fh.read().split(")")[-1].split()[0] == "Z"
                except OSError:
                    return False

            wait_for(gone, 10)

    def test_one_job_per_key_and_history_carries_over(self):
        first = self.runner.start("c", "install", py("print('installing')"), self.tmp.path)
        with self.assertRaises(RuntimeError):
            self.runner.start("c", "run", py("print(1)"), self.tmp.path)
        wait_for(lambda: not first.running)
        second = self.runner.start("c", "run", py("print('running')"), self.tmp.path)
        wait_for(lambda: not second.running)
        text = [line for _, line in second.output()]
        self.assertLess(text.index("installing"), text.index("running"))
        seqs = [s for s, _ in second.output()]
        self.assertEqual(seqs, sorted(seqs))

    def test_task_reports_errors(self):
        def boom(log):
            log("working")
            raise ValueError("broken")

        done = []
        job = self.runner.task("d", "clone", "x", boom, done.append)
        wait_for(lambda: done)
        self.assertEqual(job.error, "broken")
        self.assertEqual(job.output()[-1][1], "Error: broken")

    def test_bad_command_does_not_crash(self):
        job = self.runner.start("e", "run", "this-command-does-not-exist-repodock", self.tmp.path)
        wait_for(lambda: not job.running)
        self.assertNotEqual(job.exit_code, 0)


class LogTests(unittest.TestCase):
    def test_ansi_and_progress_redraws(self):
        job = Job("k", "run", "x")
        job.log("\x1b[32mgreen\x1b[0m")
        job.log("Receiving 10%\rReceiving 50%\rReceiving 100%, done.")
        job.log("a\r\nb")
        self.assertEqual([line for _, line in job.output()], ["green", "Receiving 100%, done.", "a", "b"])


class ExtractTests(unittest.TestCase):
    def test_rejects_zip_slip(self):
        tmp = TempDir()
        try:
            archive = tmp.path / "evil.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("ok/file.txt", "fine")
                zf.writestr("../../escaped.txt", "bad")
            with self.assertRaises(FetchError):
                extract(archive, tmp.path / "out")
            self.assertFalse((tmp.path.parent / "escaped.txt").exists())
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
