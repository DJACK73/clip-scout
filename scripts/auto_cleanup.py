import app.cleanup as cleanup

MAX_AUTO = 5


def main() -> int:
    items = cleanup.plan(None)
    if not items:
        return 0
    if len(items) > MAX_AUTO:
        print(f"auto-cleanup refusé: {len(items)} fichiers (> {MAX_AUTO}), lancer app.cleanup à la main")
        return 1
    for path, _ in items:
        path.unlink(missing_ok=True)
        print(f"supprimé: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
