import os
import pytest
from core.state import StateManager
from core.schemas import UserProfile
from interfaces.cli.setup_wizard import (
    is_account_initialized,
    reset_account_to_day_zero,
    save_env_variable
)

def test_day_zero_account_detection(tmp_path):
    db_file = os.path.join(tmp_path, "clean_core.db")
    state = StateManager(db_path=db_file)

    # Initial Day-Zero state
    assert is_account_initialized(state) is False

    # Configure account
    profile = UserProfile(
        user_id="primary_user",
        preferred_name="Dyvorn",
        aliases=["Vyrn"],
        preferred_tone="tactical_direct",
        preferences={"primary_space": "sanctuary"}
    )
    state.save_user_profile(profile)

    # Now it is initialized
    assert is_account_initialized(state) is True

    # Reset to Day-Zero blank slate
    reset_account_to_day_zero(state)
    assert is_account_initialized(state) is False
    clean_profile = state.get_user_profile()
    assert clean_profile.preferred_name == "User"

def test_save_env_variable(tmp_path):
    env_file = os.path.join(tmp_path, "test.env")
    save_env_variable("CORE_AUTH_SECRET", "super_secret_hex_12345", env_path=env_file)

    with open(env_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CORE_AUTH_SECRET=super_secret_hex_12345" in content

    # Update variable in same file
    save_env_variable("CORE_AUTH_SECRET", "updated_secret_99999", env_path=env_file)
    with open(env_file, "r", encoding="utf-8") as f:
        updated_content = f.read()

    assert "CORE_AUTH_SECRET=updated_secret_99999" in updated_content
    assert "super_secret_hex_12345" not in updated_content
