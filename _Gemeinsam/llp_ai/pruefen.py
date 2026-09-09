"""Zeigt den Foundry-Status ohne Schlüssel oder Endpunkt."""

from __future__ import annotations

from llp_ai.company_ai import describe_status


def main() -> int:
    status = describe_status()
    print("LLP Foundry-Status")
    print("  Eingeschaltet: ", "ja" if status["enabled"] else "nein")
    print("  Anbieter Foundry:", "ja" if status["provider_ok"] else "nein")
    print("  Endpoint gesetzt:", "ja" if status["endpoint_gesetzt"] else "nein")
    print("  Deployment gesetzt:", "ja" if status["deployment_gesetzt"] else "nein")
    print("  Schluessel gesetzt:", "ja" if status["schluessel_gesetzt"] else "nein")
    print("  Bereit:          ", "ja" if status["bereit"] else "nein")
    print()
    print(status["hinweis"])
    return 0 if status["bereit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
