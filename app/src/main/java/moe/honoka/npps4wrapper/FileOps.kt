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
    private const val KEY_CN_ENABLED = "cn_enabled"
    private const val KEY_GL_ENABLED = "gl_enabled"
    private const val KEY_CN_BACKEND = "cn_backend"
    private const val KEY_GL_BACKEND = "gl_backend"
    private const val KEY_DEFAULT_PROFILE = "default_profile"
    private const val KEY_CN_ONLINE_SERVER = "cn_online_server"
    private const val KEY_GL_ONLINE_SERVER = "gl_online_server"
    private const val KEY_DUAL_PROFILE_PREFS_MIGRATED = "dual_profile_prefs_migrated_v2"
    private const val KEY_LEGACY_DOWNLOAD_PROFILE = "download_profile"

    const val PROFILE_CN = "cn"
    const val PROFILE_GL = "gl"
    const val BACKEND_LOCAL = "local"
    const val BACKEND_ONLINE = "online"
    const val MODE_DISABLED = "disabled"
    const val MODE_LOCAL = "local"
    const val MODE_ONLINE = "online"
    const val ONLINE_DLAPI_SERVER = "https://ll.sif.moe/npps4_dlapi/"

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /**
     * Migrate the old mutually-exclusive GUI preference once.  The old value
     * selected either CN-local or GL-online for the whole process; it must not
     * remain authoritative after CN and GL become independent Profiles.
     *
     * Existing Stage-3 per-profile values are preserved.  A clean install
     * enables both Profiles (CN local + GL online), while an upgrade directly
     * from v4.60 preserves the one mode which the operator had selected and
     * leaves the other Profile available but disabled until explicitly chosen.
     */
    private fun ensureDualProfilePreferences(context: Context) {
        val p = prefs(context)
        if (p.getBoolean(KEY_DUAL_PROFILE_PREFS_MIGRATED, false)) return
        val editor = p.edit()
        val hasNewValues = p.contains(KEY_CN_ENABLED) || p.contains(KEY_GL_ENABLED) ||
            p.contains(KEY_CN_BACKEND) || p.contains(KEY_GL_BACKEND)
        if (!hasNewValues) {
            val legacy = p.getString(KEY_LEGACY_DOWNLOAD_PROFILE, null)
            if (legacy == "gl_online_dlapi") {
                editor.putBoolean(KEY_CN_ENABLED, false)
                editor.putString(KEY_CN_BACKEND, BACKEND_LOCAL)
                editor.putBoolean(KEY_GL_ENABLED, true)
                editor.putString(KEY_GL_BACKEND, BACKEND_ONLINE)
                editor.putString(KEY_DEFAULT_PROFILE, PROFILE_GL)
            } else if (legacy == "cn_archive") {
                editor.putBoolean(KEY_CN_ENABLED, true)
                editor.putString(KEY_CN_BACKEND, BACKEND_LOCAL)
                editor.putBoolean(KEY_GL_ENABLED, false)
                editor.putString(KEY_GL_BACKEND, BACKEND_ONLINE)
                editor.putString(KEY_DEFAULT_PROFILE, PROFILE_CN)
            } else {
                editor.putBoolean(KEY_CN_ENABLED, true)
                editor.putString(KEY_CN_BACKEND, BACKEND_LOCAL)
                editor.putBoolean(KEY_GL_ENABLED, true)
                editor.putString(KEY_GL_BACKEND, BACKEND_ONLINE)
                editor.putString(KEY_DEFAULT_PROFILE, PROFILE_CN)
            }
        }
        editor.remove(KEY_LEGACY_DOWNLOAD_PROFILE)
        editor.putBoolean(KEY_DUAL_PROFILE_PREFS_MIGRATED, true)
        editor.apply()
    }

    fun isProfileEnabled(context: Context, profile: String): Boolean {
        ensureDualProfilePreferences(context)
        return when (profile) {
            PROFILE_GL -> prefs(context).getBoolean(KEY_GL_ENABLED, true)
            else -> prefs(context).getBoolean(KEY_CN_ENABLED, true)
        }
    }

    fun getProfileBackend(context: Context, profile: String): String {
        ensureDualProfilePreferences(context)
        val key = if (profile == PROFILE_GL) KEY_GL_BACKEND else KEY_CN_BACKEND
        val default = if (profile == PROFILE_GL) BACKEND_ONLINE else BACKEND_LOCAL
        return when (prefs(context).getString(key, default)) {
            BACKEND_ONLINE -> BACKEND_ONLINE
            else -> BACKEND_LOCAL
        }
    }

    fun getProfileMode(context: Context, profile: String): String {
        if (!isProfileEnabled(context, profile)) return MODE_DISABLED
        return if (getProfileBackend(context, profile) == BACKEND_ONLINE) MODE_ONLINE else MODE_LOCAL
    }

    fun getDefaultProfile(context: Context): String {
        ensureDualProfilePreferences(context)
        val selected = prefs(context).getString(KEY_DEFAULT_PROFILE, PROFILE_CN) ?: PROFILE_CN
        if (selected == PROFILE_GL && isProfileEnabled(context, PROFILE_GL)) return PROFILE_GL
        if (isProfileEnabled(context, PROFILE_CN)) return PROFILE_CN
        return PROFILE_GL
    }

    fun getOnlineServer(context: Context, profile: String): String {
        ensureDualProfilePreferences(context)
        val key = if (profile == PROFILE_GL) KEY_GL_ONLINE_SERVER else KEY_CN_ONLINE_SERVER
        val default = if (profile == PROFILE_GL) ONLINE_DLAPI_SERVER else ""
        return prefs(context).getString(key, default) ?: default
    }

    fun setProfileMode(context: Context, profile: String, mode: String): String {
        ensureDualProfilePreferences(context)
        val normalized = when (mode) {
            MODE_DISABLED -> MODE_DISABLED
            MODE_ONLINE -> MODE_ONLINE
            else -> MODE_LOCAL
        }
        val other = if (profile == PROFILE_CN) PROFILE_GL else PROFILE_CN
        if (normalized == MODE_DISABLED && !isProfileEnabled(context, other)) {
            return "CN 与 GL 不能同时禁用；请先启用另一个 Profile。"
        }
        val enabledKey = if (profile == PROFILE_GL) KEY_GL_ENABLED else KEY_CN_ENABLED
        val backendKey = if (profile == PROFILE_GL) KEY_GL_BACKEND else KEY_CN_BACKEND
        val editor = prefs(context).edit()
        editor.putBoolean(enabledKey, normalized != MODE_DISABLED)
        if (normalized != MODE_DISABLED) {
            editor.putString(backendKey, if (normalized == MODE_ONLINE) BACKEND_ONLINE else BACKEND_LOCAL)
        }
        if (normalized == MODE_DISABLED && getDefaultProfile(context) == profile) {
            editor.putString(KEY_DEFAULT_PROFILE, other)
        }
        editor.apply()
        rewriteDefaultConfig(context)
        val description = when (normalized) {
            MODE_DISABLED -> "禁用"
            MODE_ONLINE -> "在线 n4dlapi"
            else -> "本地数据"
        }
        return "${profile.uppercase(Locale.US)} 已设为$description；CN 与 GL 的设置互不覆盖，重启服务端后生效。"
    }

    fun setDefaultProfile(context: Context, profile: String): String {
        ensureDualProfilePreferences(context)
        val normalized = if (profile == PROFILE_GL) PROFILE_GL else PROFILE_CN
        if (!isProfileEnabled(context, normalized)) {
            return "${normalized.uppercase(Locale.US)} 当前未启用，不能设为默认 Profile。"
        }
        prefs(context).edit().putString(KEY_DEFAULT_PROFILE, normalized).apply()
        rewriteDefaultConfig(context)
        return "默认 Profile 已设为 ${normalized.uppercase(Locale.US)}；只影响无法自动识别的登录前请求。"
    }

    fun saveProfileOptions(
        context: Context,
        cnOnlineServer: String,
        glArchiveRoot: String,
        glOnlineServer: String,
    ): String {
        val cleanCn = cnOnlineServer.trim().trimEnd('/')
        val cleanGl = glOnlineServer.trim().trimEnd('/')
        prefs(context).edit()
            .putString(KEY_CN_ONLINE_SERVER, cleanCn)
            .putString(KEY_GL_ONLINE_SERVER, cleanGl)
            .apply()
        if (glArchiveRoot.isNotBlank()) PythonBridge.setGlArchiveRoot(context, File(glArchiveRoot.trim()))
        rewriteDefaultConfig(context)
        return "双 Profile 配置已保存。CN 与 GL 的启用状态、下载源、路径和 CDN 地址互不覆盖；重启服务端后生效。"
    }

    fun downloadSummary(context: Context): String {
        fun one(profile: String): String {
            if (!isProfileEnabled(context, profile)) return "${profile.uppercase(Locale.US)}：禁用"
            val backend = getProfileBackend(context, profile)
            val detail = when {
                profile == PROFILE_CN && backend == BACKEND_LOCAL -> "本地 cn_archive → ${PythonBridge.cnAndroidArchives(context).absolutePath}"
                profile == PROFILE_GL && backend == BACKEND_LOCAL -> "本地 internal → ${PythonBridge.glArchiveRoot(context).absolutePath}"
                else -> "在线 n4dlapi → ${getOnlineServer(context, profile).ifBlank { "未填写" }}"
            }
            return "${profile.uppercase(Locale.US)}：$detail"
        }
        return listOf(
            one(PROFILE_CN),
            one(PROFILE_GL),
            "默认 Profile：${getDefaultProfile(context).uppercase(Locale.US)}",
        ).joinToString("\n")
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
        // Editable configuration is user-owned after first creation. Create a
        // default only when the file is absent; blank, malformed, or manually
        // changed files are left untouched and reported by normal startup.
        cfg.parentFile?.mkdirs()
        if (!cfg.exists()) {
            cfg.writeText(defaultConfig(context), Charsets.UTF_8)
        }
        val loginBonus = File(work, "external/login_bonus.py")
        if (!loginBonus.exists()) {
            loginBonus.parentFile?.mkdirs()
            loginBonus.writeText(defaultLoginBonusScript(), Charsets.UTF_8)
        }
        // Do not create an empty server_data.json here. Python workspace
        // preparation copies the bundled full default only when the file is
        // missing. Once created, the user's exact file is never merged/reset.
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

        val cnArchives = PythonBridge.cnAndroidArchives(context).absolutePath.replace('\\', '/')
        val glArchive = PythonBridge.glArchiveRoot(context).absolutePath.replace('\\', '/')
        val dbRoot = PythonBridge.dbRoot(context).absolutePath.replace('\\', '/')
        val cnEnabled = isProfileEnabled(context, PROFILE_CN)
        val glEnabled = isProfileEnabled(context, PROFILE_GL)
        val cnBackend = if (getProfileBackend(context, PROFILE_CN) == BACKEND_LOCAL) "cn_archive" else "n4dlapi"
        val glBackend = if (getProfileBackend(context, PROFILE_GL) == BACKEND_LOCAL) "internal" else "n4dlapi"
        var text = cfg.readText(Charsets.UTF_8)

        // Disable the v4.60 process-global selector.  The profile registry below
        // is authoritative; the legacy key remains blank only for old parsers.
        text = upsertTomlValue(text, "download", "backend", tomlString(""), true)
        text = upsertTomlValue(text, "download", "default_profile", tomlString(getDefaultProfile(context)), true)

        text = upsertTomlValue(text, "download.profiles.cn", "enabled", cnEnabled.toString(), true)
        text = upsertTomlValue(text, "download.profiles.cn", "backend", tomlString(cnBackend), true)
        text = upsertTomlValue(text, "download.profiles.cn", "museum_unlock_policy", tomlString("all"), false)
        text = upsertTomlValue(text, "download.profiles.cn", "send_patched_server_info", "true", true)
        text = upsertTomlValue(text, "download.profiles.cn.n4dlapi", "server", tomlString(getOnlineServer(context, PROFILE_CN)), true)
        text = upsertTomlValue(text, "download.profiles.cn.n4dlapi", "shared_key", tomlString(""), false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "android_archives", tomlString(cnArchives), true)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "ios_archives", tomlString(""), false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "android_extracted", tomlString(""), false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "ios_extracted", tomlString(""), false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "db_root", tomlString(dbRoot), true)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "application_version", tomlString("9.7.1"), false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "client_version", tomlString("97.4.6"), false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "update_package_type", "99", false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "server_info_override", tomlString("99_0_115.zip"), false)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "android_server_info_override", tomlString("cn_server_info_99_0_115.zip"), true)
        text = upsertTomlValue(text, "download.profiles.cn.cn_archive", "ios_server_info_override", tomlString(""), false)

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
            "main_scenario_unlock_policy" to tomlString("normal"),
            "subscenario_unlock_policy" to tomlString("normal"),
            "live_unlock_policy" to tomlString("normal"),
            "album_catalog_unlock_policy" to tomlString("normal"),
        )
        cnDefaults.forEach { (key, value) ->
            text = upsertTomlValue(text, "download.profiles.cn.cn_archive", key, value, false)
        }

        text = upsertTomlValue(text, "download.profiles.gl", "enabled", glEnabled.toString(), true)
        text = upsertTomlValue(text, "download.profiles.gl", "backend", tomlString(glBackend), true)
        text = upsertTomlValue(text, "download.profiles.gl", "museum_unlock_policy", tomlString("all"), false)
        text = upsertTomlValue(text, "download.profiles.gl", "send_patched_server_info", "true", true)
        text = upsertTomlValue(text, "download.profiles.gl.internal", "archive_root", tomlString(glArchive), true)
        text = upsertTomlValue(text, "download.profiles.gl.n4dlapi", "server", tomlString(getOnlineServer(context, PROFILE_GL)), true)
        text = upsertTomlValue(text, "download.profiles.gl.n4dlapi", "shared_key", tomlString(""), false)
        text = upsertTomlValue(text, "download.profiles.gl.none", "client_version", tomlString("59.4"), false)

        // CN compatibility options are now request/profile-gated.  They may stay
        // enabled globally without affecting GL sessions.
        text = upsertTomlValue(text, "compat", "region", tomlString("dual"), true)
        text = upsertTomlValue(text, "compat", "cn_main_headers", "true", true)
        text = upsertTomlValue(text, "compat", "cn_autocreate_ghome_users", "true", true)
        text = upsertTomlValue(text, "compat", "cn_wrappers", "true", true)
        text = upsertTomlValue(text, "compat", "cn_optional_stubs", "false", true)
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
        val glArchive = PythonBridge.glArchiveRoot(context)
        val db = PythonBridge.dbRoot(context)
        val lines = mutableListOf<String>()
        lines += "CDN ZIP 目录: ${base.absolutePath}"
        lines += "所有文件访问权限: ${if (android.os.Build.VERSION.SDK_INT < 30 || android.os.Environment.isExternalStorageManager()) "已授予/不需要" else "未授予"}"
        lines += "GL 本地 archive-root: ${glArchive.absolutePath}"
        for (dir in listOf(base, archives, glArchive, db)) {
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
        val cnArchives = PythonBridge.cnAndroidArchives(context).absolutePath.replace('\\', '/')
        val glArchive = PythonBridge.glArchiveRoot(context).absolutePath.replace('\\', '/')
        val dbRoot = PythonBridge.dbRoot(context).absolutePath.replace('\\', '/')
        val cnBackend = if (getProfileBackend(context, PROFILE_CN) == BACKEND_LOCAL) "cn_archive" else "n4dlapi"
        val glBackend = if (getProfileBackend(context, PROFILE_GL) == BACKEND_LOCAL) "internal" else "n4dlapi"
        return commonConfigPrefix(root) + """
[download]
backend = ""
default_profile = "${getDefaultProfile(context)}"

[download.profiles.cn]
enabled = ${isProfileEnabled(context, PROFILE_CN)}
backend = "$cnBackend"
museum_unlock_policy = "all"
send_patched_server_info = true

[download.profiles.cn.n4dlapi]
server = "${getOnlineServer(context, PROFILE_CN)}"
shared_key = ""

[download.profiles.cn.cn_archive]
android_archives = "$cnArchives"
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
main_scenario_unlock_policy = "normal"
subscenario_unlock_policy = "normal"
live_unlock_policy = "normal"
album_catalog_unlock_policy = "normal"

[download.profiles.gl]
enabled = ${isProfileEnabled(context, PROFILE_GL)}
backend = "$glBackend"
museum_unlock_policy = "all"
send_patched_server_info = true

[download.profiles.gl.internal]
archive_root = "$glArchive"

[download.profiles.gl.n4dlapi]
server = "${getOnlineServer(context, PROFILE_GL)}"
shared_key = ""

[download.profiles.gl.none]
client_version = "59.4"

[compat]
region = "dual"
cn_main_headers = true
cn_autocreate_ghome_users = true
cn_wrappers = true
cn_optional_stubs = false
daily_rotation_timezone = "auto"
live_continue_loveca_cost = 1
""" + commonGameConfig()
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
