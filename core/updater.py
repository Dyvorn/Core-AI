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

    def create_state_snapshot(self, backup_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Creates timestamped point-in-time snapshots of SQLite database and .env config.
        Retains maximum 5 newest snapshots to prevent storage bloat.
        """
        from datetime import datetime, timezone
        import shutil
        target_backup_dir = backup_dir or os.path.join(self.repo_dir, "backups")
        os.makedirs(target_backup_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        db_snapshot = None
        db_path = os.path.join(self.repo_dir, "core_ai.db")
        if os.path.exists(db_path):
            try:
                from core.state import StateManager
                sm = StateManager(db_path=db_path)
                db_snapshot = sm.create_backup(target_backup_dir)
            except Exception as e:
                logger.warning(f"Online DB snapshot failed ({e}). Falling back to file copy.")
                db_snapshot = os.path.join(target_backup_dir, f"state_backup_{timestamp}.db")
                shutil.copy2(db_path, db_snapshot)

        env_snapshot = None
        for env_cand in [os.path.join(self.repo_dir, "config", ".env"), os.path.join(self.repo_dir, ".env")]:
            if os.path.exists(env_cand):
                try:
                    env_snapshot = os.path.join(target_backup_dir, f"env_backup_{timestamp}.env")
                    shutil.copy2(env_cand, env_snapshot)
                    break
                except Exception as e:
                    logger.warning(f"Failed to copy env file: {e}")

        self._prune_old_snapshots(target_backup_dir, max_keep=5)
        return db_snapshot, env_snapshot

    def restore_state_snapshot(self, db_snapshot: Optional[str], env_snapshot: Optional[str] = None):
        """Restores database and env file from given snapshot paths."""
        import shutil
        if db_snapshot and os.path.exists(db_snapshot):
            try:
                dest = os.path.join(self.repo_dir, "core_ai.db")
                shutil.copy2(db_snapshot, dest)
                logger.info(f"Restored database from snapshot: {db_snapshot}")
            except Exception as e:
                logger.error(f"Failed to restore database snapshot: {e}")
        if env_snapshot and os.path.exists(env_snapshot):
            try:
                dest_env = os.path.join(self.repo_dir, "config", ".env") if os.path.exists(os.path.join(self.repo_dir, "config")) else os.path.join(self.repo_dir, ".env")
                shutil.copy2(env_snapshot, dest_env)
                logger.info(f"Restored .env from snapshot: {env_snapshot}")
            except Exception as e:
                logger.error(f"Failed to restore .env snapshot: {e}")

    def _prune_old_snapshots(self, backup_dir: str, max_keep: int = 5):
        """Keeps only the most recent N backup files in backup_dir."""
        try:
            files = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("state_backup_") or f.startswith("env_backup_")]
            db_files = sorted([f for f in files if "state_backup_" in f], key=os.path.getmtime, reverse=True)
            for old in db_files[max_keep:]:
                try:
                    os.remove(old)
                except Exception:
                    pass
            env_files = sorted([f for f in files if "env_backup_" in f], key=os.path.getmtime, reverse=True)
            for old in env_files[max_keep:]:
                try:
                    os.remove(old)
                except Exception:
                    pass
        except Exception:
            pass

    def apply_update(
        self,
        on_test_failure_prompt: Optional[Callable[[str], bool]] = None
    ) -> Tuple[bool, str]:
        """
        Pulls latest commits, executes test guard, and rolls back if tests fail.
        Automatically snapshots SQLite state and env configuration before pulling.
        Returns: (success, message)
        """
        has_updates, cur_commit, remote_commit = self.check_for_updates()
        if not has_updates:
            return True, f"System is up-to-date at commit {cur_commit}."

        logger.info(f"Applying update: {cur_commit} -> {remote_commit}...")
        previous_commit = cur_commit

        # Pre-update state snapshot
        db_snap, env_snap = self.create_state_snapshot()
        logger.info(f"Pre-update state snapshot created (db={db_snap}, env={env_snap})")

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
            if db_snap:
                self.restore_state_snapshot(db_snap, env_snap)
            return False, f"Update rolled back to {previous_commit} because test guard detected test failures. State snapshot restored."

        return True, "Update retained per operator override despite test failures."
