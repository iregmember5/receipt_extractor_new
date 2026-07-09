import json
import traceback
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from PIL import Image

from .services import run_receipt_pipeline, update_ocr_texts


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
def update_ocr_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed."}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    ocr_data = body.get("ocr_data")
    updates = body.get("updates", [])

    if not ocr_data or not updates:
        return JsonResponse({"error": "ocr_data and updates are required."}, status=400)

    if "rec_texts" not in ocr_data or "rec_polys" not in ocr_data:
        return JsonResponse({"error": "ocr_data must contain rec_texts and rec_polys."}, status=400)

    new_ocr_data = update_ocr_texts(ocr_data, updates)

    return JsonResponse({"ocr_data": new_ocr_data})


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
