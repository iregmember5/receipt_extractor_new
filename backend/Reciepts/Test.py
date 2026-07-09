from pathlib import Path
from paddleocr import PaddleOCR


INPUT_FILE = r"D:\IREG\Reciepts\recipt 5.png"
OUTPUT_DIR = Path("./output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # Same as:
    # --ocr_version PP-OCRv5
    # --use_doc_orientation_classify True
    # --use_doc_unwarping True
    # --use_textline_orientation True
    # --device cpu
    ocr = PaddleOCR(
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=True,
        use_doc_unwarping=True,
        use_textline_orientation=True,
        device="cpu",
    )

    # Same as: -i receipt.jpg
    results = ocr.predict(INPUT_FILE)

    full_text = []

    for page_index, result in enumerate(results, start=1):
        print(f"\nPAGE {page_index}")
        print("=" * 50)

        # Print PaddleOCR's detailed result
        result.print()

        # Same as: --save_path ./output
        result.save_to_img(str(OUTPUT_DIR))
        result.save_to_json(str(OUTPUT_DIR))

        # Extract recognized text lines
        result_dict = result.to_dict() if hasattr(result, "to_dict") else {}

        texts = result_dict.get("rec_texts", [])
        scores = result_dict.get("rec_scores", [])

        for i, text in enumerate(texts):
            confidence = scores[i] if i < len(scores) else None

            if confidence is not None:
                print(f"{text}  | confidence={confidence:.4f}")
            else:
                print(text)

            full_text.append(text)

    # Save simple raw text file
    text_output_path = OUTPUT_DIR / "receipt_text.txt"

    with open(text_output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_text))

    print("\nOCR completed.")
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"Raw text file: {text_output_path}")


if __name__ == "__main__":
    main()