from src.ai.gemini_client import GeminiClient, GeminiClientError
from src.services.enrichment_service import EnrichmentService


def main() -> int:
    try:
        client = GeminiClient()
        service = EnrichmentService(gemini_client=client)

        result = service.run()

        print(f"Processed : {result.processed}")
        print(f"Skipped   : {result.skipped}")
        print(f"Failed    : {len(result.failed)}")

        if result.failed:
            print("\nFailures:")
            for failure in result.failed:
                print(f"- {failure.review_id}: {failure.error}")

        return 0

    except (GeminiClientError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())