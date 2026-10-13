
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


PRIORITY_RANK = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


def priority_score(
    emergency_type: str,
    people_count: int,
    message: str,
    battery: int,
) -> str:
    """
    Transparent prototype scoring policy.
    This is not a medical triage system.
    """
    text = f"{emergency_type} {message}".lower()

    score = 0

    critical_keywords = (
        "trapped",
        "collapse",
        "unconscious",
        "not breathing",
        "fire",
        "drowning",
        "severe bleeding",
    )

    high_keywords = (
        "medical",
        "injury",
        "bleeding",
        "flood",
        "missing",
    )

    if any(word in text for word in critical_keywords):
        score += 5

    if any(word in text for word in high_keywords):
        score += 3

    if people_count >= 5:
        score += 2
    elif people_count >= 2:
        score += 1

    if battery <= 10:
        score += 1

    if score >= 6:
        return "CRITICAL"
    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"

    return "LOW"


def carq_sort(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Baseline CARQ ordering:
    1. Higher rule-based priority first.
    2. Older reports first within the same priority.
    3. Missing timestamps sort last within their priority.
    """
    def sort_key(packet):
        priority = packet.get("priority", "LOW")
        rank = PRIORITY_RANK.get(priority, 4)

        created_at = packet.get("created_at")
        if not created_at:
            timestamp = float("inf")
        else:
            try:
                parsed = datetime.fromisoformat(
                    str(created_at).replace("Z", "+00:00")
                )

                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)

                timestamp = parsed.timestamp()
            except (ValueError, TypeError, OverflowError):
                timestamp = float("inf")

        return rank, timestamp

    return sorted(packets, key=sort_key)


def simulate_relay(
    packet: dict,
    nodes: list[str],
    network_condition: str,
    ttl: int,
    duplicate: bool = False,
) -> dict:
    """
    SOFTWARE SIMULATION ONLY.

    Does not perform Bluetooth, Wi-Fi Direct, or radio communication.
    A successful result represents the simulated route.
    """
    nodes = [node.strip() for node in nodes if node.strip()]
    if not nodes:
        nodes = ["Victim-Phone", "Rescue-Gateway"]

    message_id = packet.get("message_id", "SOS-DEMO")
    ttl = max(0, int(ttl))

    events = [{
        "node": nodes[0],
        "event": f"Created packet {message_id}",
    }]

    # The first node is the source. Every subsequent node
    # represents one simulated transmission hop.
    route = nodes[1:] or ["Rescue-Gateway"]

    if ttl == 0 and route:
        events.append({
            "node": nodes[0],
            "event": "TTL is zero; forwarding stopped",
        })
        return {
            "delivered": False,
            "hops": 0,
            "events": events,
            "status": "TTL_EXPIRED",
            "message_id": message_id,
        }

    condition = network_condition.lower()

    if "no gateway" in condition or "partition" in condition:
        events.append({
            "node": nodes[-1],
            "event": (
                "Gateway unreachable; packet remains queued "
                "for a future retry"
            ),
        })

        return {
            "delivered": False,
            "hops": 0,
            "events": events,
            "status": "QUEUED",
            "message_id": message_id,
        }

    hops = 0
    seen_ids = {message_id}

    intermittent = "intermittent" in condition

    if intermittent:
        events.append({
            "node": nodes[0],
            "event": "Connection unavailable; packet saved in retry queue",
        })
        events.append({
            "node": route[0],
            "event": "Connectivity restored; forwarding resumed",
        })

    for node in route:
        next_hop = hops + 1

        if next_hop > ttl:
            events.append({
                "node": node,
                "event": "TTL exceeded; forwarding stopped",
            })

            return {
                "delivered": False,
                "hops": hops,
                "events": events,
                "status": "TTL_EXPIRED",
                "message_id": message_id,
            }

        hops = next_hop

        events.append({
            "node": node,
            "event": f"Packet received at simulated hop {hops}",
        })

    if duplicate:
        duplicate_id = message_id

        if duplicate_id in seen_ids:
            events.append({
                "node": route[0],
                "event": (
                    f"Duplicate {duplicate_id} detected; "
                    "second copy discarded"
                ),
            })
        else:
            seen_ids.add(duplicate_id)

    events.append({
        "node": route[-1],
        "event": "Simulated gateway receipt recorded",
    })

    return {
        "delivered": True,
        "hops": hops,
        "events": events,
        "status": "SIMULATED_DELIVERY",
        "message_id": message_id,
    }