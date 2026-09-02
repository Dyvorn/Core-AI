import pytest
from core.schemas import TextEvent

# Mock tests as Redis requires a running server
def test_schema_creation():
    event = TextEvent(source_node="mic_1", room_id="room_1", text="hello")
    assert event.text == "hello"
    assert event.room_id == "room_1"
    assert event.id is not None
