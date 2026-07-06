<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Receipt OCR Processor</title>
  <style>
    :root {
      --bg-a: #f3f7ef;
      --bg-b: #e1efe3;
      --panel: #ffffff;
      --ink: #0f2a20;
      --accent: #0b7a5b;
      --accent-2: #d7efe4;
      --danger: #b42318;
      --radius: 16px;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background: radial-gradient(circle at 20% 20%, var(--bg-b), var(--bg-a));
      color: var(--ink);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 20px;
    }

    .card {
      width: min(780px, 100%);
      background: var(--panel);
      border-radius: var(--radius);
      box-shadow: 0 16px 36px rgba(10, 30, 20, 0.15);
      overflow: hidden;
      animation: rise 350ms ease;
    }

    .hero {
      padding: 26px 28px;
      background: linear-gradient(130deg, var(--accent), #0f9b73);
      color: #fff;
    }

    .hero h1 {
      margin: 0;
      font-size: 1.6rem;
    }

    .hero p {
      margin: 8px 0 0;
      opacity: 0.95;
    }

    .body {
      padding: 22px 28px 28px;
    }

    form {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-bottom: 14px;
    }

    input[type="file"] {
      flex: 1 1 300px;
      border: 1px solid #c8d7d0;
      border-radius: 10px;
      padding: 10px;
      background: #f8fcfa;
    }

    button {
      border: none;
      border-radius: 10px;
      background: var(--accent);
      color: #fff;
      font-weight: 600;
      padding: 11px 18px;
      cursor: pointer;
    }

    .error {
      background: #fee4e2;
      color: var(--danger);
      border: 1px solid #fecdca;
      border-radius: 10px;
      padding: 10px 12px;
      margin-top: 12px;
    }

    .success {
      background: var(--accent-2);
      border: 1px solid #b5e2cd;
      border-radius: 10px;
      padding: 14px;
      margin-top: 14px;
    }

    .downloads {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }

    .downloads a {
      display: inline-block;
      text-decoration: none;
      border-radius: 10px;
      border: 1px solid #7bc7ab;
      background: #fff;
      color: #055f46;
      padding: 10px 14px;
      font-weight: 600;
    }

    @keyframes rise {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
  </style>
</head>
<body>
  <main class="card">
    <section class="hero">
      <h1>Receipt OCR to Text Files</h1>
      <p>Upload a receipt image and download ordered text and layout-preserved text.</p>
    </section>

    <section class="body">
      <form method="post" enctype="multipart/form-data">
        {% csrf_token %}
        <input type="file" name="receipt_image" accept="image/*" required>
        <button type="submit">Process Receipt</button>
      </form>

      {% if error %}
        <div class="error">{{ error }}</div>
      {% endif %}

      {% if success %}
        <div class="success">
          Processing complete. Download your files:
          <div class="downloads">
            <a href="{{ ordered_text_url }}" download>Ordered Text</a>
            <a href="{{ layout_text_url }}" download>Layout Text</a>
            <a href="{{ json_url }}" download>OCR JSON</a>
          </div>
        </div>
      {% endif %}
    </section>
  </main>
</body>
</html>
