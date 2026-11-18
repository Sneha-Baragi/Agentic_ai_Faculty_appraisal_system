"""Local Mock API Tool for Campus Schedule Services.

Course: Agentic AI (26ECAC401)
Lab: 5 - MCP-Style Connector
Scenario: Local Campus Mock API Tool

Provides a deterministic, local mock API service simulating campus event feeds
and room schedule endpoints without external network requests or API keys.
"""

from typing import Any, Dict, List, Optional


class LocalApiTool:
    """Mock API tool providing deterministic campus event and scheduling data."""

    def __init__(self) -> None:
        self.endpoints: Dict[str, Any] = {
            "events_today": self._get_events_today,
            "event_details": self._get_event_details,
            "system_status": self._get_system_status,
        }

    def _get_events_today(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return the scheduled events happening on campus today."""
        events = [
            {
                "event": "AI Club Talk",
                "time": "14:00 - 15:30",
                "room": "Auditorium Hall B",
                "speaker": "Dr. Aarav Sharma",
                "status": "confirmed",
            },
            {
                "event": "Robotics Demo",
                "time": "16:00 - 17:30",
                "room": "Robotics Lab 204",
                "speaker": "Prof. Priya Verma",
                "status": "confirmed",
            },
        ]
        return {
            "date": "Today",
            "total_events": len(events),
            "events": events,
        }

    def _get_event_details(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return detailed information for a specific requested event."""
        params = params or {}
        event_name = params.get("event", "AI Club Talk")

        database = {
            "AI Club Talk": {
                "event": "AI Club Talk",
                "topic": "Practical Agent Architectures & MCP Tools",
                "registered_attendees": 12,
                "room": "Auditorium Hall B",
                "host_club": "AI & Machine Learning Society",
            },
            "Hackathon Kickoff": {
                "event": "Hackathon Kickoff",
                "topic": "48-Hour Agentic Systems Sprint Launch",
                "registered_attendees": 9,
                "room": "Innovation Complex Ground Floor",
                "host_club": "Hackathon Guild",
            },
            "Robotics Demo": {
                "event": "Robotics Demo",
                "topic": "Autonomous Ground Vehicle Navigation Demo",
                "registered_attendees": 15,
                "room": "Robotics Lab 204",
                "host_club": "Robotics Society",
            },
        }

        if event_name in database:
            return database[event_name]

        return {
            "event": event_name,
            "topic": "General Campus Gathering",
            "registered_attendees": 0,
            "room": "TBD",
            "host_club": "Student Council",
        }

    def _get_system_status(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return operational health metrics for campus mock services."""
        return {
            "service": "Campus Mock API Gateway",
            "status": "online",
            "environment": "Local Simulation",
            "active_term": "Spring 2026",
            "endpoints_available": list(self.endpoints.keys()),
        }

    def call_api(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoke a local API endpoint.

        Args:
            endpoint: Name of the endpoint to query (e.g. 'events_today').
            params: Optional query parameters dictionary.

        Returns:
            Structured dictionary response indicating success or structured error.
        """
        cleaned_endpoint = endpoint.strip() if endpoint else ""

        if cleaned_endpoint not in self.endpoints:
            return {
                "status": "error",
                "error_code": "ENDPOINT_NOT_FOUND",
                "message": (
                    f"Unknown API endpoint: '{cleaned_endpoint}'. "
                    f"Available endpoints are: {sorted(list(self.endpoints.keys()))}."
                ),
            }

        try:
            handler = self.endpoints[cleaned_endpoint]
            data = handler(params)
            return {
                "status": "success",
                "endpoint": cleaned_endpoint,
                "data": data,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "API_EXECUTION_ERROR",
                "message": f"API invocation failed on endpoint '{cleaned_endpoint}': {str(exc)}",
            }
