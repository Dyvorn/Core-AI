import os
import sys
import subprocess
import logging
from typing import Tuple, Optional, Callable

logger = logging.getLogger(__name__)

class CoreUpdater:
    """
    Automated Self-Updater with Test-Guard Protection:
    - Checks GitHub / git remote for new commits.
    - If updates exist, pulls the new code and immediately executes automated test suite (pytest).
    - If all tests pass: finalizes the update.
    - If tests fail: warns operator, prompts, or automatically rolls back to keep system stable.
    """

    def __init__(self, repo_dir: Optional[str] = None):
        self.repo_dir = repo_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def _run_git(self, args: list) -> Tuple[int, str, str]:
        """Runs a git command in the repository directory."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=30.0
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except Exception as e:
            return 1, "", str(e)

    def is_git_repository(self) -> bool:
        code, _, _ = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return code == 0

    def get_current_commit(self) -> Optional[str]:
        code, out, _ = self._run_git(["rev-parse", "--short", "HEAD"])
        return out if code == 0 else None

    def check_for_updates(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Fetches remote and checks if there are newer commits on origin/master.
        Returns: (has_updates, current_commit, remote_commit)
        """
        if not self.is_git_repository():
            logger.debug("Not running in a git repository; skipping update check.")
            return False, None, None

        current = self.get_current_commit()
        # Fetch remote silently
        self._run_git(["fetch", "origin", "master"])

        code, remote_hash, _ = self._run_git(["rev-parse", "--short", "origin/master"])
        if code != 0 or not remote_hash:
            return False, current, None

        has_updates = current != remote_hash
        return has_updates, current, remote_hash

    def run_tests(self) -> Tuple[bool, str]:
        """Runs pytest on the test suite to verify stability."""
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pytest", "tests"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=90.0
            )
            passed = res.returncode == 0
            return passed, res.stdout
        except Exception as e:
            return False, str(e)

    def apply_update(
        self,
        on_test_failure_prompt: Optional[Callable[[str], bool]] = None
    ) -> Tuple[bool, str]:
        """
        Pulls latest commits, executes test guard, and rolls back if tests fail.
        Returns: (success, message)
        """
        has_updates, cur_commit, remote_commit = self.check_for_updates()
        if not has_updates:
            return True, f"System is up-to-date at commit {cur_commit}."

        logger.info(f"Applying update: {cur_commit} -> {remote_commit}...")
        previous_commit = cur_commit

        # Pull from origin master
        code, pull_out, pull_err = self._run_git(["pull", "origin", "master"])
        if code != 0:
            return False, f"Git pull failed: {pull_err}"

        # Run automated test guard
        logger.info("Running automated test guard on updated files...")
        passed, test_out = self.run_tests()

        if passed:
            new_commit = self.get_current_commit()
            msg = f"Upgrade successful! Updated to commit {new_commit}. All tests passed 100% green."
            logger.info(msg)
            return True, msg

        # Tests failed on new update!
        logger.warning("Test guard failed after applying update!")
        keep_anyway = False
        if on_test_failure_prompt:
            keep_anyway = on_test_failure_prompt(test_out)

        if not keep_anyway and previous_commit:
            logger.warning(f"Rolling back to previous commit {previous_commit} for safety...")
            self._run_git(["reset", "--hard", previous_commit])
            return False, f"Update rolled back to {previous_commit} because test guard detected test failures."

        return True, "Update retained per operator override despite test failures."
