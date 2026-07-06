from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .services import extract_items_from_json_data, normalize_ocr_result


class PaddleOcrResultParsingTests(TestCase):
	def test_normalize_ocr_result_uses_json_res_payload(self):
		class FakePaddleResult(dict):
			@property
			def json(self):
				return {
					"res": {
						"rec_texts": ["Total", "100.00"],
						"rec_scores": [0.99, 0.98],
						"rec_polys": [
							[[0, 0], [40, 0], [40, 10], [0, 10]],
							[[50, 0], [90, 0], [90, 10], [50, 10]],
						],
					}
				}

		data = normalize_ocr_result(FakePaddleResult())

		self.assertEqual(data["rec_texts"], ["Total", "100.00"])

	def test_extract_items_from_nested_ocr_result(self):
		data = normalize_ocr_result(
			{
				"res": {
					"rec_texts": ["Total", "100.00"],
					"rec_scores": [0.99, 0.98],
					"rec_polys": [
						[[0, 0], [40, 0], [40, 10], [0, 10]],
						[[50, 0], [90, 0], [90, 10], [50, 10]],
					],
				}
			}
		)

		items = extract_items_from_json_data(data)

		self.assertEqual([item["text"] for item in items], ["Total", "100.00"])


class ProcessReceiptApiTests(TestCase):
	@patch("ocrapp.views._save_and_process_uploaded_receipt")
	def test_process_receipt_api_returns_urls(self, mock_process):
		mock_process.return_value = {
			"ordered_text_url": "/media/results/demo/ordered.txt",
			"layout_text_url": "/media/results/demo/layout.txt",
			"json_url": "/media/results/demo/result.json",
		}

		image_file = SimpleUploadedFile(
			"receipt.png",
			b"fake-image-bytes",
			content_type="image/png",
		)

		response = self.client.post(
			"/api/process-receipt/",
			{"receipt_image": image_file},
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn("ordered_text_url", response.json())
		self.assertIn("layout_text_url", response.json())
		self.assertIn("json_url", response.json())

	def test_process_receipt_api_requires_file(self):
		response = self.client.post("/api/process-receipt/", {})

		self.assertEqual(response.status_code, 400)

	def test_process_receipt_api_requires_post(self):
		response = self.client.get("/api/process-receipt/")

		self.assertEqual(response.status_code, 405)

# Create your tests here.
