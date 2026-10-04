import os
import pytest
from core.state import StateManager
from core.schemas import UserProfile
from interfaces.cli.setup_wizard import (
    is_account_initialized,
    reset_account_to_day_zero,
    save_env_variable,
    ensure_env_template
)

def test_day_zero_account_detection(tmp_path):
    db_file = os.path.join(tmp_path, "clean_core.db")
    state = StateManager(db_path=db_file)

    # Initial Day-Zero state
    assert is_account_initialized(state) is False

    # Configure account and register dynamic zone
    profile = UserProfile(
        user_id="primary_user",
        preferred_name="Dyvorn",
        aliases=["Vyrn"],
        preferred_tone="tactical_direct",
        preferences={"primary_space": "sanctuary"}
    )
    state.save_user_profile(profile)
    state.ensure_zone_exists("sanctuary", display_name="Sanctuary")

    # Now it is initialized and has 1 zone
    assert is_account_initialized(state) is True
    assert len(state.list_zones()) == 1

    # Reset to Day-Zero blank slate with full wipe
    reset_account_to_day_zero(state, full_wipe=True)
    assert is_account_initialized(state) is False
    clean_profile = state.get_user_profile()
    assert clean_profile.preferred_name == "User"
    assert len(state.list_zones()) == 0

def test_ensure_env_template(tmp_path):
    example_file = os.path.join(tmp_path, ".env.example")
    env_file = os.path.join(tmp_path, ".env")
    with open(example_file, "w", encoding="utf-8") as f:
        f.write("CORE_HOST=0.0.0.0\nCORE_PORT=8000\n")

    assert not os.path.exists(env_file)
    ensure_env_template(env_path=env_file, example_path=example_file)
    assert os.path.exists(env_file)

    with open(env_file, "r", encoding="utf-8") as f:
        data = f.read()
    assert "CORE_HOST=0.0.0.0" in data

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
