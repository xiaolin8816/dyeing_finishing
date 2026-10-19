import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import frappe
from frappe import _


def _check(label, ok, detail, level=None):
	return {"label": label, "status": "ok" if ok else (level or "error"), "detail": str(detail or "")}


def _typst_version():
	path = shutil.which("typst")
	if not path:
		return None, None
	result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10, check=False)
	return path, (result.stdout or result.stderr).strip()


@frappe.whitelist()
def get_diagnostics():
	frappe.only_for("System Manager")
	checks = []
	apps = frappe.get_installed_apps()
	checks.append(_check("Crispy Print", "crispy_print" in apps,
		"已安装" if "crispy_print" in apps else "未安装 crispy_print"))
	try:
		import crispy_print
		version = getattr(crispy_print, "__version__", "未声明版本")
		checks.append(_check("Crispy Print 版本", True, version))
	except Exception as exc:
		checks.append(_check("Crispy Print 版本", False, exc))

	typst_path, typst_version = _typst_version()
	checks.append(_check("Typst 编译器", bool(typst_path), typst_version or "未找到 typst 命令"))
	font_candidates = [Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
		Path(frappe.get_site_path("private", "files", "crispy_print", "fonts", "WenQuanYiZenHei.ttc"))]
	font = next((path for path in font_candidates if path.exists()), None)
	checks.append(_check("中文字体", bool(font), font or "未找到文泉驿正黑字体"))

	asset = None
	if "crispy_print" in apps:
		asset = Path(frappe.get_app_path("crispy_print", "public", "vendor", "pdfjs", "pdf.min.mjs"))
	checks.append(_check("PDF 预览资源", bool(asset and asset.exists()), asset or "Crispy Print 未安装"))
	private_dir = Path(frappe.get_site_path("private", "files", "crispy_print"))
	private_dir.mkdir(parents=True, exist_ok=True)
	checks.append(_check("报表临时目录", os.access(private_dir, os.W_OK), private_dir))

	for doctype in ("Crispy Format", "Crispy Template", "Dyeing Paper Format"):
		checks.append(_check(doctype, frappe.db.exists("DocType", doctype), "数据模型已就绪" if frappe.db.exists("DocType", doctype) else "缺少数据模型"))
	format_count = frappe.db.count("Crispy Format") if frappe.db.exists("DocType", "Crispy Format") else 0
	active_count = frappe.db.count("Crispy Template", {"status": "Approved", "is_active": 1}) if frappe.db.exists("DocType", "Crispy Template") else 0
	paper_count = frappe.db.count("Dyeing Paper Format", {"enabled": 1}) if frappe.db.exists("DocType", "Dyeing Paper Format") else 0
	checks.append(_check("可视化模板", format_count > 0, f"{format_count} 个设计模板"))
	checks.append(_check("已发布模板", active_count > 0, f"{active_count} 个可打印模板"))
	checks.append(_check("纸张规格", paper_count > 0, f"{paper_count} 个已启用规格"))
	return {"checks": checks, "healthy": all(row["status"] == "ok" for row in checks)}


@frappe.whitelist()
def run_smoke_test():
	frappe.only_for("System Manager")
	typst_path, version = _typst_version()
	if not typst_path:
		frappe.throw(_("未找到 Typst 编译器"))
	font_dir = Path(frappe.get_site_path("private", "files", "crispy_print", "fonts"))
	with tempfile.TemporaryDirectory(dir=frappe.get_site_path("private", "files")) as temp_dir:
		source = Path(temp_dir) / "test.typ"
		output = Path(temp_dir) / "test.pdf"
		source.write_text('#set text(font: "WenQuanYi Zen Hei", size: 12pt)\n[印染整理报表引擎测试正常]', encoding="utf-8")
		command = [typst_path, "compile"]
		if font_dir.exists():
			command.extend(["--font-path", str(font_dir)])
		command.extend([str(source), str(output)])
		result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
		if result.returncode or not output.exists():
			frappe.throw(_("Typst 中文试打失败：{0}").format((result.stderr or result.stdout)[-1000:]))
		return {"message": "Crispy Print → Typst 中文 PDF 试打成功", "typst": version,
			"pdf_bytes": output.stat().st_size}
