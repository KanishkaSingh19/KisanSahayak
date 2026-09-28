import sys
import time
from pathlib import Path

# Ensure project root in sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.agent.pipeline import KisanPipeline


def run_example_queries():
    print("=" * 80)
    print("🌾 KISANSAHAYAK PHASE 1 MVP - 5 BENCHMARK EVALUATION QUERIES")
    print("=" * 80)

    pipeline = KisanPipeline()

    test_queries = [
        {
            "id": 1,
            "category": "Crop Disease Management (Wheat)",
            "query": "गेहूं में पीली कुंगी (Yellow Rust) के लक्षण क्या हैं और इसका उपचार कैसे करें?",
        },
        {
            "id": 2,
            "category": "Pest Control & Spraying Timing (Mustard)",
            "query": "How to control aphids (mahu) in mustard crop, and what is the best time to spray?",
        },
        {
            "id": 3,
            "category": "Insect Pest Management (Rice/Paddy)",
            "query": "धान में भूरा तेला (Brown Planthopper) के नियंत्रण के लिए क्या करें?",
        },
        {
            "id": 4,
            "category": "Pesticide Safety & Statutory Restrictions (CIBRC)",
            "query": "क्या बैंगन या गोभी की फसल में मोनोक्रोटोफॉस (Monocrotophos) का उपयोग कर सकते हैं?",
        },
        {
            "id": 5,
            "category": "Agronomy / Critical Irrigation (Wheat)",
            "query": "What is the recommended sowing time and first critical irrigation stage for wheat?",
        },
        {
            "id": 6,
            "category": "Ag-Weather & Spray Window Advisory (Ludhiana)",
            "query": "लुधियाना में आज बारिश और मौसम का क्या हाल है, क्या कीटनाशक छिड़काव कर सकते हैं?",
        },
    ]

    for item in test_queries:
        print("\n" + "-" * 80)
        print(f"QUERY #{item['id']} [{item['category']}]")
        print(f"Farmer Query: {item['query']}")
        print("-" * 80)

        t0 = time.time()
        result = pipeline.process_query(item["query"])
        elapsed_ms = int((time.time() - t0) * 1000)

        print(f"• Classified Intent: {result.intent}")
        print(f"• Detected Crop: {result.processing_metadata.get('detected_crop')}")
        print(f"• Latency: {elapsed_ms} ms")
        print(f"• Grounding Passed: {result.is_grounded} (Score: {result.processing_metadata.get('grounding_score')})")
        print(f"• Total Evidence Chunks Retrieved: {len(result.retrieved_chunks)}")

        print("\n📋 GROUNDED ANSWER:")
        print(result.answer)

        if result.safety_disclaimers:
            print("\n⚠️ SAFETY DISCLAIMERS:")
            for disc in result.safety_disclaimers:
                print(f"  - {disc}")

        print("\n📚 OFFICIAL CITATIONS:")
        for cit in result.citations:
            print(f"  📌 {cit}")

    print("\n" + "=" * 80)
    print("All 5 queries processed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    run_example_queries()
