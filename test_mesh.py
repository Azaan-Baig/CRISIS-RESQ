
from src.mesh import priority_score, carq_sort, simulate_relay


def test_critical_trapped_group():
    assert priority_score(
        "Trapped / building collapse",
        5,
        "We are trapped",
        5,
    ) == "CRITICAL"


def test_low_priority():
    assert priority_score(
        "Other",
        1,
        "Need information",
        80,
    ) == "LOW"


def test_carq_orders_critical_before_low():
    packets = [
        {"message_id": "A", "priority": "LOW"},
        {"message_id": "B", "priority": "CRITICAL"},
        {"message_id": "C", "priority": "HIGH"},
    ]

    result = carq_sort(packets)

    assert [
        packet["message_id"] for packet in result
    ] == ["B", "C", "A"]


def test_carq_older_report_first_with_same_priority():
    packets = [
        {
            "message_id": "NEW",
            "priority": "HIGH",
            "created_at": "2026-10-13T10:30:00+00:00",
        },
        {
            "message_id": "OLD",
            "priority": "HIGH",
            "created_at": "2026-10-13T10:00:00+00:00",
        },
    ]

    result = carq_sort(packets)

    assert result[0]["message_id"] == "OLD"


def test_relay_delivered():
    result = simulate_relay(
        {"message_id": "SOS-X", "priority": "HIGH"},
        ["Victim", "Relay", "Gateway"],
        "Connected route available",
        5,
    )

    assert result["delivered"] is True
    assert result["hops"] == 2
    assert result["status"] == "SIMULATED_DELIVERY"


def test_partition_queues_packet():
    result = simulate_relay(
        {"message_id": "SOS-X"},
        ["Victim", "Relay", "Gateway"],
        "Network partition — no gateway reachable",
        5,
    )

    assert result["delivered"] is False
    assert result["status"] == "QUEUED"


def test_ttl_prevents_excessive_forwarding():
    result = simulate_relay(
        {"message_id": "SOS-TTL"},
        ["Victim", "Relay", "Gateway"],
        "Connected route available",
        1,
    )

    assert result["delivered"] is False
    assert result["status"] == "TTL_EXPIRED"


def test_duplicate_is_recorded_as_discarded():
    result = simulate_relay(
        {"message_id": "SOS-DUP"},
        ["Victim", "Relay", "Gateway"],
        "Connected route available",
        5,
        duplicate=True,
    )

    assert result["delivered"] is True
    assert any(
        "Duplicate" in event["event"]
        and "discarded" in event["event"]
        for event in result["events"]
    )