import { NextRequest, NextResponse } from "next/server";
import { unlink } from "fs/promises";
import path from "path";

const CROP_DIR = path.join(process.cwd(), "..", "crop_images");

export async function DELETE(req: NextRequest) {
  const { filename } = await req.json();
  if (!filename) return NextResponse.json({ error: "Missing filename" }, { status: 400 });

  const safe = path.basename(filename);
  await unlink(path.join(CROP_DIR, safe));

  // also delete matching json
  const jsonFile = safe.replace(/\.png$/, ".json");
  await unlink(path.join(CROP_DIR, jsonFile)).catch(() => {});

  return NextResponse.json({ ok: true });
}
