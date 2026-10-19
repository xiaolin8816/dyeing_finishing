import base64
import hashlib
import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import getdate, nowdate


PUBLIC_EXPONENT = 65537
PUBLIC_MODULUS = int(
	"D54030CB38A8D42FC8F4E3EA2A9B8223FADC68B23BE547924013731ABC98F12DAA0910723FF4F27F42A0344E345259ABF2FE67BA4164916E0C22597E6194FD7E969ABD1BE60DA17969C0C5BF89E7AB1E93AF3E26E6E60A98A5BB501829BE9797B39544689E5C166DC2CF2DE9B4F01C09BDE38484BBD89B5BE7C016B22E62C5BA913A795BC6D018BD7618D8450B0C33CAA2C10141F09A79E0A56EF0B1A3528A0A5850C307082D305432ADB3DF06A41963D0562C84658BB8D36890E3B49CF0188FBDFDCDA708279552DA0278E34865603A59133A9BB4AD86B546B4CBE773C7680D8926AEAA565F39D86126F60E70E7247575AC8450C29374A65B5CDD70FF95B7B7",
	16,
)
GRACE_DAYS = 15
TRANSITION_DAYS = 30
LICENSE_DOCTYPE = "Dyeing Finishing License"
MODULE_NAME = "dyeing_finishing"


def _b64decode(value):
	return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_rsa_sha256(message, signature):
	key_size = (PUBLIC_MODULUS.bit_length() + 7) // 8
	if len(signature) != key_size:
		return False
	decoded = pow(int.from_bytes(signature, "big"), PUBLIC_EXPONENT, PUBLIC_MODULUS).to_bytes(key_size, "big")
	digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(message).digest()
	padding_length = key_size - len(digest_info) - 3
	return decoded == b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info


def decode_license(token):
	try:
		container = json.loads((token or "").strip())
		payload_bytes = _b64decode(container["payload"])
		signature = _b64decode(container["signature"])
		if not _verify_rsa_sha256(payload_bytes, signature):
			raise ValueError("signature")
		payload = json.loads(payload_bytes.decode("utf-8"))
	except Exception:
		frappe.throw(_("许可证格式错误或数字签名无效"))
	if payload.get("site") not in (frappe.local.site, "*"):
		frappe.throw(_("许可证不属于当前站点 {0}").format(frappe.local.site))
	if "dyeing_finishing" not in (payload.get("features") or []):
		frappe.throw(_("许可证未授权印染整理模块"))
	for fieldname in ("license_id", "valid_from", "expires_on"):
		if not payload.get(fieldname):
			frappe.throw(_("许可证缺少字段：{0}").format(fieldname))
	return frappe._dict(payload)


def initialize_license_transition():
	if not frappe.db.get_global("dyeing_finishing_license_transition_started"):
		frappe.db.set_global("dyeing_finishing_license_transition_started", nowdate())


def _transition_status(today):
	started = getdate(frappe.db.get_global("dyeing_finishing_license_transition_started") or today)
	ends_on = started + timedelta(days=TRANSITION_DAYS)
	remaining = (ends_on - today).days
	if remaining >= 0:
		return frappe._dict(status="过渡期", indicator="orange", write_allowed=True, expires_on=ends_on,
			remaining_days=remaining, message=_("尚未安装正式许可证，过渡期剩余 {0} 天").format(remaining))
	return frappe._dict(status="已到期", indicator="red", write_allowed=False, expires_on=ends_on,
		remaining_days=remaining, message=_("印染整理过渡期已结束，现为只读状态，请安装有效许可证。"))


def get_status(update_clock=True):
	today = getdate(nowdate())
	last_verified = frappe.db.get_global("dyeing_finishing_license_last_verified_date")
	if last_verified and today < getdate(last_verified):
		return frappe._dict(status="时间异常", indicator="red", write_allowed=False, expires_on=None,
			remaining_days=None, message=_("检测到服务器日期回退，印染整理已进入只读状态。"))

	token = frappe.db.get_single_value(LICENSE_DOCTYPE, "license_token") if frappe.db.exists("DocType", LICENSE_DOCTYPE) else ""
	if not token:
		result = _transition_status(today)
	else:
		try:
			payload = decode_license(token)
		except frappe.ValidationError as error:
			return frappe._dict(status="无效", indicator="red", write_allowed=False, expires_on=None,
				remaining_days=None, message=str(error))
		valid_from, expires_on = getdate(payload.valid_from), getdate(payload.expires_on)
		remaining = (expires_on - today).days
		if today < valid_from:
			result = frappe._dict(status="未生效", indicator="orange", write_allowed=False, expires_on=expires_on,
				remaining_days=remaining, message=_("许可证将于 {0} 生效").format(valid_from))
		elif remaining >= 0:
			result = frappe._dict(status="有效", indicator="green", write_allowed=True, expires_on=expires_on,
				remaining_days=remaining, message=_("许可证有效，剩余 {0} 天").format(remaining))
		elif today <= expires_on + timedelta(days=GRACE_DAYS):
			grace_remaining = (expires_on + timedelta(days=GRACE_DAYS) - today).days
			result = frappe._dict(status="宽限期", indicator="orange", write_allowed=True, expires_on=expires_on,
				remaining_days=grace_remaining, message=_("许可证已到期，宽限期剩余 {0} 天").format(grace_remaining))
		else:
			result = frappe._dict(status="已到期", indicator="red", write_allowed=False, expires_on=expires_on,
				remaining_days=remaining, message=_("印染整理许可证已到期，现为只读状态。"))
		result.update({key: payload.get(key) for key in ("license_id", "customer", "site", "features")})

	if update_clock and result.write_allowed and str(last_verified or "") != str(today):
		frappe.db.set_global("dyeing_finishing_license_last_verified_date", str(today))
	return result


@frappe.whitelist()
def get_license_status():
	status = get_status()
	from dyeing_finishing.dyeing_finishing.settings import get_setting
	status["reminder_days"] = get_setting("license_reminder_days")
	return status


def enforce_document_write(doc, method=None):
	if getattr(frappe.flags, "in_migrate", False) or getattr(frappe.flags, "in_install", False):
		return
	if doc.doctype == LICENSE_DOCTYPE or getattr(doc.meta, "istable", False) or doc.meta.module != MODULE_NAME:
		return
	status = get_status()
	if not status.write_allowed:
		frappe.throw(_("{0} 不允许保存或提交印染整理单据。").format(status.message), title=_("印染整理授权限制"))
