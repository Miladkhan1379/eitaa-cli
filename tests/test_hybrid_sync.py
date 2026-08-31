from __future__ import annotations

from eitaa_cli.hybrid_sync import UpdateState, _messages_from_difference, _state_from_difference


def test_difference_extracts_new_and_edited_messages() -> None:
    result = {
        "_": "updates.difference",
        "new_messages": [
            {"_": "message", "id": 10, "peer_id": {"_": "peerChannel", "channel_id": 7}, "date": 100}
        ],
        "other_updates": [
            {
                "_": "updateEditChannelMessage",
                "message": {"_": "message", "id": 9, "peer_id": {"_": "peerChannel", "channel_id": 7}, "date": 90},
            }
        ],
    }
    found = _messages_from_difference(result)
    assert {(event, int(message["id"])) for event, message in found} == {
        ("new_message", 10),
        ("edited_message", 9),
    }


def test_difference_state_prefers_intermediate_state() -> None:
    previous = UpdateState(1, 2, 3, 4)
    result = {"_": "updates.differenceSlice", "intermediate_state": {"pts": 11, "qts": 12, "date": 13, "seq": 14}}
    state = _state_from_difference(result, previous)
    assert state == UpdateState(11, 12, 13, 14)


def test_difference_empty_advances_date_and_seq() -> None:
    previous = UpdateState(1, 2, 3, 4)
    state = _state_from_difference({"_": "updates.differenceEmpty", "date": 30, "seq": 40}, previous)
    assert state == UpdateState(1, 2, 30, 40)
