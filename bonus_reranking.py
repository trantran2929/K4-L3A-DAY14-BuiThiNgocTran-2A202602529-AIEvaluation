import json
from collections import Counter
from pathlib import Path

from template import RAGASEvaluator, rerank_by_overlap


def main() -> None:
    golden = json.loads(
        Path("golden_dataset.json").read_text(encoding="utf-8")
    )
    actual = json.loads(
        Path("artifacts/actual_answers.json").read_text(encoding="utf-8")
    )

    pairs = {pair["id"]: pair for pair in golden["qa_pairs"]}
    answers = {answer["id"]: answer for answer in actual["answers"]}

    # Chọn trước khi đo: ba cases thấp nhất và hai cases hỗ trợ khách hàng.
    selected_ids = ["A03", "A01", "A02", "M05", "M06"]
    evaluator = RAGASEvaluator()
    rows = []

    for pair_id in selected_ids:
        pair = pairs[pair_id]
        record = answers[pair_id]

        assert pair["question"] == record["question"]
        assert record["error"] is None

        contexts = [chunk["text"] for chunk in record["retrieved_contexts"]]

        # Rerank bằng câu hỏi thật, không dùng đáp án tham chiếu.
        reranked = rerank_by_overlap(contexts, pair["question"])

        # Bảo đảm không thêm, xóa hoặc làm mất chunks trùng nhau.
        assert Counter(contexts) == Counter(reranked)

        expected = pair["expected_answer"]

        recall_before = evaluator.evaluate_context_recall(
            contexts, expected
        )
        recall_after = evaluator.evaluate_context_recall(
            reranked, expected
        )
        precision_before = evaluator.evaluate_context_precision(
            contexts, expected
        )
        precision_after = evaluator.evaluate_context_precision(
            reranked, expected
        )

        assert abs(recall_before - recall_after) < 1e-12

        rows.append({
            "id": pair_id,
            "recall_before": recall_before,
            "recall_after": recall_after,
            "precision_before": precision_before,
            "precision_after": precision_after,
            "delta_precision": precision_after - precision_before,
            "contexts_before": contexts,
            "contexts_after": reranked,
        })

    print(
        "| ID | Recall before | Recall after | Precision before | "
        "Precision after | Delta Precision |"
    )
    print("|---|---:|---:|---:|---:|---:|")

    fields = [
        "recall_before",
        "recall_after",
        "precision_before",
        "precision_after",
        "delta_precision",
    ]

    for row in rows:
        values = " | ".join(f"{row[field]:.3f}" for field in fields)
        print(f"| {row['id']} | {values} |")

    averages = {
        field: sum(row[field] for row in rows) / len(rows)
        for field in fields
    }
    values = " | ".join(f"{averages[field]:.3f}" for field in fields)
    print(f"| **Avg** | {values} |")

    output = {
        "method": "word overlap with question; stable descending sort",
        "selected_ids": selected_ids,
        "source_generated_at": actual["generated_at"],
        "averages": averages,
        "results": rows,
    }

    output_path = Path("artifacts/reranking_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()