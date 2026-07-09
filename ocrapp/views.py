import json
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


def _resolve_media_path(json_url):
    """
    Turns a URL like '/media/results/<uuid>/xxx_res.json' (as returned by
    process_receipt_api_view) back into a real path on disk, and makes sure
    it actually lives inside media/results/ — so this endpoint can never be
    tricked into reading/writing an arbitrary file elsewhere on the server.
    Returns the resolved Path, or None if the URL is invalid/unsafe.
    """
    media_url = settings.MEDIA_URL  # e.g. "/media/"
    if not json_url or not json_url.startswith(media_url):
        return None

    relative_path = json_url[len(media_url):]
    target_path = (Path(settings.MEDIA_ROOT) / relative_path).resolve()
    results_root = (Path(settings.MEDIA_ROOT) / "results").resolve()

    try:
        target_path.relative_to(results_root)
    except ValueError:
        return None

    return target_path


@csrf_exempt
def update_receipt_api_view(request):
    """
    Receives corrections made in the frontend (drag-and-drop tags plus any
    in-place text edits) and writes them back into the SAME saved OCR JSON
    file on disk, at the exact rec_texts index they came from.

    Expected JSON body:
    {
        "json_url": "/media/results/<uuid>/xxx_res.json",
        "edits": [ {"index": 7, "newText": "Original Recipe"}, ... ],
        "tags": {"amount": {...}, "description": {...}, "date": {...}}  # optional, for reference
    }

    Matching by index (not by searching for the old text) is what makes
    this safe: the same amount like "180.00" can appear more than once on
    a receipt, so only the array position is unambiguous.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed."}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    json_url = body.get("json_url")
    edits = body.get("edits", [])
    tags = body.get("tags")

    target_path = _resolve_media_path(json_url)
    if target_path is None:
        return JsonResponse({"error": "Invalid or unsafe json_url."}, status=400)

    if not target_path.exists():
        return JsonResponse({"error": "Result file not found."}, status=404)

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return JsonResponse({"error": f"Failed to read JSON: {exc}"}, status=500)

    rec_texts = data.get("rec_texts")
    if rec_texts is None:
        return JsonResponse({"error": "rec_texts not found in saved JSON."}, status=400)

    applied_indices = []
    skipped = []

    for edit in edits:
        idx = edit.get("index")
        new_text = edit.get("newText")

        if not isinstance(idx, int) or new_text is None:
            skipped.append(edit)
            continue
        if idx < 0 or idx >= len(rec_texts):
            skipped.append(edit)
            continue

        rec_texts[idx] = new_text
        applied_indices.append(idx)

    data["rec_texts"] = rec_texts

    # Store the tagged fields (amount/description/date) alongside the OCR
    # data too, so downstream consumers don't have to re-derive them.
    if isinstance(tags, dict):
        data["tags"] = tags

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        return JsonResponse({"error": f"Failed to write JSON: {exc}"}, status=500)

    return JsonResponse(
        {
            "message": "Receipt JSON updated successfully.",
            "applied_indices": applied_indices,
            "skipped": skipped,
        }
    )