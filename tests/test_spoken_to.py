import pytest
import time
from core.schemas import UserProfile
from core.state import StateManager
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema
from brain.spoken_to import SpokenToReasoning, DiscourseRole, SpokenToDecision


@pytest.fixture
def spoken_engine(tmp_path):
    state_file = str(tmp_path / "test_spoken.db")
    state = StateManager(db_path=state_file)
    profile = state.get_user_profile()
    profile.preferred_name = "Dyvorn"
    state.save_user_profile(profile)

    registry = ToolRegistry()
    registry.register_tool("get_time", get_time, time_schema)

    return SpokenToReasoning(
        state_manager=state,
        registry=registry,
        assistant_name="Core"
    )


def test_direct_command_german(spoken_engine):
    """Verify vocative direct command in German strips wake word and signals response."""
    prof = UserProfile(preferred_name="Dyvorn")
    dec = spoken_engine.evaluate("Hey Core, wie spät ist es?", profile=prof)
    
    assert dec.discourse_role == DiscourseRole.ADDRESSED
    assert dec.should_respond is True
    assert dec.action_type == "command"
    assert dec.clean_command == "wie spät ist es?"


def test_direct_command_english(spoken_engine):
    """Verify vocative direct command in English strips wake word and signals response."""
    prof = UserProfile(preferred_name="Dyvorn")
    dec = spoken_engine.evaluate("Core, what time is it?", profile=prof)
    
    assert dec.discourse_role == DiscourseRole.ADDRESSED
    assert dec.should_respond is True
    assert dec.action_type == "command"
    assert dec.clean_command == "what time is it?"


def test_demonstration_showcase_german(spoken_engine):
    """Verify demonstration / showcase in German triggers dynamic chime-in with operator context."""
    prof = UserProfile(preferred_name="Dyvorn")
    dec = spoken_engine.evaluate("Ja, das ist Core AI, ich zeig dir mal was", profile=prof)
    
    assert dec.discourse_role == DiscourseRole.DEMONSTRATED
    assert dec.should_respond is True
    assert dec.action_type == "chime_in"
    assert dec.autonomous_response is not None
    assert "Dyvorn" in dec.autonomous_response
    assert "Demonstration" in dec.autonomous_response


def test_demonstration_showcase_english(spoken_engine):
    """Verify demonstration / showcase in English triggers dynamic chime-in."""
    prof = UserProfile(preferred_name="Dyvorn")
    dec = spoken_engine.evaluate("Look, this is Core AI, let me show you what it can do", profile=prof)
    
    assert dec.discourse_role == DiscourseRole.DEMONSTRATED
    assert dec.should_respond is True
    assert dec.action_type == "chime_in"
    assert dec.autonomous_response is not None
    assert "Dyvorn" in dec.autonomous_response


def test_third_person_passive_talk_german(spoken_engine):
    """Verify talking ABOUT Core AI in German past/descriptive mode stays silent."""
    prof = UserProfile(preferred_name="Dyvorn")
    dec = spoken_engine.evaluate("Ich habe Core AI gestern bis spät in die Nacht gebaut", profile=prof)
    
    assert dec.discourse_role == DiscourseRole.REFERENCED
    assert dec.should_respond is False
    assert dec.action_type == "silent"


def test_third_person_passive_talk_english(spoken_engine):
    """Verify talking ABOUT Core AI in English past/descriptive mode stays silent."""
    prof = UserProfile(preferred_name="Dyvorn")
    dec = spoken_engine.evaluate("I built Core AI last week with python", profile=prof)
    
    assert dec.discourse_role == DiscourseRole.REFERENCED
    assert dec.should_respond is False
    assert dec.action_type == "silent"


def test_ambient_side_talk_ignored(spoken_engine):
    """Verify ambient remarks and conversation between others are ignored."""
    prof = UserProfile(preferred_name="Dyvorn")
    dec1 = spoken_engine.evaluate("Kannst du mir mal das Wasser geben?", profile=prof)
    assert dec1.discourse_role == DiscourseRole.BYSTANDER
    assert dec1.should_respond is False
    assert dec1.action_type == "silent"

    dec2 = spoken_engine.evaluate("Where did I put my car keys?", profile=prof)
    assert dec2.discourse_role == DiscourseRole.BYSTANDER
    assert dec2.should_respond is False
    assert dec2.action_type == "silent"


def test_follow_up_conversational_window(spoken_engine):
    """Verify that follow-up questions within the active window do not require wake word."""
    prof = UserProfile(preferred_name="Dyvorn")
    # Simulate an interaction having just happened
    spoken_engine.record_interaction(DiscourseRole.ADDRESSED)

    # Follow-up question without "Hey Core"
    dec = spoken_engine.evaluate("Wie spät ist es?", profile=prof)
    assert dec.discourse_role == DiscourseRole.ADDRESSED
    assert dec.should_respond is True
    assert dec.action_type == "command"


def test_direct_greeting_conversational(spoken_engine):
    """Verify that standalone greetings like 'hi' or vocative calls like 'Hey Core' trigger conversational response."""
    prof = UserProfile(preferred_name="Dyvorn")
    
    # Pure greeting
    dec_hi = spoken_engine.evaluate("hi", profile=prof)
    assert dec_hi.discourse_role == DiscourseRole.ADDRESSED
    assert dec_hi.should_respond is True
    assert dec_hi.action_type == "chime_in"
    assert "Dyvorn" in dec_hi.autonomous_response

    # Vocative assistant call without trailing command
    dec_core = spoken_engine.evaluate("Hey Core", profile=prof)
    assert dec_core.discourse_role == DiscourseRole.ADDRESSED
    assert dec_core.should_respond is True
    assert dec_core.action_type == "chime_in"
    assert "Dyvorn" in dec_core.autonomous_response

