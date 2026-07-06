# Receipt OCR Django Project

This project accepts a receipt image upload, runs PaddleOCR, and returns:

- Ordered text file (line-sorted)
- Layout text file (column-preserved approximation)
- OCR JSON output file

## Project Structure

- `config/` Django project settings and root URLs
- `ocrapp/` Upload view and OCR processing pipeline
- `templates/ocrapp/index.html` Upload UI

## Setup

1. Activate your virtual environment.
2. Install dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Run migrations:

```powershell
.\venv\Scripts\python.exe manage.py migrate
```

4. Start server:

```powershell
.\venv\Scripts\python.exe manage.py runserver
```

5. Open in browser:

- http://127.0.0.1:8000/

## Local Run Commands (Windows PowerShell)

```powershell
cd D:\IREG\Reciepts
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver
```

## API Endpoint

- Endpoint: `POST /api/process-receipt/`
- Form field name: `receipt_image`
- Content type: `multipart/form-data`

Example PowerShell request while server is running:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/process-receipt/" ^
   -F "receipt_image=@recipt 5.png"
```

Successful response example:

```json
{
   "message": "Receipt processed successfully.",
   "ordered_text_url": "/media/results/<id>/<name>_text_ordered.txt",
   "layout_text_url": "/media/results/<id>/<name>_text_layout.txt",
   "json_url": "/media/results/<id>/<name>_res.json"
}
```

Note: The first real OCR request can take longer because model files are loaded/downloaded.

## Workflow

1. Upload a receipt image.
2. App runs OCR and builds `<image_name>_res.json`.
3. App cleans/groups text and creates:
   - `<image_name>_text_ordered.txt`
   - `<image_name>_text_layout.txt`
4. Download links are shown on the results page.

## Output Location

Generated files are saved under `media/results/<request_id>/`.
Uploaded images are stored under `media/uploads/`.
