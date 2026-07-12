"""CLI entry point: python -m voicemeet"""

import sys


def main() -> None:
    if "--version" in sys.argv or "-V" in sys.argv:
        from voicemeet import __version__

        print(f"voicemeet {__version__}")
        return

    if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) <= 1:
        print("voicemeet — Premium local meeting notes")
        print()
        print("Usage: python -m voicemeet <command> [options]")
        print()
        print("Commands will be available after Phase 7 (CLI).")
        print("  --version    Show version and exit")
        return

    print("voicemeet ready — full CLI coming in Phase 7")


if __name__ == "__main__":
    main()
