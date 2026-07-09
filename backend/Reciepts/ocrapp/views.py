import json
import traceback
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from PIL import Image

from .services import run_receipt_pipeline, ocr_image, find_texts_in_region, compare_texts, ocr_image, find_texts_in_region, compare_texts


def _get_image_size(uploaded):
	img = Image.open(uploaded)
	return img.width, img.height


def _save_and_process_uploaded_receipt(uploaded):
	upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
	result_dir = Path(settings.MEDIA_ROOT) / "results" / uuid4().hex
	upload_dir.mkdir(parents=True, exist_ok=True)

	upload_path = upload_dir / uploaded.name

	with open(upload_path, "wb") as f:
		for chunk in uploaded.chunks():
			f.write(chunk)

	img_width, img_height = _get_image_size(upload_path)
	outputs = run_receipt_pipeline(upload_path, result_dir)

	ordered_text_url = settings.MEDIA_URL + str(outputs["ordered_text_path"].relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
	layout_text_url = settings.MEDIA_URL + str(outputs["layout_text_path"].relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
	json_url = settings.MEDIA_URL + str(outputs["json_path"].relative_to(settings.MEDIA_ROOT)).replace("\\", "/")

	return {
		"ordered_text_url": ordered_text_url,
		"layout_text_url": layout_text_url,
		"json_url": json_url,
		"json_path": outputs["json_path"],
		"image_width": img_width,
		"image_height": img_height,
	}


def home_view(request):
	context = {}

	if request.method == "POST":
		uploaded = request.FILES.get("receipt_image")

		if not uploaded:
			context["error"] = "Please upload a receipt image."
			return render(request, "ocrapp/index.html", context)

		try:
			outputs = _save_and_process_uploaded_receipt(uploaded)
		except Exception:
			context["error"] = f"Processing failed:\n{traceback.format_exc()}"
			return render(request, "ocrapp/index.html", context)

		context["success"] = True
		context["ordered_text_url"] = outputs["ordered_text_url"]
		context["layout_text_url"] = outputs["layout_text_url"]
		context["json_url"] = outputs["json_url"]

	return render(request, "ocrapp/index.html", context)


@csrf_exempt
def process_receipt_api_view(request):
	if request.method != "POST":
		return JsonResponse({"error": "Only POST method is allowed."}, status=405)

	uploaded = request.FILES.get("receipt_image")

	if not uploaded:
		return JsonResponse({"error": "receipt_image file is required."}, status=400)

	try:
		outputs = _save_and_process_uploaded_receipt(uploaded)
	except Exception:
		return JsonResponse({"error": f"Processing failed:\n{traceback.format_exc()}"}, status=500)

	return JsonResponse(
		{
			"message": "Receipt processed successfully.",
			"ordered_text_url": outputs["ordered_text_url"],
			"layout_text_url": outputs["layout_text_url"],
			"json_url": outputs["json_url"],
		}
	)


@csrf_exempt
def process_receipt_json_view(request):
	if request.method != "POST":
		return JsonResponse({"error": "Only POST method is allowed."}, status=405)

	uploaded = request.FILES.get("receipt_image")

	if not uploaded:
		return JsonResponse({"error": "receipt_image file is required."}, status=400)

	try:
		outputs = _save_and_process_uploaded_receipt(uploaded)
	except Exception:
		return JsonResponse({"error": f"Processing failed:\n{traceback.format_exc()}"}, status=500)

	json_path = outputs["json_path"]
	with open(json_path, "r", encoding="utf-8") as f:
		ocr_data = json.load(f)

	return JsonResponse(
		{
			"message": "Receipt processed successfully.",
			"image_width": outputs["image_width"],
			"image_height": outputs["image_height"],
			"ocr_data": ocr_data,
		}
	)


@csrf_exempt
def compare_crop_view(request):
	if request.method != "POST":
		return JsonResponse({"error": "Only POST method is allowed."}, status=405)

	crop_image = request.FILES.get("crop_image")
	crop_meta_str = request.POST.get("crop_meta")
	original_ocr_str = request.POST.get("original_ocr")

	if not crop_image or not crop_meta_str or not original_ocr_str:
		return JsonResponse({"error": "crop_image, crop_meta and original_ocr are required."}, status=400)

	try:
		crop_meta = json.loads(crop_meta_str)
		original_ocr = json.loads(original_ocr_str)
		src_rect = crop_meta["srcRect"]

		upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
		upload_dir.mkdir(parents=True, exist_ok=True)
		crop_path = upload_dir / f"crop_{uuid4().hex}.png"
		with open(crop_path, "wb") as f:
			for chunk in crop_image.chunks():
				f.write(chunk)

		crop_ocr = ocr_image(crop_path)
		crop_texts = crop_ocr.get("rec_texts", [])
		crop_scores = crop_ocr.get("rec_scores", [])

		original_texts = find_texts_in_region(original_ocr, src_rect)

		result = compare_texts(crop_texts, original_texts)
		result["label"] = crop_meta.get("label", "")
		result["src_rect"] = src_rect
		result["crop_confidence"] = round(sum(crop_scores) / len(crop_scores), 3) if crop_scores else None

		crop_path.unlink(missing_ok=True)

		return JsonResponse(result)

	except Exception:
		return JsonResponse({"error": f"Comparison failed:\n{traceback.format_exc()}"}, status=500)
