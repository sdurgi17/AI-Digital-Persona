from app.services.llm.anthropic_provider import map_messages


def test_system_hoisted_and_joined():
    system, turns = map_messages(
        [
            {"role": "system", "content": "You are X."},
            {"role": "system", "content": "Context: Y."},
            {"role": "user", "content": "hi"},
        ]
    )
    assert system == "You are X.\n\nContext: Y."
    assert turns == [{"role": "user", "content": "hi"}]


def test_consecutive_same_role_merged():
    _, turns = map_messages(
        [
            {"role": "user", "content": "one"},
            {"role": "user", "content": "two"},
            {"role": "assistant", "content": "reply"},
            {"role": "assistant", "content": "more"},
            {"role": "user", "content": "three"},
        ]
    )
    assert turns == [
        {"role": "user", "content": "one\n\ntwo"},
        {"role": "assistant", "content": "reply\n\nmore"},
        {"role": "user", "content": "three"},
    ]


def test_leading_assistant_gets_placeholder_user():
    # ElevenLabs sends the agent's first_message as assistant history
    _, turns = map_messages(
        [
            {"role": "system", "content": "persona"},
            {"role": "assistant", "content": "Hey, what's up?"},
            {"role": "user", "content": "who are you?"},
        ]
    )
    assert turns[0]["role"] == "user"
    assert turns[1] == {"role": "assistant", "content": "Hey, what's up?"}


def test_rag_system_message_mid_conversation():
    # gateway injects a system message just before the last user turn
    system, turns = map_messages(
        [
            {"role": "system", "content": "persona prompt"},
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "system", "content": "RAG: excerpts"},
            {"role": "user", "content": "q2"},
        ]
    )
    assert "persona prompt" in system and "RAG: excerpts" in system
    assert turns == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]


def test_openai_content_parts_flattened():
    _, turns = map_messages(
        [{"role": "user", "content": [{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {}}]}]
    )
    assert turns == [{"role": "user", "content": "hello"}]


def test_empty_and_unknown_roles_dropped():
    _, turns = map_messages(
        [
            {"role": "tool", "content": "ignored"},
            {"role": "user", "content": "   "},
            {"role": "user", "content": "real"},
        ]
    )
    assert turns == [{"role": "user", "content": "real"}]


def test_no_turns_gets_placeholder():
    system, turns = map_messages([{"role": "system", "content": "only system"}])
    assert system == "only system"
    assert turns == [{"role": "user", "content": "(conversation begins)"}]
