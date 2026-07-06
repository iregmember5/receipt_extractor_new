from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .services import run_receipt_pipeline


def _save_and_process_uploaded_receipt(uploaded):
	upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
	result_dir = Path(settings.MEDIA_ROOT) / "results" / uuid4().hex
	upload_dir.mkdir(parents=True, exist_ok=True)

	upload_path = upload_dir / uploaded.name

	with open(upload_path, "wb") as f:
		for chunk in uploaded.chunks():
			f.write(chunk)

	outputs = run_receipt_pipeline(upload_path, result_dir)

	ordered_text_url = settings.MEDIA_URL + str(outputs["ordered_text_path"].relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
	layout_text_url = settings.MEDIA_URL + str(outputs["layout_text_path"].relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
	json_url = settings.MEDIA_URL + str(outputs["json_path"].relative_to(settings.MEDIA_ROOT)).replace("\\", "/")

	return {
		"ordered_text_url": ordered_text_url,
		"layout_text_url": layout_text_url,
		"json_url": json_url,
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
		except Exception as exc:
			context["error"] = f"Processing failed: {exc}"
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
	except Exception as exc:
		return JsonResponse({"error": f"Processing failed: {exc}"}, status=500)

	return JsonResponse(
		{
			"message": "Receipt processed successfully.",
			"ordered_text_url": outputs["ordered_text_url"],
			"layout_text_url": outputs["layout_text_url"],
			"json_url": outputs["json_url"],
		}
	)
