package moe.honoka.npps4wrapper

import android.content.Context
import android.net.Uri
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

object FileOps {
    private const val PREFS = "npps4_wrapper_prefs"
    private const val KEY_DOWNLOAD_PROFILE = "download_profile"
    const val PROFILE_CN_ARCHIVE = "cn_archive"
    const val PROFILE_GL_ONLINE_DLAPI = "gl_online_dlapi"
    const val ONLINE_DLAPI_SERVER = "https://ll.sif.moe/npps4_dlapi/"

    fun getDownloadProfile(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_DOWNLOAD_PROFILE, PROFILE_CN_ARCHIVE) ?: PROFILE_CN_ARCHIVE

    fun setDownloadProfile(context: Context, profile: String) {
        val normalized = when (profile) {
            PROFILE_GL_ONLINE_DLAPI -> PROFILE_GL_ONLINE_DLAPI
            else -> PROFILE_CN_ARCHIVE
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_DOWNLOAD_PROFILE, normalized)
            .apply()
        rewriteDefaultConfig(context)
    }

    fun configureCnArchive(context: Context): String {
        setDownloadProfile(context, PROFILE_CN_ARCHIVE)
        return "已切换为国服本地 CDN 模式：download.backend=cn_archive。重启服务端后生效。"
    }

    fun configureGlOnlineDlapi(context: Context): String {
        setDownloadProfile(context, PROFILE_GL_ONLINE_DLAPI)
        return "已切换为国际服在线 DLAPI/CDN 模式：download.backend=n4dlapi，server=$ONLINE_DLAPI_SERVER。重启服务端后生效。"
    }

    fun ensureTemplate(context: Context) {
        val work = PythonBridge.workDir(context)
        work.mkdirs()
        File(work, "data").mkdirs()
        File(work, "static").mkdirs()
        File(work, "templates").mkdirs()
        File(work, "external").mkdirs()
        File(work, "npps4").mkdirs()
        // Do NOT create or modify the user-managed public CDN directory here.
        // On Android 11+ this may require MANAGE_EXTERNAL_STORAGE, and the raw
        // ZIP archives should remain read-only anyway. Only create app-owned
        // mutable directories.
        PythonBridge.exportsDir(context).mkdirs()
        val cfg = PythonBridge.configFile(context)
        // v4.48 rewrote config.toml on every start, silently discarding manual
        // archive/all unlock policies and every other operator edit. Create a
        // canonical file only when missing/broken; normal starts preserve it.
        cfg.parentFile?.mkdirs()
        val currentConfig = try { if (cfg.exists()) cfg.readText(Charsets.UTF_8) else "" } catch (_: Throwable) { "" }
        if (currentConfig.isBlank() || !currentConfig.contains("[download]")) {
            cfg.writeText(defaultConfig(context), Charsets.UTF_8)
        }
        val loginBonus = File(work, "external/login_bonus.py")
        val placeholder = "# Android wrapper placeholder. NPPS4 bundled defaults will be used after Python workspace preparation."
        if (!loginBonus.exists() || loginBonus.readText(Charsets.UTF_8).trim() == placeholder) {
            loginBonus.parentFile?.mkdirs()
            if (loginBonus.exists()) File(loginBonus.parentFile, "login_bonus.py.placeholder.bak").writeText(loginBonus.readText(Charsets.UTF_8), Charsets.UTF_8)
            loginBonus.writeText(defaultLoginBonusScript(), Charsets.UTF_8)
        }
        val serverData = PythonBridge.serverDataFile(context)
        if (!serverData.exists()) {
            serverData.parentFile?.mkdirs()
            serverData.writeText("{}\n", Charsets.UTF_8)
        }
        // Public CDN archives are user-managed and intentionally read-only.
        // Do not write README.txt or any marker files into that folder.
    }

    fun rewriteDefaultConfig(context: Context) {
        val cfg = PythonBridge.configFile(context)
        cfg.parentFile?.mkdirs()
        if (!cfg.exists() || cfg.readText(Charsets.UTF_8).isBlank()) {
            cfg.writeText(defaultConfig(context), Charsets.UTF_8)
            return
        }

        // Synchronize only values owned by the Wrapper UI. Everything else —
        // especially museum/archive unlock policies and user-edited hooks — is
        // preserved verbatim instead of being reset on every start/restart.
        val archives = PythonBridge.cnAndroidArchives(context).absolutePath.replace('\\', '/')
        val dbRoot = PythonBridge.dbRoot(context).absolutePath.replace('\\', '/')
        val profile = getDownloadProfile(context)
        val isCn = profile != PROFILE_GL_ONLINE_DLAPI
        var text = cfg.readText(Charsets.UTF_8)
        text = upsertTomlValue(text, "download", "backend", tomlString(if (isCn) "cn_archive" else "n4dlapi"), true)
        text = upsertTomlValue(text, "download.n4dlapi", "server", tomlString(ONLINE_DLAPI_SERVER), true)
        text = upsertTomlValue(text, "download.cn_archive", "android_archives", tomlString(archives), true)
        text = upsertTomlValue(text, "download.cn_archive", "db_root", tomlString(dbRoot), true)
        text = upsertTomlValue(text, "download.cn_archive", "application_version", tomlString("9.7.1"), false)
        text = upsertTomlValue(text, "download.cn_archive", "client_version", tomlString("97.4.6"), false)
        text = upsertTomlValue(text, "download.cn_archive", "android_server_info_override", tomlString(if (isCn) "cn_server_info_99_0_115.zip" else ""), true)

        val cnDefaults = linkedMapOf(
            "gl_overlay_enabled" to "true",
            "gl_overlay_server" to tomlString("https://ll.sif.moe/npps4_dlapi"),
            "gl_overlay_shared_key" to tomlString(""),
            "gl_overlay_cache" to tomlString(""),
            "gl_overlay_timeout" to "30",
            "gl_overlay_try_language_fallback" to "true",
            "gl_overlay_negative_ttl" to "300",
            "android_extra_update_packages" to "[]",
            "ios_extra_update_packages" to "[]",
            "archive_access_manifest" to tomlString("data/cn_update_overlays/archive_access_manifest.json"),
            "museum_unlock_policy" to tomlString("all"),
            "main_scenario_unlock_policy" to tomlString("normal"),
            "subscenario_unlock_policy" to tomlString("normal"),
            "live_unlock_policy" to tomlString("normal"),
            "album_catalog_unlock_policy" to tomlString("normal"),
        )
        cnDefaults.forEach { (key, value) ->
            text = upsertTomlValue(text, "download.cn_archive", key, value, false)
        }

        text = upsertTomlValue(text, "compat", "region", tomlString(if (isCn) "cn" else "global"), true)
        text = upsertTomlValue(text, "compat", "cn_main_headers", isCn.toString(), true)
        text = upsertTomlValue(text, "compat", "cn_autocreate_ghome_users", isCn.toString(), true)
        text = upsertTomlValue(text, "compat", "cn_wrappers", isCn.toString(), true)
        text = upsertTomlValue(text, "compat", "cn_optional_stubs", isCn.toString(), true)
        cfg.writeText(text, Charsets.UTF_8)
    }

    private fun tomlString(value: String): String =
        "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    private fun upsertTomlValue(
        source: String,
        section: String,
        key: String,
        value: String,
        replaceExisting: Boolean,
    ): String {
        val lines = source.replace("\r\n", "\n").split('\n').toMutableList()
        val sectionHeader = "[$section]"
        var sectionIndex = lines.indexOfFirst { it.trim() == sectionHeader }
        if (sectionIndex < 0) {
            while (lines.isNotEmpty() && lines.last().isBlank()) lines.removeAt(lines.lastIndex)
            if (lines.isNotEmpty()) lines.add("")
            lines.add(sectionHeader)
            lines.add("$key = $value")
            return lines.joinToString("\n").trimEnd() + "\n"
        }
        var sectionEnd = lines.size
        for (i in sectionIndex + 1 until lines.size) {
            val trimmed = lines[i].trim()
            if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
                sectionEnd = i
                break
            }
        }
        val keyRegex = Regex("^\\s*${Regex.escape(key)}\\s*=")
        val existing = (sectionIndex + 1 until sectionEnd).firstOrNull { keyRegex.containsMatchIn(lines[it]) }
        if (existing != null) {
            if (replaceExisting) lines[existing] = "$key = $value"
        } else {
            lines.add(sectionEnd, "$key = $value")
        }
        return lines.joinToString("\n").trimEnd() + "\n"
    }

    fun checkPublicPaths(context: Context): String {
        val base = PythonBridge.publicBase(context)
        val archives = PythonBridge.cnAndroidArchives(context)
        val db = PythonBridge.dbRoot(context)
        val lines = mutableListOf<String>()
        lines += "CDN ZIP 目录: ${base.absolutePath}"
        lines += "所有文件访问权限: ${if (android.os.Build.VERSION.SDK_INT < 30 || android.os.Environment.isExternalStorageManager()) "已授予/不需要" else "未授予"}"
        for (dir in listOf(base, archives, db)) {
            lines += "${dir.name.ifBlank { dir.absolutePath }}: exists=${dir.exists()} dir=${dir.isDirectory} canRead=${dir.canRead()} canWrite=${dir.canWrite()}"
        }
        lines += "CDN ZIP 目录写入测试: 已跳过（目录按只读处理；不会修改普通 ZIP 或 99_0_115.zip）"
        val zipCount = try { archives.listFiles { f -> f.isFile && f.name.endsWith(".zip", ignoreCase = true) }?.size ?: 0 } catch (_: Throwable) { -1 }
        val dbCount = try { db.listFiles { f -> f.isFile && (f.name.endsWith(".db_") || f.name.endsWith(".db")) }?.size ?: 0 } catch (_: Throwable) { -1 }
        lines += "CDN ZIP 数量: $zipCount"
        lines += "master DB 文件数量: $dbCount"
        lines += "99_0_115.zip: ${File(archives, "99_0_115.zip").exists()}"
        return lines.joinToString("\n")
    }

    fun exportWorkspaceToUri(context: Context, destUri: Uri) {
        val work = PythonBridge.workDir(context).canonicalFile
        context.contentResolver.openOutputStream(destUri)?.use { output ->
            ZipOutputStream(BufferedOutputStream(output)).use { zip ->
                zip.setLevel(6)
                // Only back up server-side mutable state: account/progress DB,
                // config, editable server data and external scripts. Do NOT include
                // the public CDN archive directory or master DB directory, because
                // those can be 10+ GB and are already stored as user-managed files.
                addDirToZip(zip, work, "workspace") { rel ->
                    shouldIncludeInStateBackup(rel)
                }
            }
        }
    }

    private fun defaultLoginBonusScript(): String = """from datetime import date


async def get_rewards(day: int, month: int, year: int, context):
    # Upstream NPPS4 default: cycle through G, friend points and Loveca.
    current = date(year, month, day)
    delta = current - date(2023, 1, 1)
    match delta.days % 3:
        case 0:
            return (3000, 3, 20000, None)
        case 1:
            return (3002, 2, 2500, None)
        case _:
            return (3001, 4, 1, None)
"""

    private fun defaultConfig(context: Context): String {
        val root = PythonBridge.workDir(context).absolutePath.replace('\\', '/')
        val archives = PythonBridge.cnAndroidArchives(context).absolutePath.replace('\\', '/')
        val dbRoot = PythonBridge.dbRoot(context).absolutePath.replace('\\', '/')
        return when (getDownloadProfile(context)) {
            PROFILE_GL_ONLINE_DLAPI -> defaultGlOnlineConfig(root, archives, dbRoot)
            else -> defaultCnArchiveConfig(root, archives, dbRoot)
        }
    }

    private fun commonConfigPrefix(root: String): String = """# Generated by NPPS4 Android Wrapper.
# Mutable workspace: $root

[main]
data_directory = "data"
secret_key = "Change this secret if you expose the server"
server_private_key = "default_server_key.pem"
server_private_key_password = ""
server_data = "npps4/server_data.json"
session_expiry = 259200
save_notes_list = false

[database]
url = "sqlite+aiosqlite:///data/main.sqlite3"
"""

    private fun commonGameConfig(): String = """
[game]
badwords = "external/badwords.py"
login_bonus = "external/login_bonus.py"
beatmaps = "external/beatmap.py"
live_unit_drop = "external/live_unit_drop.py"
live_box_drop = "external/live_box_drop.py"

[advanced]
base_xorpad = "eit4Ahph4aiX4ohmephuobei6SooX9xo"
application_key = "b6e6c940a93af2357ea3e0ace0b98afc"
consumer_key = "lovelive_test"
verify_xmc = true

[iex]
enable_export = true
enable_import = true
bypass_signature = false

[gameplay]
energy_multiplier = 1
love_multiplier = 1
secretbox_cost_multiplier = 1
"""

    private fun defaultCnArchiveConfig(root: String, archives: String, dbRoot: String): String {
        return commonConfigPrefix(root) + """
[download]
backend = "cn_archive"
send_patched_server_info = true

[download.n4dlapi]
server = "$ONLINE_DLAPI_SERVER"
shared_key = ""

[download.cn_archive]
android_archives = "$archives"
ios_archives = ""
android_extracted = ""
ios_extracted = ""
db_root = "$dbRoot"
application_version = "9.7.1"
client_version = "97.4.6"
update_package_type = 99
server_info_override = "99_0_115.zip"
android_server_info_override = "cn_server_info_99_0_115.zip"
ios_server_info_override = ""
gl_overlay_enabled = true
gl_overlay_server = "https://ll.sif.moe/npps4_dlapi"
gl_overlay_shared_key = ""
gl_overlay_cache = ""
gl_overlay_timeout = 30
gl_overlay_try_language_fallback = true
gl_overlay_negative_ttl = 300
android_extra_update_packages = []
ios_extra_update_packages = []
archive_access_manifest = "data/cn_update_overlays/archive_access_manifest.json"
museum_unlock_policy = "all"
main_scenario_unlock_policy = "normal"
subscenario_unlock_policy = "normal"
live_unlock_policy = "normal"
album_catalog_unlock_policy = "normal"

[compat]
region = "cn"
cn_main_headers = true
cn_autocreate_ghome_users = true
cn_wrappers = true
cn_optional_stubs = true
daily_rotation_timezone = "auto"
live_continue_loveca_cost = 1
""" + commonGameConfig()
    }

    private fun defaultGlOnlineConfig(root: String, archives: String, dbRoot: String): String {
        return commonConfigPrefix(root) + """
[download]
backend = "n4dlapi"
send_patched_server_info = true

[download.n4dlapi]
server = "$ONLINE_DLAPI_SERVER"
shared_key = ""

[download.cn_archive]
android_archives = "$archives"
ios_archives = ""
android_extracted = ""
ios_extracted = ""
db_root = "$dbRoot"
application_version = "9.7.1"
client_version = "97.4.6"
update_package_type = 99
server_info_override = "99_0_115.zip"
android_server_info_override = ""
ios_server_info_override = ""
gl_overlay_enabled = true
gl_overlay_server = "https://ll.sif.moe/npps4_dlapi"
gl_overlay_shared_key = ""
gl_overlay_cache = ""
gl_overlay_timeout = 30
gl_overlay_try_language_fallback = true
gl_overlay_negative_ttl = 300
android_extra_update_packages = []
ios_extra_update_packages = []
archive_access_manifest = "data/cn_update_overlays/archive_access_manifest.json"
museum_unlock_policy = "all"
main_scenario_unlock_policy = "normal"
subscenario_unlock_policy = "normal"
live_unlock_policy = "normal"
album_catalog_unlock_policy = "normal"

[compat]
region = "global"
cn_main_headers = false
cn_autocreate_ghome_users = false
cn_wrappers = false
cn_optional_stubs = false
daily_rotation_timezone = "auto"
live_continue_loveca_cost = 1
""" + commonGameConfig()
    }

    private fun addDirToZip(zip: ZipOutputStream, root: File, prefix: String, include: (String) -> Boolean) {
        root.walkTopDown().forEach { file ->
            if (file == root || file.isDirectory) return@forEach
            val rel = file.relativeTo(root).invariantSeparatorsPath
            if (!include(rel)) return@forEach
            val entry = ZipEntry("$prefix/$rel")
            zip.putNextEntry(entry)
            FileInputStream(file).use { it.copyTo(zip) }
            zip.closeEntry()
        }
    }

    fun importWorkspaceFromUri(context: Context, srcUri: Uri) {
        val work = PythonBridge.workDir(context).canonicalFile
        work.mkdirs()
        context.contentResolver.openInputStream(srcUri)?.use { input ->
            ZipInputStream(BufferedInputStream(input)).use { zip ->
                while (true) {
                    val entry = zip.nextEntry ?: break
                    if (entry.isDirectory) {
                        zip.closeEntry()
                        continue
                    }
                    val parts = entry.name.split('/', limit = 2)
                    if (parts.size != 2 || parts[0] != "workspace") {
                        zip.closeEntry()
                        continue
                    }
                    if (!shouldIncludeInStateBackup(parts[1])) {
                        zip.closeEntry()
                        continue
                    }
                    val out = File(work, parts[1]).canonicalFile
                    if (!out.path.startsWith(work.canonicalPath)) throw SecurityException("Zip slip: ${entry.name}")
                    out.parentFile?.mkdirs()
                    FileOutputStream(out).use { zip.copyTo(it) }
                    zip.closeEntry()
                }
            }
        }
    }

    private fun shouldIncludeInStateBackup(rel: String): Boolean {
        val r = rel.replace('\\', '/')
        if (r.isBlank()) return false
        if (r.startsWith("exports/")) return false
        if (r.startsWith("cn/")) return false
        if (r.startsWith("beatmaps/")) return false
        if (r.startsWith("data/db/")) return false
        if (r.endsWith(".zip", ignoreCase = true)) return false
        return r == "config.toml" ||
            r == "default_server_key.pem" ||
            r == "alembic.ini" ||
            r.startsWith("data/") ||
            r.startsWith("external/") ||
            r.startsWith("npps4/")
    }


    fun createAppSpecificPublicTemplate(context: Context): String {
        val base = File(context.getExternalFilesDir(null), "public_cdn")
        val archives = File(base, "list_CN_Android")
        val db = File(base, "db")
        archives.mkdirs()
        db.mkdirs()
        File(base, "README.txt").writeText(
            """
NPPS4 Wrapper 应用专属直读目录

如果系统不给“所有文件访问权限”，可以把国服 ZIP 放到：
  ${archives.absolutePath}

这些 ZIP 仍然按只读处理，Wrapper 不会修改。

也可以只把完整 CDN 目录移动到这里，避免复制两份。
""".trimIndent(), Charsets.UTF_8
        )
        PythonBridge.setPublicBase(context, base)
        rewriteDefaultConfig(context)
        return "已切换到应用专属直读目录：${base.absolutePath}\nCN archives: ${archives.absolutePath}\n无需所有文件访问权限，但你需要把数据包放/移动到这里。"
    }

    fun defaultBackupName(): String {
        val ts = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        return "NPPS4-Android-StateBackup-$ts.zip"
    }
}
