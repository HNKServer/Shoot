from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
import hashlib
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

import apksigtool
from apksigcopier import zip_data

OLD_PACKAGE = "com.npdep.wrapperthingen"
NEW_PACKAGE = "moe.honoka.npps4glclient"
OLD_SETTINGS_URL = b"http://127.0.0.1:51376"
NEW_SETTINGS_URL = b"http://127.0.0.1:8080/"  # same byte length; URL semantics are 127.0.0.1:8080
OLD_SERVER_BASE = "http://sif.ethanthesleepy.one"
NEW_SERVER_BASE = "http://127.0.0.1:8080"
ALG_ID = 0x0103  # RSA PKCS#1 v1.5 with SHA-256, APK chunked digest
V2_ID = apksigtool.APK_SIGNATURE_SCHEME_V2_BLOCK_ID
MAGIC = b"APK Sig Block 42"


def lp(data: bytes) -> bytes:
    return struct.pack("<I", len(data)) + data


def repair_dex_header(data: bytes) -> bytes:
    if not data.startswith(b"dex\n"):
        raise ValueError("not a DEX file")
    out = bytearray(data)
    out[12:32] = hashlib.sha1(out[32:]).digest()
    out[8:12] = struct.pack("<I", zlib.adler32(out[12:]) & 0xFFFFFFFF)
    return bytes(out)


def clone_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    out = zipfile.ZipInfo(info.filename, info.date_time)
    out.compress_type = info.compress_type
    out.comment = info.comment
    out.extra = info.extra
    out.internal_attr = info.internal_attr
    out.external_attr = info.external_attr
    out.create_system = info.create_system
    out.create_version = info.create_version
    out.extract_version = info.extract_version
    out.flag_bits = info.flag_bits & ~0x08
    return out


def replace_package_resource(data: bytes, restore_activity: bool = False) -> bytes:
    old8 = OLD_PACKAGE.encode()
    new8 = NEW_PACKAGE.encode()
    old16 = OLD_PACKAGE.encode("utf-16le")
    new16 = NEW_PACKAGE.encode("utf-16le")
    out = data.replace(old8, new8).replace(old16, new16)
    if restore_activity:
        old_cls8 = f"{OLD_PACKAGE}.ServerSettingActivity".encode()
        new_cls8 = f"{NEW_PACKAGE}.ServerSettingActivity".encode()
        old_cls16 = f"{OLD_PACKAGE}.ServerSettingActivity".encode("utf-16le")
        new_cls16 = f"{NEW_PACKAGE}.ServerSettingActivity".encode("utf-16le")
        out = out.replace(new_cls8, old_cls8).replace(new_cls16, old_cls16)
    return out


def patch_urls(obj):
    if isinstance(obj, str):
        return NEW_SERVER_BASE + obj[len(OLD_SERVER_BASE):] if obj.startswith(OLD_SERVER_BASE) else obj
    if isinstance(obj, list):
        return [patch_urls(x) for x in obj]
    if isinstance(obj, dict):
        return {k: patch_urls(v) for k, v in obj.items()}
    return obj


def patch_app_assets(data: bytes, python_root: Path) -> tuple[bytes, dict]:
    sys.path.insert(0, str(python_root))
    from npps4.tools import honky_file

    src = io.BytesIO(data)
    dst = io.BytesIO()
    report = {}
    with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(dst, "w", allowZip64=True) as zout:
        for info in zin.infolist():
            payload = zin.read(info.filename)
            if info.filename == "config/server_info.json":
                plain, meta = honky_file.decrypt_v3(payload, info.filename, "jp")
                original = json.loads(plain.decode("utf-8"))
                patched = patch_urls(original)
                patched["domain"] = NEW_SERVER_BASE
                new_plain = json.dumps(patched, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                payload = honky_file.encrypt_v3(new_plain, meta, info.filename)
                roundtrip, check_meta = honky_file.decrypt_v3(payload, info.filename, "jp")
                if json.loads(roundtrip.decode("utf-8")) != patched:
                    raise RuntimeError("Honky v3 server_info round-trip failed")
                report = {
                    "honky_region": check_meta.region,
                    "honky_version": 3,
                    "honky_name_sum": check_meta.name_sum,
                    "old_domain": original.get("domain"),
                    "new_domain": patched.get("domain"),
                    "api_uri": patched.get("api_uri", {}),
                }
            zout.writestr(clone_info(info), payload)
    if not report:
        raise RuntimeError("config/server_info.json not found in AppAssets.zip")
    return dst.getvalue(), report


def create_signing_material(directory: Path, password: bytes):
    directory.mkdir(parents=True, exist_ok=True)
    key_pem = directory / "npps4-gl-test-key.pem"
    cert_pem = directory / "npps4-gl-test-cert.pem"
    p12_path = directory / "npps4-gl-test.p12"
    if key_pem.exists() and cert_pem.exists():
        key = serialization.load_pem_private_key(key_pem.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(cert_pem.read_bytes())
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = dt.datetime.now(dt.timezone.utc)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "JP"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NPPS4 Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NPPS4 GL Local Test Client"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )
        key_pem.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        cert_pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    p12_path.write_bytes(pkcs12.serialize_key_and_certificates(
        name=b"npps4gltest", key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    ))
    return key, cert, p12_path


def build_unsigned(source: Path, output: Path, python_root: Path) -> dict:
    report = {"patched_entries": {}, "source": str(source)}
    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(output, "w", allowZip64=True) as zout:
        for info in zin.infolist():
            if info.filename.upper().startswith("META-INF/"):
                continue
            data = zin.read(info.filename)
            before = data
            if info.filename == "AndroidManifest.xml":
                data = replace_package_resource(data, restore_activity=True)
            elif info.filename in {"resources.arsc", "res/xml/shortcuts.xml", "res/xml-v22/shortcuts.xml"}:
                data = replace_package_resource(data, restore_activity=True)
            elif info.filename == "assets/AppAssets.zip":
                data, server_report = patch_app_assets(data, python_root)
                report["server_info"] = server_report
            elif info.filename.endswith(".dex") and OLD_SETTINGS_URL in data:
                count = data.count(OLD_SETTINGS_URL)
                data = data.replace(OLD_SETTINGS_URL, NEW_SETTINGS_URL)
                data = repair_dex_header(data)
                report["settings_url_dex"] = {"entry": info.filename, "replacements": count, "url": NEW_SETTINGS_URL.decode()}
            if data != before:
                report["patched_entries"][info.filename] = {
                    "old_sha256": hashlib.sha256(before).hexdigest(),
                    "new_sha256": hashlib.sha256(data).hexdigest(),
                    "old_size": len(before), "new_size": len(data),
                }
            zout.writestr(clone_info(info), data)
    return report


def jarsign(unsigned: Path, signed_v1: Path, p12_path: Path, password: str):
    cmd = [
        "jarsigner", "-keystore", str(p12_path), "-storetype", "PKCS12",
        "-storepass", password, "-keypass", password,
        "-sigalg", "SHA256withRSA", "-digestalg", "SHA-256",
        "-signedjar", str(signed_v1), str(unsigned), "npps4gltest",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def write_aligned_entry(zout: zipfile.ZipFile, info: zipfile.ZipInfo, data: bytes) -> None:
    out = clone_info(info)
    # Python's ZipInfo only exposes central-directory extras.  The original APK
    # used local-header-only zipalign padding, so compute fresh padding here.
    out.extra = b""
    if out.compress_type == zipfile.ZIP_STORED:
        alignment = 16384 if out.filename.endswith(".so") else 4
        name_len = len(out.filename.encode("utf-8"))
        current = zout.fp.tell() if zout.fp is not None else 0
        base = current + 30 + name_len
        pad = (-base) % alignment
        if pad and pad < 4:
            pad += alignment
        if pad:
            out.extra = struct.pack("<HH", 0xD935, pad - 4) + (b"\x00" * (pad - 4))
    zout.writestr(out, data)


def rebuild_aligned_v1(unsigned: Path, jarsigned: Path, output: Path) -> None:
    with zipfile.ZipFile(unsigned, "r") as original, zipfile.ZipFile(jarsigned, "r") as signed, zipfile.ZipFile(output, "w", allowZip64=True) as zout:
        # Keep the exact jarsigner-generated v1 files, then add the patched APK
        # entries.  V1 signatures cover entry contents, not local offsets.
        for info in signed.infolist():
            if info.filename.upper().startswith("META-INF/"):
                write_aligned_entry(zout, info, signed.read(info.filename))
        for info in original.infolist():
            if not info.filename.upper().startswith("META-INF/"):
                write_aligned_entry(zout, info, original.read(info.filename))


def alignment_report(apk: Path) -> dict:
    bad = []
    stored = 0
    with zipfile.ZipFile(apk, "r") as z, open(apk, "rb") as fh:
        for info in z.infolist():
            if info.compress_type != zipfile.ZIP_STORED:
                continue
            stored += 1
            fh.seek(info.header_offset)
            header = fh.read(30)
            if len(header) != 30 or header[:4] != b"PK\x03\x04":
                raise RuntimeError(f"invalid local header for {info.filename}")
            name_len, extra_len = struct.unpack("<HH", header[26:30])
            data_offset = info.header_offset + 30 + name_len + extra_len
            required = 16384 if info.filename.endswith(".so") else 4
            if data_offset % required:
                bad.append({"entry": info.filename, "offset": data_offset, "required": required})
    return {"stored_entries": stored, "misaligned": bad}


def make_v2_block(apk_path: Path, private_key, cert: x509.Certificate) -> bytes:
    cd_offset = zip_data(str(apk_path)).cd_offset
    digest = apksigtool.apk_digest_chunked(str(apk_path), cd_offset, hashlib.sha256)
    digest_record = lp(struct.pack("<I", ALG_ID) + lp(digest))
    digests = digest_record
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    certs = lp(cert_der)
    attrs = b""
    signed_data = lp(digests) + lp(certs) + lp(attrs)
    signature = private_key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    signature_record = lp(struct.pack("<I", ALG_ID) + lp(signature))
    signatures = signature_record
    pubkey = private_key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    signer = lp(signed_data) + lp(signatures) + lp(pubkey)
    v2_value = lp(lp(signer))
    pair = struct.pack("<Q", 4 + len(v2_value)) + struct.pack("<I", V2_ID) + v2_value
    size = len(pair) + 24
    return struct.pack("<Q", size) + pair + struct.pack("<Q", size) + MAGIC


def add_v2_signature(v1_apk: Path, final_apk: Path, private_key, cert):
    raw = v1_apk.read_bytes()
    zd = zip_data(str(v1_apk))
    block = make_v2_block(v1_apk, private_key, cert)
    prefix = raw[:zd.cd_offset]
    tail = bytearray(raw[zd.cd_offset:])
    rel_eocd = zd.eocd_offset - zd.cd_offset
    new_cd_offset = zd.cd_offset + len(block)
    tail[rel_eocd + 16:rel_eocd + 20] = struct.pack("<I", new_cd_offset)
    final_apk.write_bytes(prefix + block + tail)


def verify_final(apk: Path, python_root: Path) -> dict:
    v1 = subprocess.run(["jarsigner", "-verify", "-strict", str(apk)], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # jarsigner returns 4 for a correctly verified self-signed test certificate.
    # Treat it as valid only when the tool explicitly says the JAR verified and
    # does not report unsigned or tampered entries.
    if v1.returncode not in (0, 4) or "jar verified" not in v1.stdout.lower() or "unsigned entries" in v1.stdout.lower():
        raise RuntimeError("v1 signature verification failed:\n" + v1.stdout[-4000:])
    subprocess.run(["apksigtool", "verify", str(apk)], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # Lightweight content verification without depending on a device.
    from androguard.core.apk import APK
    from loguru import logger
    logger.remove()
    parsed = APK(str(apk))
    if parsed.get_package() != NEW_PACKAGE:
        raise RuntimeError(f"package verification failed: {parsed.get_package()}")
    if parsed.get_main_activity() != "klb.android.GameEngine.GameEngineActivity":
        raise RuntimeError("main activity changed unexpectedly")
    activities = parsed.get_activities()
    if f"{OLD_PACKAGE}.ServerSettingActivity" not in activities:
        raise RuntimeError("settings Activity class path was not preserved")

    with zipfile.ZipFile(apk) as outer:
        app_assets = outer.read("assets/AppAssets.zip")
        dex = outer.read("classes5.dex")
        manifest = outer.read("AndroidManifest.xml")
        shortcuts = outer.read("res/xml/shortcuts.xml") + outer.read("res/xml-v22/shortcuts.xml")
    sys.path.insert(0, str(python_root))
    from npps4.tools import honky_file
    with zipfile.ZipFile(io.BytesIO(app_assets)) as nested:
        encrypted = nested.read("config/server_info.json")
    plain, meta = honky_file.decrypt_v3(encrypted, "config/server_info.json", "jp")
    server = json.loads(plain.decode("utf-8"))
    if server.get("domain") != NEW_SERVER_BASE:
        raise RuntimeError("server_info domain verification failed")
    if OLD_SERVER_BASE.encode() in plain:
        raise RuntimeError("old server URL remains in server_info")
    if OLD_SETTINGS_URL in dex or NEW_SETTINGS_URL not in dex:
        raise RuntimeError("settings-screen URL verification failed")
    if NEW_PACKAGE.encode("utf-16le") not in manifest:
        raise RuntimeError("new package missing from binary Manifest")
    if NEW_PACKAGE.encode() not in shortcuts:
        raise RuntimeError("new targetPackage missing from shortcuts")
    sb_offset, block = apksigtool.extract_v2_sig(str(apk))
    parsed_block = apksigtool.parse_apk_signing_block(block, str(apk))
    if not any(p.id == V2_ID and getattr(p.value, "verified", False) for p in parsed_block.pairs):
        raise RuntimeError("APK v2 signature block did not verify")
    aligned = alignment_report(apk)
    if aligned["misaligned"]:
        raise RuntimeError(f"APK contains misaligned stored entries: {aligned['misaligned'][:5]}")
    return {
        "package": parsed.get_package(),
        "main_activity": parsed.get_main_activity(),
        "settings_activity": f"{OLD_PACKAGE}.ServerSettingActivity",
        "server_domain": server.get("domain"),
        "settings_default_url": NEW_SETTINGS_URL.decode(),
        "honky": {"region": meta.region, "version": 3, "name_sum": meta.name_sum},
        "v1_verified": True,
        "v2_verified": True,
        "v2_signing_block_offset": sb_offset,
        "zip_alignment": aligned,
        "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
        "size": apk.stat().st_size,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--python-root", required=True, type=Path)
    ap.add_argument("--work", required=True, type=Path)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    unsigned = args.work / "gl-client-unsigned.apk"
    v1_unaligned = args.work / "gl-client-v1-unaligned.apk"
    v1 = args.work / "gl-client-v1-aligned.apk"
    password = "npps4gltest2026"
    report = build_unsigned(args.input, unsigned, args.python_root)
    key, cert, p12_path = create_signing_material(args.work / "signing", password.encode())
    jarsign(unsigned, v1_unaligned, p12_path, password)
    rebuild_aligned_v1(unsigned, v1_unaligned, v1)
    add_v2_signature(v1, args.output, key, cert)
    report["verification"] = verify_final(args.output, args.python_root)
    report["signing"] = {
        "keystore": str(p12_path), "alias": "npps4gltest", "password": password,
        "certificate_sha256": cert.fingerprint(hashes.SHA256()).hex(),
    }
    (args.work / "GL_TEST_APK_BUILD_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["verification"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
